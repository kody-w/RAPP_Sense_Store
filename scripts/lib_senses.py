"""lib_senses — canonical sense validator.

Single source of truth for SPEC.md §4 (validation rules). Used by:

  - .github/workflows/process-sense.yml (server-side validation)
  - .github/workflows/approve-sense.yml (promotion)
  - the @rapp/rapp_publish_agent in RAR (pre-flight, when it routes a sense
    submission here)

Stdlib only. Python 3.8+.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCHEMA_SENSE = "rapp-sense/1.0"
SCHEMA_INDEX = "rapp-sense-store/1.0"

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PUBLISHER_RE = re.compile(r"^@[a-zA-Z0-9][a-zA-Z0-9-]*$")
DELIMITER_RE = re.compile(r"^\S+$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

REQUIRED_EXPORTS = ("name", "delimiter", "response_key", "wrapper_tag", "system_prompt")
ACCEPTED_SURFACES = frozenset({"chat", "voice", "mobile", "cards"})

# Reserved names (kernel-baked in kody-w/RAPP, cannot be republished here):
RESERVED_NAMES = frozenset({"voice", "twin"})

OFFICIAL_PUBLISHERS = frozenset({"@rapp"})

MAX_SENSE_BYTES = 50 * 1024
MIN_SYSTEM_PROMPT = 40

TEMPLATE_PLACEHOLDERS = (
    "{{PLACEHOLDER}}",
    "YOUR LOGIC GOES HERE",
    "TODO REPLACE",
    "RAPP SENSE TEMPLATE",
    "@your_username/",
)

CATALOG_RAW_BASE = "https://raw.githubusercontent.com/kody-w/RAPP_Sense_Store/main"


@dataclass
class ValidationResult:
    ok: bool
    name: str | None = None
    publisher: str | None = None
    exports: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    sha256: str | None = None
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def validate_sense_text(source: str, *,
                        expected_publisher: str | None = None,
                        expected_slug: str | None = None,
                        existing_catalog: dict | None = None) -> ValidationResult:
    """Validate a sense file's source text against SPEC.md §4."""
    errors: list[str] = []

    if len(source.encode("utf-8")) > MAX_SENSE_BYTES:
        return ValidationResult(ok=False, errors=[
            f"E_SENSE_TOO_LARGE: {len(source.encode('utf-8'))} bytes > {MAX_SENSE_BYTES} cap"
        ])

    for ph in TEMPLATE_PLACEHOLDERS:
        if ph in source:
            errors.append(f"E_TEMPLATE_PLACEHOLDER: unresolved '{ph}'")

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return ValidationResult(ok=False, errors=[f"E_SENSE_SYNTAX: {e}"])

    exports = _extract_exports(tree)

    for req in REQUIRED_EXPORTS:
        if req not in exports:
            errors.append(f"E_MISSING_EXPORT: required module-level '{req}' not found or not a string literal")

    name = exports.get("name")
    if name is not None:
        if not isinstance(name, str) or not NAME_RE.match(name):
            errors.append(f"E_BAD_NAME: name must match {NAME_RE.pattern}, got {name!r}")
        elif name in RESERVED_NAMES:
            errors.append(f"E_RESERVED_NAME: '{name}' is reserved (kernel-baked in kody-w/RAPP)")
        if expected_slug and name and name != expected_slug:
            errors.append(f"E_NAME_SLUG_MISMATCH: name '{name}' != filename slug '{expected_slug}'")

    delimiter = exports.get("delimiter")
    if delimiter is not None:
        if not isinstance(delimiter, str) or not delimiter:
            errors.append("E_BAD_DELIMITER: delimiter must be a non-empty string")
        elif not DELIMITER_RE.match(delimiter):
            errors.append(f"E_BAD_DELIMITER: delimiter must contain no whitespace, got {delimiter!r}")

    sp = exports.get("system_prompt")
    if isinstance(sp, str):
        if len(sp) < MIN_SYSTEM_PROMPT:
            errors.append(f"E_SYSTEM_PROMPT_TOO_SHORT: < {MIN_SYSTEM_PROMPT} chars")
        if delimiter and isinstance(delimiter, str) and delimiter not in sp:
            errors.append(
                f"E_PROMPT_MISSING_DELIMITER: system_prompt does not reference the "
                f"delimiter '{delimiter}'. The LLM won't know what token to emit."
            )

    surfaces = exports.get("surfaces")
    if surfaces is not None:
        if not isinstance(surfaces, list) or not all(isinstance(s, str) for s in surfaces):
            errors.append("E_BAD_SURFACES: surfaces must be a list of strings")
        else:
            unknown = [s for s in surfaces if s not in ACCEPTED_SURFACES]
            if unknown:
                errors.append(
                    f"E_UNKNOWN_SURFACE: {unknown} not in {sorted(ACCEPTED_SURFACES)}. "
                    f"Add to the SPEC and validator if a new surface is needed."
                )

    manifest = _extract_dict_literal(tree, "__manifest__")
    if manifest is not None:
        m_schema = manifest.get("schema")
        if m_schema and m_schema != SCHEMA_SENSE:
            errors.append(f"E_BAD_MANIFEST_SCHEMA: __manifest__.schema must be '{SCHEMA_SENSE}'")
        m_name = manifest.get("name", "")
        if m_name and PUBLISHER_RE.match(m_name.split("/")[0] if "/" in m_name else ""):
            mp = m_name.split("/")[0]
            if expected_publisher and mp.lower() != expected_publisher.lower() and mp not in OFFICIAL_PUBLISHERS:
                errors.append(
                    f"E_PUBLISHER_MISMATCH: __manifest__.name publisher '{mp}' != "
                    f"submitter '{expected_publisher}'"
                )

    if existing_catalog is not None and name:
        prev = _find_catalog_entry(existing_catalog, name)
        if prev:
            new_v = (manifest or {}).get("version", "0.0.0")
            old_v = prev.get("version", "0.0.0")
            if not _semver_gt(new_v, old_v):
                errors.append(
                    f"E_VERSION_NOT_BUMPED: '{name}' already in catalog at v{old_v}; "
                    f"submission must bump version (got v{new_v})."
                )
        # Delimiter collision against a different sense:
        for entry in existing_catalog.get("senses", []):
            if entry.get("name") != name and entry.get("delimiter") == delimiter:
                errors.append(
                    f"E_DELIMITER_COLLISION: delimiter '{delimiter}' is already "
                    f"taken by '{entry.get('name')}'. Pick a unique token."
                )

    publisher = None
    if isinstance(manifest, dict):
        mn = manifest.get("name", "")
        if "/" in mn:
            publisher = mn.split("/")[0]

    sha = hashlib.sha256(source.encode("utf-8")).hexdigest()

    if errors:
        return ValidationResult(ok=False, name=name, publisher=publisher,
                                exports=exports, manifest=manifest or {},
                                sha256=sha, errors=errors)
    return ValidationResult(ok=True, name=name, publisher=publisher,
                            exports=exports, manifest=manifest or {},
                            sha256=sha, errors=[])


