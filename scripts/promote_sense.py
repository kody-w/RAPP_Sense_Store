#!/usr/bin/env python3
"""promote_sense.py — promote a staged sense to the live catalog.

Triggered when a maintainer adds the `approved` label to a [SENSE] issue.
Reads staging/_pending.json for the matching issue, moves the staged file
from staging/@<publisher>/ → senses/@<publisher>/, recomputes integrity,
merges the catalog entry into index.json, removes the pending record.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import lib_senses


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STAGING = REPO_ROOT / "staging"
DEFAULT_CATALOG = REPO_ROOT / "index.json"


def find_pending(staging_dir: Path, issue: int) -> dict:
    p = staging_dir / "_pending.json"
    if not p.is_file():
        raise FileNotFoundError(f"E_NO_PENDING: {p}")
    items = json.loads(p.read_text()).get("items", [])
    for it in items:
        if it.get("issue") == issue:
            return it
    raise LookupError(f"E_NO_PENDING_FOR_ISSUE: issue #{issue} not in {p}")


def remove_pending(staging_dir: Path, issue: int):
    p = staging_dir / "_pending.json"
    if not p.is_file():
        return
    d = json.loads(p.read_text())
    d["items"] = [i for i in d.get("items", []) if i.get("issue") != issue]
    p.write_text(json.dumps(d, indent=2))


def promote(event: dict, staging_dir: Path, catalog_path: Path) -> tuple[bool, str]:
    issue = event.get("issue", {})
    issue_number = issue.get("number")
    try:
        item = find_pending(staging_dir, issue_number)
    except (FileNotFoundError, LookupError) as e:
        return False, f"## ❌ Promotion failed\n\n`{e}`\n"

    publisher = item["publisher"]
    slug = item["slug"]
    base = staging_dir.parent
    src = base / item["staged_path"]
    if not src.is_file():
        return False, f"## ❌ Promotion failed\n\n`E_STAGED_MISSING: {src}`\n"

    target_dir = base / "senses" / publisher
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{slug}_sense.py"
    shutil.move(str(src), str(target))

    # Re-validate the actual on-disk file to recompute fields from authoritative
    # bytes (don't trust the staging metadata blindly).
    catalog = json.loads(catalog_path.read_text()) if catalog_path.is_file() else {
        "schema": "rapp-sense-store/1.0", "senses": [],
    }
    result = lib_senses.validate_sense_text(target.read_text())
    if not result.ok:
        return False, (
            f"## ❌ Promotion failed (post-promote re-validation)\n\n"
            f"Errors: `{result.errors}`\n"
        )

    entry = lib_senses.build_index_entry(result, publisher)
    catalog = lib_senses.merge_index_entry(catalog, entry)
    catalog["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    remove_pending(staging_dir, issue_number)

    return True, (
        f"## ✅ Sense approved and promoted\n\n"
        f"- **id:** `{publisher}/{result.name}`\n"
        f"- **version:** `{entry['version']}`\n"
        f"- **delimiter:** `{entry['delimiter']}`\n"
        f"- **surfaces:** `{', '.join(entry['surfaces'])}`\n"
        f"- **url:** {entry['url']}\n\n"
        f"Brainstems with the binder agent installed will pick this up on next "
        f"`browse` / `install` against `RAPP_Sense_Store`.\n"
    )


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--event-path", required=True)
    p.add_argument("--staging-dir", default=str(DEFAULT_STAGING))
    p.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    args = p.parse_args(argv)

    event = json.loads(Path(args.event_path).read_text())
    ok, report = promote(event, Path(args.staging_dir), Path(args.catalog))
    sys.stdout.write(report)
    sys.stdout.flush()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
