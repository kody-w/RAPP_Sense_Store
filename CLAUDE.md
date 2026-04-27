# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`kody-w/RAPP_Sense_Store` is the **sense library** of the RAPP platform — peer to `kody-w/RAR` (bare agents) and `kody-w/RAPP_Store` (rapplications). A sense is the smallest installable artifact: one Python file that adds a delimited output channel to every brainstem reply.

The full ecosystem topology is defined in [`kody-w/RAPP_Store/docs/proposals/0002-three-stores.md`](https://github.com/kody-w/RAPP_Store/blob/main/docs/proposals/0002-three-stores.md). This repo's spec is `SPEC.md`.

## Commands

- `python3 -m pytest tests/` — run validator tests
- (Once a sense submission lands as an `[SENSE]` issue, the GitHub Actions workflows `process-sense.yml` + `approve-sense.yml` handle stage and promote.)

## Architecture

- **`SPEC.md`** — sense contract (file layout, required exports, validation rules). Single source of truth.
- **`scripts/lib_senses.py`** — canonical validator. Used by both workflows.
- **`scripts/process_sense.py`** — issue receiver. Parses `[SENSE]` issue body, validates, stages.
- **`scripts/promote_sense.py`** — label-triggered promoter. Moves staging → `senses/@<publisher>/`, merges catalog.
- **`senses/@<publisher>/<slug>_sense.py`** — the artifacts.
- **`index.json`** — catalog, schema `rapp-sense-store/1.0`. Built by `promote_sense.py` on each merge.
- **`index.html`** — landing page, served via GitHub Pages.

## Key contracts

- **Sense file**: required module-level exports `name`, `delimiter`, `response_key`, `wrapper_tag`, `system_prompt`. Optional: `surfaces` (default `["chat"]`), `__manifest__`. See `SPEC.md` §2.
- **Issue title**: `[SENSE] @<publisher>/<slug>`.
- **Body**: a fenced ` ```python ` block with the sense file's source.
- **Publisher namespace**: `@<github-username>` for community, `@rapp` reserved for platform official, requires maintainer override.
- **Reserved names**: `voice` and `twin` (kernel-baked in `kody-w/RAPP/rapp_brainstem/utils/senses/`).

## Constitution

Senses are governed by:
- [Article XXIV](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxiv--senses-are-agent-first-frontends-are-modular-consumers) — senses are agent-first; frontends are modular consumers.
- [Article XXVII](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxvii--rar-holds-files-the-rapp-store-holds-bundles) (and the forthcoming XXXI) — the three-tier model.
- [Article XXVIII](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxviii--material-changes-are-proposed-before-theyre-applied) — material changes need proposals.
- [Article XXIX](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxix--use-the-upstreams-front-door) — submissions go through the `[SENSE]` issue flow.

## Three-store cross-references

| Repo | Artifact | Path | Submission |
|---|---|---|---|
| `kody-w/RAR` | bare `*_agent.py` | `agents/@<publisher>/<slug>_agent.py` | `[AGENT]` |
| `kody-w/RAPP_Store` | rapplication bundles | `apps/@<publisher>/<id>/` | `[RAPP]` |
| **this repo** | senses | `senses/@<publisher>/<slug>_sense.py` | `[SENSE]` |

A single bare agent in RAR — `@rapp/rapp_publish_agent` — can auto-route a submission to the right repo by detecting artifact type.
