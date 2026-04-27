# RAPP Sense Spec

`schema: rapp-sense/1.0`

A **sense** is a modular per-channel output overlay. The brainstem's LLM emits a delimited block at the end of each reply (e.g. `|||ELI5|||...`); each enabled sense gets one such block. Frontends parse and render whichever blocks their channel cares about. Senses are not agents — they have no `BasicAgent`, no `perform()`, no tool-call schema. They're a system-prompt fragment plus a parsing contract.

## 1. File layout

A sense is **one Python file** at:

```
senses/@<publisher>/<slug>_sense.py
```

`<publisher>` is `@<github-username>` for community submissions, `@rapp` for official platform senses. `<slug>` is snake_case, must match `^[a-z][a-z0-9_]*$`, and the filename must end in `_sense.py`.

The submission unit is a single `.py` file. There is no zip, no manifest sidecar, no UI. Senses are *deliberately* the smallest installable artifact in the platform.

## 2. Module contract

Every sense file MUST export the following module-level names:

| Name | Type | Notes |
|---|---|---|
| `name` | string | snake_case identifier. Must match the slug in the file name. Must be unique across all senses installed in a brainstem. |
| `delimiter` | string | The literal token the LLM emits to start this sense's block. Convention: `\|\|\|<TAG>\|\|\|`. Must be unique across all senses. |
| `response_key` | string | The JSON field clients read for this sense's output. Convention: `<name>_response`. |
| `wrapper_tag` | string | The XML tag clients render the block in (for chat UIs). Convention: same as `name`. |
| `system_prompt` | string | What the brainstem appends to the system message after the main reply instructions. The text the LLM follows to produce this sense's output. |

Optional but recommended:

| Name | Type | Notes |
|---|---|---|
| `surfaces` | list[string] | Which output channels this sense applies to. Default: `["chat"]`. Allowed values: `chat`, `voice`, `mobile`, `cards`. The brainstem only composes a sense's `system_prompt` into the system message when the active surface intersects with the declared list. |
| `__manifest__` | dict | Registry metadata: `{schema: "rapp-sense/1.0", name: "@<pub>/<slug>", version: "X.Y.Z", description: "..."}` — required for catalog inclusion (the receiver auto-fills missing fields where it can). |

## 3. The constraint

A sense's `system_prompt` MUST instruct the LLM to:

1. Emit its `delimiter` exactly once per reply, after the main response.
2. Emit content after the delimiter that's structured to fit the sense's purpose (a headline, a haiku, an ELI5 explanation, etc.).
3. Treat its block as additive, never as a replacement for the main reply.

The brainstem trusts this contract. Frontends parse on the delimiter and render the trailing content under `response_key` / `wrapper_tag`.

## 4. Validation rules

A submission is **accepted** iff all of the following pass (`scripts/lib_senses.py` enforces):

1. The file is named `<slug>_sense.py` with `<slug>` matching `^[a-z][a-z0-9_]*$`.
2. The file parses as Python (`ast.parse` succeeds).
3. The module exports `name`, `delimiter`, `response_key`, `wrapper_tag`, `system_prompt` as string literals (AST-extractable).
4. `name` matches the file's slug.
5. `delimiter` is a non-empty string and follows the `|||TAG|||` convention (or any other unique token — convention is recommended, not enforced).
6. `system_prompt` is at least 40 characters and includes a reference to the `delimiter` (so the LLM is told to emit it).
7. No `{{PLACEHOLDER}}` / `YOUR LOGIC GOES HERE` template remnants in the file.
8. File size < 50 KB (senses are small by design).
9. If a sense with the same `name` is already in the catalog, `__manifest__.version` must be strictly greater (semver).
10. `delimiter` and `name` do not collide with any sense already in the catalog.

A failure on any rule rejects the submission with a specific error code (see `scripts/lib_senses.py`).

## 5. Submission paths

- **Issue template** — open a `[SENSE]` issue with the file pasted in a fenced ``` ```python ``` block. Receiver workflow processes per Article XXIX.
- **`@rapp/rapp_publish_agent`** (in RAR) — auto-detects sense shape and routes here. Standard publishing path.
- **Direct PR** — drop a file under `senses/@<publisher>/` and update `index.json`. Maintainer-only.

## 6. Receiver flow

1. `process-sense.yml` (issues:opened) → `scripts/process_sense.py` parses the issue body, validates per §4, stages to `staging/@<publisher>/<slug>_sense.py`, comments + labels `pending-review`.
2. Maintainer adds `approved` label.
3. `approve-sense.yml` promotes staging → `senses/@<publisher>/`, updates `index.json`, commits, comments, closes the issue.

## 7. Brainstem integration

A sense file installs to `rapp_brainstem/utils/senses/<slug>_sense.py`. The brainstem auto-discovers any `*_sense.py` in that directory at startup. The binder agent (per RAPP issue #22) handles install/uninstall/list against this store the same way it does against `kody-w/RAR` and `kody-w/RAPP_Store`.

## 8. The `surfaces` field

The brainstem knows which surface the active request is on (`/chat` is `chat`, `/voice/...` is `voice`, etc.). Before composing the system message, it filters senses: only senses whose `surfaces` list includes the active surface get their `system_prompt` appended. A user on the voice surface doesn't get the headline sense; a user on the chat surface doesn't get the voice-prosody sense.

This is what makes senses *modular per channel* rather than global.

## 9. Reserved names

These slugs are reserved by the platform: `voice`, `twin`. They're kernel-baked into `kody-w/RAPP/rapp_brainstem/utils/senses/` and cannot be re-published here.
