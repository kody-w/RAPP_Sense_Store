#!/usr/bin/env python3
"""
build_pokedex_api.py — generate the static RAPP_Sense_Store Pokédex API.

Mirrors kody-w/RAPP_Store + kody-w/RAR's Pokédex APIs (same shape,
applied to sense overlays). Modeled on PokeAPI: predictable static
URLs, no backend.

URL shape (relative to repo root, all under api/v1/):

    api/v1/index.json                    — paginated list + counts
    api/v1/sense/<id>.json               — single sense entry
    api/v1/sense/<id>.py                 — slug-named mirror of the .py
    api/v1/sprite/<id>.svg               — deterministic generative sprite

Where <id> is `<publisher>__<sense_name>` (URL-safe).

Sources `index.json` (existing source of truth) — each entry already
carries the sense protocol fields (delimiter / response_key /
wrapper_tag / surfaces / description / sha256). No registry rebuild
needed; this is a pure transformation.

The rapp-zoo Discover tab fetches from this + RAPP_Store + RAR and
renders the union as one Pokédex. Per Article XXXVII, every entry is
an organism; the catalog of choice is just where the user's eye lands.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_INDEX_SRC = _REPO / "index.json"
_API = _REPO / "api" / "v1"

SCHEMA_API_INDEX = "rapp-sense-pokedex-api/1.0"
SCHEMA_API_SENSE = "rapp-sense-pokedex-sense/1.0"
RAW_PREFIX = "https://raw.githubusercontent.com/kody-w/RAPP_Sense_Store/main"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _slug(publisher: str, name: str) -> str:
    pub = publisher[1:] if publisher.startswith("@") else publisher
    return f"{pub}__{name}".replace("/", "_")


PALETTES = {
    "default":   ["#7df0c8", "#3fb950", "#1a7f37"],   # mint family — senses are perception channels
    "voice":     ["#79c0ff", "#58a6ff", "#0969da"],
    "twin":      ["#b58ddf", "#a78bfa", "#8250df"],
    "summary":   ["#ffa657", "#f78166", "#bc4c00"],
}


def _sprite_svg(seed: str, name_for_palette: str = "default") -> str:
    palette_key = "default"
    for k in PALETTES:
        if k != "default" and k in name_for_palette.lower():
            palette_key = k
            break
    palette = PALETTES[palette_key]
    h = abs(int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16))
    fg = palette[h % 3]
    bg = palette[(h >> 4) % 3]
    rects = []
    for y in range(6):
        for x in range(3):
            bit = (h >> ((y * 3 + x) % 28)) & 1
            if bit:
                rects.append(f'<rect x="{x*8}" y="{y*8}" width="8" height="8" fill="{fg}"/>')
                rects.append(f'<rect x="{(5-x)*8}" y="{y*8}" width="8" height="8" fill="{fg}"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="192" height="192" shape-rendering="crispEdges">\n'
        f'  <rect width="48" height="48" fill="{bg}" opacity="0.25"/>\n'
        + "  " + "\n  ".join(rects) + "\n</svg>\n"
    )


def _build_entry(sense: dict) -> dict:
    name = sense["name"]
    publisher = sense.get("publisher", "@anon")
    slug = _slug(publisher, name)
    sha = sense.get("sha256") or ""
    rappid = f"rappid:v2:sense:{publisher}/{name}:{(sha or slug)[:32]}"

    return {
        "schema": SCHEMA_API_SENSE,
        "id": slug,
        "name": name,
        "rappid": rappid,
        "version": sense.get("version", "0.0.0"),
        "publisher": publisher,
        "description": sense.get("description"),

        # Sense protocol fields — what the kernel needs to know
        "delimiter":    sense.get("delimiter"),
        "response_key": sense.get("response_key"),
        "wrapper_tag":  sense.get("wrapper_tag"),
        "surfaces":     sense.get("surfaces", []),

        # Stats
        "filename": sense.get("filename"),
        "sha256":   sha,

        # Lineage
        "parent_rappid": "rappid:v2:prototype:@rapp/origin:0b635450c04249fbb4b1bdb571044dec@github.com/kody-w/RAPP",

        # Asset URLs
        "sprite_url": f"{RAW_PREFIX}/api/v1/sprite/{slug}.svg",
        "py_url":     sense.get("url"),                                # original namespaced
        "api_py_url": f"{RAW_PREFIX}/api/v1/sense/{slug}.py",          # slug-named mirror
        "self_url":   f"{RAW_PREFIX}/api/v1/sense/{slug}.json",
        "github_url": f"https://github.com/kody-w/RAPP_Sense_Store/blob/main/senses/{publisher}/{sense.get('filename','')}",
    }


def main():
    if not _INDEX_SRC.is_file():
        print(f"err: index.json not found at {_INDEX_SRC}", file=sys.stderr)
        sys.exit(1)

    if _API.exists():
        shutil.rmtree(_API)
    (_API / "sense").mkdir(parents=True)
    (_API / "sprite").mkdir(parents=True)

    src_index = json.loads(_INDEX_SRC.read_text())
    senses = src_index.get("senses", [])

    entries = []
    for sense in senses:
        entry = _build_entry(sense)
        slug = entry["id"]
        entries.append(entry)
        (_API / "sense" / f"{slug}.json").write_text(json.dumps(entry, indent=2) + "\n")
        (_API / "sprite" / f"{slug}.svg").write_text(_sprite_svg(entry["rappid"], entry["name"]))
        # Mirror the .py at a slug-named URL for stable fetching
        publisher = entry["publisher"]
        fname = entry.get("filename")
        if fname:
            src_py = _REPO / "senses" / publisher / fname
            if src_py.is_file():
                (_API / "sense" / f"{slug}.py").write_bytes(src_py.read_bytes())
        print(f"  ✓ {publisher}/{entry['name']:<14}  {entry.get('delimiter','?')}")

    index = {
        "schema": SCHEMA_API_INDEX,
        "name": "RAPP_Sense_Store Pokédex API",
        "description": (
            "Static catalog API for RAPP sense overlays — per-channel "
            "output transformers that the brainstem installs into "
            "utils/senses/. Mirrors the RAPP_Store + RAR API shape so "
            "the rapp-zoo can browse all federation stores with one "
            "client. Each entry has a sprite, sense protocol metadata "
            "(delimiter / response_key / wrapper_tag / surfaces), and "
            "a slug-named .py mirror at a stable URL."
        ),
        "version": "1.0.0",
        "generated_at": _now_iso(),
        "count": len(entries),
        "self_url":  f"{RAW_PREFIX}/api/v1/index.json",
        "senses": [
            {
                "id":           e["id"],
                "name":         e["name"],
                "publisher":    e["publisher"],
                "version":      e["version"],
                "delimiter":    e["delimiter"],
                "wrapper_tag":  e["wrapper_tag"],
                "surfaces":     e["surfaces"],
                "url":          e["self_url"],
                "sprite":       e["sprite_url"],
                "py":           e["api_py_url"],
            }
            for e in entries
        ],
    }
    (_API / "index.json").write_text(json.dumps(index, indent=2) + "\n")

    print()
    print(f"  → wrote {len(entries)} sense entries to {_API.relative_to(_REPO)}/")
    print(f"  → index: api/v1/index.json")


if __name__ == "__main__":
    main()
