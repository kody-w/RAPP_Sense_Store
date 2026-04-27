"""Tests for scripts/lib_senses.py — the SPEC.md §4 validator."""
import textwrap
from pathlib import Path

import pytest

import lib_senses

FIXTURES = Path(__file__).parent / "fixtures"


def good_sense(**overrides):
    """Build a minimal valid sense source. Override specific fields with kwargs
    to flip individual rule violations."""
    fields = {
        "name": '"example"',
        "delimiter": '"|||EXAMPLE|||"',
        "response_key": '"example_response"',
        "wrapper_tag": '"example"',
        "surfaces": '["chat"]',
        "system_prompt": (
            '"After your main reply, append `|||EXAMPLE|||` followed by '
            'a one-line summary of what you said. Always emit — empty is not allowed."'
        ),
    }
    fields.update(overrides)
    lines = [f"{k} = {v}" for k, v in fields.items()]
    return "\n".join(lines) + "\n"


# ── Golden case ───────────────────────────────────────────────────────────

class TestGoldenEli5:
    def test_eli5_fixture_validates(self):
        src = (FIXTURES / "eli5_sense.py").read_text()
        result = lib_senses.validate_sense_text(src, expected_slug="eli5")
        assert result.ok, result.errors
        assert result.name == "eli5"
        assert result.exports.get("delimiter") == "|||ELI5|||"


# ── Required exports ──────────────────────────────────────────────────────

class TestRequiredExports:
    @pytest.mark.parametrize("missing", lib_senses.REQUIRED_EXPORTS)
    def test_missing_export_rejected(self, missing):
        # Build a sense missing one required export
        all_fields = {
            "name": '"example"',
            "delimiter": '"|||EXAMPLE|||"',
            "response_key": '"example_response"',
            "wrapper_tag": '"example"',
            "system_prompt": '"After your main reply, append `|||EXAMPLE|||` plus content."',
        }
        del all_fields[missing]
        src = "\n".join(f"{k} = {v}" for k, v in all_fields.items()) + "\n"
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_MISSING_EXPORT" in e and missing in e for e in result.errors)


# ── Naming rules ──────────────────────────────────────────────────────────

class TestNaming:
    def test_dash_in_name_rejected(self):
        src = good_sense(name='"my-sense"')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_BAD_NAME" in e for e in result.errors)

    def test_uppercase_name_rejected(self):
        src = good_sense(name='"MyExample"')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_BAD_NAME" in e for e in result.errors)

    def test_reserved_name_voice_rejected(self):
        src = good_sense(name='"voice"')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_RESERVED_NAME" in e for e in result.errors)

    def test_reserved_name_twin_rejected(self):
        src = good_sense(name='"twin"')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_RESERVED_NAME" in e for e in result.errors)

    def test_name_slug_mismatch(self):
        src = good_sense(name='"foo"')
        result = lib_senses.validate_sense_text(src, expected_slug="bar")
        assert not result.ok
        assert any("E_NAME_SLUG_MISMATCH" in e for e in result.errors)


# ── Delimiter rules ───────────────────────────────────────────────────────

class TestDelimiter:
    def test_empty_delimiter_rejected(self):
        src = good_sense(delimiter='""')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_BAD_DELIMITER" in e for e in result.errors)

    def test_whitespace_delimiter_rejected(self):
        src = good_sense(delimiter='"|| HEAD ||"')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_BAD_DELIMITER" in e for e in result.errors)

    def test_collision_with_existing(self):
        src = good_sense()
        catalog = {"senses": [
            {"name": "different_sense", "delimiter": "|||EXAMPLE|||"}
        ]}
        result = lib_senses.validate_sense_text(src, existing_catalog=catalog)
        assert not result.ok
        assert any("E_DELIMITER_COLLISION" in e for e in result.errors)


# ── system_prompt rules ───────────────────────────────────────────────────

