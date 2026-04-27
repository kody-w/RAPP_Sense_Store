# Proposal 0001 — Bootstrap RAPP_Sense_Store

| | |
|---|---|
| **Status** | Draft |
| **Sponsor** | @kody-w |
| **Drafted** | 2026-04-27 |
| **Touches** | Everything in this repo (it's currently empty). Migrates 5 senses from `kody-w/RAPP_Store/senses/` into `senses/@rapp/`. |
| **Implements step A of** | [`kody-w/RAPP_Store/docs/proposals/0002-three-stores.md`](https://github.com/kody-w/RAPP_Store/blob/main/docs/proposals/0002-three-stores.md) |
| **Complies with** | Article XXVIII (proposals before changes), Article XXIX (front doors), Article XXX (pipelines end-to-end). |

## 1. Context

`kody-w/RAPP_Sense_Store` was just created as the third peer store (alongside `kody-w/RAR` for bare agents and `kody-w/RAPP_Store` for rapplications). The repo is empty. This proposal is its first commit — bootstrapping the spec, validator, workflows, scripts, tests, landing page, and the empty catalog scaffold so the `[SENSE]` submission flow is live and the migration of the existing 5 senses can happen via that flow (per Article XXIX — use the upstream's front door).

## 2. What this proposal ships

The PR for this proposal lands the following at the repo root:

| Path | Purpose |
|---|---|
| `SPEC.md` | The sense contract: file layout, required exports (`name`, `delimiter`, `response_key`, `wrapper_tag`, `system_prompt`), optional `surfaces` field for per-channel modularity, validation rules. |
| `README.md` | Public-facing doc for submitters and maintainers. |
| `CLAUDE.md` | Codebase guidance for Claude Code. |
| `scripts/lib_senses.py` | Canonical validator implementing SPEC §4. |
| `scripts/process_sense.py` | Issue receiver — parses `[SENSE]` issue body, validates, stages. |
| `scripts/promote_sense.py` | Approval-label promoter — staging → `senses/@<publisher>/`, merges catalog. |
| `tests/conftest.py`, `tests/test_lib_senses.py`, `tests/fixtures/eli5_sense.py` | Pytest suite for the validator. ELI5 fixture copied from `RAPP_Store/senses/` as the golden case. |
| `.github/ISSUE_TEMPLATE/submit-sense.yml` | Form-style issue template. |
| `.github/workflows/process-sense.yml` | Fires on `[SENSE]` issue open/edit/reopen → runs `process_sense.py`. |
| `.github/workflows/approve-sense.yml` | Fires on `approved` label → runs `promote_sense.py`. |
| `index.json` | Empty catalog scaffold (`schema: rapp-sense-store/1.0`, `senses: []`). |
| `index.html` | GitHub Pages landing — gateway listing the cataloged senses. |
| `.gitignore` | Standard ignores. |

This is a single PR (this proposal's companion). Once merged, the repo is operational: the next thing to land is the first `[SENSE]` issue migrating ELI5.

## 3. The sense contract (summary; full in `SPEC.md`)

A sense is **one Python file** at `senses/@<publisher>/<slug>_sense.py` exporting:

- `name` (string, snake_case, matches filename slug, unique in catalog)
- `delimiter` (string, no whitespace, unique in catalog — the LLM emits this token)
- `response_key` (string, the JSON field clients read)
- `wrapper_tag` (string, the chat-XML tag clients render)
- `system_prompt` (string, ≥40 chars, must reference the delimiter)

Optional but recommended:
- `surfaces` (list, default `["chat"]`, one of `chat`/`voice`/`mobile`/`cards` — **the modular-per-channel piece**)
- `__manifest__` (dict, registry metadata for catalog inclusion)

Reserved names: `voice`, `twin` (kernel-baked in `kody-w/RAPP/rapp_brainstem/utils/senses/`).

## 4. Migration plan (per-step)

Each step is its own action; A is this PR; B–F follow.

| | Step | Mechanism |
|---|---|---|
| A | This PR — bootstrap repo (SPEC, scripts, workflows, tests, scaffolding). | One PR in this repo. |
| B | Migrate ELI5: open `[SENSE] @rapp/eli5` issue with the source from `kody-w/RAPP_Store/senses/eli5_sense.py`. Validates → stages → maintainer approves → forges. | One RAR-style issue. |
| C | Migrate Emoji, Haiku, Headline, TLDR — same flow as B, one at a time (concurrency: workflows serialize via `concurrency: sense-state` group, so submitting in batch is safe). | 4 issues. |
| D | After all 5 land here, drop `senses/` from `kody-w/RAPP_Store` (handled by step C of the parent Proposal 0002). | PR in `RAPP_Store`. |
| E | Update `RAPP_Store`'s `vbrainstem.html` to load senses from this repo's `index.json` for the unified browse surface (handled by step H of Proposal 0002). | PR in `RAPP_Store`. |
| F | Update `kody-w/RAPP/rapp_brainstem/utils/services/binder_service.py` to know about this catalog as a third source (handled by step F of Proposal 0002). | PR in `RAPP`. |

## 5. The two kernel-baked senses stay

`voice_sense.py` and `twin_sense.py` live in `kody-w/RAPP/rapp_brainstem/utils/senses/`. They're **load-bearing platform features** the brainstem ships with — voice routing and the twin separator are constitutional surfaces (Article XX, Article XXII), not community submissions. They stay where they are. Their slugs (`voice`, `twin`) are reserved in `RESERVED_NAMES` so the community can't republish them.

## 6. What's intentionally NOT shipped in this proposal

- **A submission router.** Step E of Proposal 0002 ships `@rapp/rapp_publish_agent` in `kody-w/RAR`, which auto-detects sense shape and routes here. Until then, the `[SENSE]` issue template is the user-facing path.
- **A binder integration.** Step F of Proposal 0002 extends `rapp_brainstem`'s binder to know about this catalog. Until then, senses install via manual `curl` per the README.
- **An aggregated catalog.** Step H of Proposal 0002 builds `RAPP_Store/ecosystem.json` merging all three. This repo just publishes its own `index.json`.

This proposal stays scoped to bootstrapping the store itself. The integration work belongs to the parent proposal in `RAPP_Store`.

## 7. Rollback

The bootstrap PR is `git revert`-able as a single squash-merge. If reverted, the repo returns to empty and the [SENSE] flow stops working — no senses are in flight at that point (B onward hasn't happened yet), so no submissions are stranded.

## 8. Open questions

1. **Should `surfaces` be required rather than defaulted to `["chat"]`?** Requiring it forces every submitter to think about per-channel applicability, which is the whole point of the field. Defaulting it lowers friction. Leaning: keep defaulted; reconsider if many senses end up with stale `["chat"]` defaults that should have included voice or mobile.
2. **Catalog format: include the `system_prompt` text in `index.json` or not?** Including it makes the catalog self-contained (clients can render senses without a second fetch) but bloats the JSON (~2-5KB per sense). Excluding keeps `index.json` small and forces a fetch per install. Leaning: exclude — same pattern RAPP_Store uses (only metadata + URLs in catalog, full source in the artifact file).
3. **Per-channel filtering happens where?** The brainstem's binder service composes the system message; it filters senses by `surfaces ∩ active_channel`. This means brainstems that haven't been updated to know about `surfaces` will load all senses for all channels. That's the same as today (no filtering), so backward-compatible. New brainstems just get the better behavior.

## 9. References

- Parent: [`RAPP_Store/docs/proposals/0002-three-stores.md`](https://github.com/kody-w/RAPP_Store/blob/main/docs/proposals/0002-three-stores.md)
- Constitution: [Article XXIV](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxiv--senses-are-agent-first-frontends-are-modular-consumers), [Article XXVII](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxvii--rar-holds-files-the-rapp-store-holds-bundles), [XXVIII](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxviii--material-changes-are-proposed-before-theyre-applied), [XXIX](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxix--use-the-upstreams-front-door), [XXX](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxx--pipelines-run-end-to-end-under-standing-authorization)
- The 5 senses being migrated: [`kody-w/RAPP_Store/senses/`](https://github.com/kody-w/RAPP_Store/tree/main/senses) — eli5, emoji, haiku, headline, tldr.