# ── Catalog merge ─────────────────────────────────────────────────────────

def build_index_entry(result: ValidationResult, publisher: str) -> dict:
    if not result.ok:
        raise ValueError("cannot build entry from a failed validation")
    name = result.name
    surfaces = result.exports.get("surfaces", ["chat"])
    rel_path = f"senses/{publisher}/{name}_sense.py"
    src = result.exports
    return {
        "name": name,
        "publisher": publisher,
        "version": (result.manifest or {}).get("version", "0.1.0"),
        "delimiter": src.get("delimiter"),
        "response_key": src.get("response_key"),
        "wrapper_tag": src.get("wrapper_tag"),
        "surfaces": surfaces,
        "description": (result.manifest or {}).get("description", ""),
        "filename": f"{name}_sense.py",
        "url": f"{CATALOG_RAW_BASE}/{rel_path}",
        "sha256": result.sha256,
    }


def merge_index_entry(catalog: dict, entry: dict) -> dict:
    out = dict(catalog)
    senses = list(out.get("senses", []))
    for i, s in enumerate(senses):
        if s.get("name") == entry["name"] and s.get("publisher") == entry["publisher"]:
            senses[i] = entry
            break
    else:
        senses.append(entry)
    out["senses"] = senses
    return out


# ── Internals ─────────────────────────────────────────────────────────────

def _extract_exports(tree: ast.Module) -> dict[str, Any]:
    """Pull module-level string assignments + literal lists/dicts."""
    out: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    val = _safe_literal(node.value)
                    if val is not None:
                        out[tgt.id] = val
    return out


def _safe_literal(node):
    """Return Python literal value if node is a constant / list / tuple / dict
    of constants. Otherwise None."""
    try:
        return ast.literal_eval(node)
    except Exception:
        # Tolerate string concatenation and parenthesized strings:
        if isinstance(node, ast.JoinedStr):
            return None  # f-strings — skip
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            l = _safe_literal(node.left)
            r = _safe_literal(node.right)
            if isinstance(l, str) and isinstance(r, str):
                return l + r
        return None


def _extract_dict_literal(tree: ast.Module, name: str) -> dict | None:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    if isinstance(node.value, ast.Dict):
                        try:
                            return ast.literal_eval(node.value)
                        except Exception:
                            return None
    return None


def _find_catalog_entry(catalog: dict, name: str) -> dict | None:
    for s in catalog.get("senses", []):
        if s.get("name") == name:
            return s
    return None


def _semver_gt(a: str, b: str) -> bool:
    ma, mb = SEMVER_RE.match(a or ""), SEMVER_RE.match(b or "")
    if not ma or not mb:
        return False
    return tuple(int(x) for x in ma.groups()) > tuple(int(x) for x in mb.groups())