class TestSystemPrompt:
    def test_too_short_rejected(self):
        src = good_sense(system_prompt='"do thing"')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_SYSTEM_PROMPT_TOO_SHORT" in e for e in result.errors)

    def test_no_delimiter_reference_rejected(self):
        src = good_sense(system_prompt='"This is a long enough prompt but does not mention the literal delimiter token at all"')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_PROMPT_MISSING_DELIMITER" in e for e in result.errors)


# ── surfaces rules ────────────────────────────────────────────────────────

class TestSurfaces:
    def test_default_surfaces_passes(self):
        # No surfaces field at all — defaults to ["chat"], should validate.
        all_fields = {
            "name": '"example"',
            "delimiter": '"|||EXAMPLE|||"',
            "response_key": '"example_response"',
            "wrapper_tag": '"example"',
            "system_prompt": '"After your main reply, append `|||EXAMPLE|||` plus content."',
        }
        src = "\n".join(f"{k} = {v}" for k, v in all_fields.items()) + "\n"
        result = lib_senses.validate_sense_text(src)
        assert result.ok, result.errors

    def test_unknown_surface_rejected(self):
        src = good_sense(surfaces='["chat", "telegraph"]')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_UNKNOWN_SURFACE" in e for e in result.errors)

    @pytest.mark.parametrize("surface", ["chat", "voice", "mobile", "cards"])
    def test_each_known_surface_accepted(self, surface):
        src = good_sense(surfaces=f'["{surface}"]')
        result = lib_senses.validate_sense_text(src)
        assert result.ok, (surface, result.errors)


# ── Misc ──────────────────────────────────────────────────────────────────

class TestMisc:
    def test_template_placeholder_rejected(self):
        src = good_sense(system_prompt='"After your main reply, append `|||EXAMPLE|||`. YOUR LOGIC GOES HERE."')
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_TEMPLATE_PLACEHOLDER" in e for e in result.errors)

    def test_oversize_rejected(self):
        big_prompt = '"' + ("x" * (lib_senses.MAX_SENSE_BYTES + 100)) + '"'
        src = good_sense(system_prompt=big_prompt)
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_SENSE_TOO_LARGE" in e for e in result.errors)

    def test_syntax_error_rejected(self):
        src = "name = 'broken\n  delimiter ="  # malformed Python
        result = lib_senses.validate_sense_text(src)
        assert not result.ok
        assert any("E_SENSE_SYNTAX" in e for e in result.errors)


# ── Catalog merge ─────────────────────────────────────────────────────────

class TestCatalogMerge:
    def test_version_not_bumped_rejected(self):
        src = good_sense() + "\n__manifest__ = {'schema': 'rapp-sense/1.0', 'name': '@x/example', 'version': '1.0.0', 'description': 'x'}\n"
        catalog = {"senses": [{"name": "example", "version": "1.0.0", "delimiter": "X"}]}
        result = lib_senses.validate_sense_text(src, existing_catalog=catalog)
        assert not result.ok
        assert any("E_VERSION_NOT_BUMPED" in e for e in result.errors)

    def test_higher_version_passes(self):
        src = good_sense() + "\n__manifest__ = {'schema': 'rapp-sense/1.0', 'name': '@x/example', 'version': '1.1.0', 'description': 'x'}\n"
        catalog = {"senses": [{"name": "example", "version": "1.0.0", "delimiter": "X"}]}
        result = lib_senses.validate_sense_text(src, existing_catalog=catalog)
        assert result.ok, result.errors

    def test_merge_appends(self):
        cat = {"senses": [{"name": "old"}]}
        new = {"name": "fresh", "publisher": "@rapp"}
        out = lib_senses.merge_index_entry(cat, new)
        assert [s["name"] for s in out["senses"]] == ["old", "fresh"]

    def test_merge_replaces_in_place(self):
        cat = {"senses": [{"name": "x", "publisher": "@rapp", "version": "1.0.0"}]}
        new = {"name": "x", "publisher": "@rapp", "version": "2.0.0"}
        out = lib_senses.merge_index_entry(cat, new)
        assert len(out["senses"]) == 1
        assert out["senses"][0]["version"] == "2.0.0"
