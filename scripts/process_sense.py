#!/usr/bin/env python3
"""process_sense.py — receiver for [SENSE] issue submissions.

Reads the GitHub Actions issue event, extracts the sense source from a
fenced ```python``` block, validates against SPEC.md §4 via lib_senses,
stages the file under staging/@<publisher>/<slug>_sense.py.

Stdout is the markdown report the workflow comments back. Exit 0 on
pass (workflow labels `pending-review`); non-zero on fail (workflow
labels `failed`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import lib_senses


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STAGING = REPO_ROOT / "staging"
DEFAULT_CATALOG = REPO_ROOT / "index.json"

PYTHON_BLOCK_RE = re.compile(r"```python\s*\n(.*?)\n```", re.DOTALL)
TITLE_RE = re.compile(r"\[SENSE\]\s+(@[^/\s]+)/([a-z][a-z0-9_]*)")


def load_catalog(p: Path) -> dict:
    if p.is_file():
        return json.loads(p.read_text())
    return {"schema": "rapp-sense-store/1.0", "senses": []}


def extract_sense_source(body: str) -> str:
    m = PYTHON_BLOCK_RE.search(body or "")
    if not m:
        raise ValueError("E_NO_PAYLOAD: issue body has no ```python``` block")
    return m.group(1)


def parse_title(title: str) -> tuple[str, str]:
    m = TITLE_RE.search(title or "")
    if not m:
        raise ValueError(
            "E_BAD_TITLE: issue title must match '[SENSE] @<publisher>/<slug>' "
            "(slug is snake_case)."
        )
    return m.group(1), m.group(2)


def process(event: dict, staging_dir: Path, catalog_path: Path) -> tuple[bool, str]:
    issue = event.get("issue", {})
    issue_number = issue.get("number")
    submitter = "@" + issue.get("user", {}).get("login", "")
    body = issue.get("body") or ""
    title = issue.get("title", "")

    try:
        publisher, slug = parse_title(title)
    except ValueError as e:
        return False, _md_error(issue_number, [str(e)])

    try:
        source = extract_sense_source(body)
    except ValueError as e:
        return False, _md_error(issue_number, [str(e)])

    catalog = load_catalog(catalog_path)
    result = lib_senses.validate_sense_text(
        source,
        expected_publisher=submitter,
        expected_slug=slug,
        existing_catalog=catalog,
    )

    if not result.ok:
        return False, _md_error(issue_number, result.errors)

    # Publisher namespace: title-declared publisher must match submitter UNLESS
    # it's an official @rapp/* override (maintainer accepts the issue).
    if publisher in lib_senses.OFFICIAL_PUBLISHERS and submitter.lower() not in {"@kody-w", "@rapp"}:
        return False, _md_error(issue_number, [
            f"E_PUBLISHER_MISMATCH: '{publisher}' is reserved; submitter '{submitter}'"
        ])
    if publisher not in lib_senses.OFFICIAL_PUBLISHERS and publisher.lower() != submitter.lower():
        return False, _md_error(issue_number, [
            f"E_PUBLISHER_MISMATCH: title declares '{publisher}' but submitter is '{submitter}'"
        ])

    target_dir = staging_dir / publisher
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{slug}_sense.py"
    target.write_text(source)

    pending_path = staging_dir / "_pending.json"
    pending = json.loads(pending_path.read_text()) if pending_path.is_file() else {"items": []}
    pending["items"] = [p for p in pending["items"] if p.get("issue") != issue_number]
    pending["items"].append({
        "issue": issue_number,
        "submitter": submitter,
        "publisher": publisher,
        "slug": slug,
        "name": result.name,
        "delimiter": result.exports.get("delimiter"),
        "sha256": result.sha256,
        "staged_path": str(target.relative_to(staging_dir.parent)),
    })
    pending_path.write_text(json.dumps(pending, indent=2))

    return True, _md_ok(issue_number, publisher, slug, result)


def _md_error(n, errs):
    bullets = "\n".join(f"- `{e}`" for e in errs)
    return (
        f"## ❌ Sense submission rejected\n\n"
        f"Issue #{n} did not pass SPEC.md §4 validation:\n\n{bullets}\n\n"
        f"See [SPEC.md](https://github.com/kody-w/RAPP_Sense_Store/blob/main/SPEC.md) "
        f"for the full ruleset.\n"
    )


def _md_ok(n, publisher, slug, result):
    surfaces = result.exports.get("surfaces", ["chat"])
    return (
        f"## ✅ Sense validated\n\n"
        f"- **publisher:** `{publisher}`\n"
        f"- **name:** `{result.name}`\n"
        f"- **delimiter:** `{result.exports.get('delimiter')}`\n"
        f"- **surfaces:** `{', '.join(surfaces)}`\n"
        f"- **sha256:** `{(result.sha256 or '')[:16]}…`\n\n"
        f"Staged under `staging/{publisher}/{slug}_sense.py`. A maintainer will "
        f"review and add the `approved` label to promote.\n"
    )


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--event-path", required=True)
    p.add_argument("--staging-dir", default=str(DEFAULT_STAGING))
    p.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    args = p.parse_args(argv)

    event = json.loads(Path(args.event_path).read_text())
    ok, report = process(event, Path(args.staging_dir), Path(args.catalog))
    sys.stdout.write(report)
    sys.stdout.flush()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
