# RAPP_Sense_Store

**[📋 SPEC](./SPEC.md)** · **[📚 Constitution Article XXIV](https://github.com/kody-w/RAPP/blob/main/CONSTITUTION.md#article-xxiv--senses-are-agent-first-frontends-are-modular-consumers)** · **[⚙️ Engine](https://github.com/kody-w/RAPP)**

Public catalog of RAPP **senses** — modular per-channel output overlays that drop into a brainstem's `rapp_brainstem/utils/senses/` directory.

A sense is a single Python file that tells the LLM to emit a delimited block at the end of each reply. The brainstem composes the sense's `system_prompt` into the system message; the LLM emits `|||DELIMITER|||...content...`; frontends parse and render. Each sense declares which surfaces it applies to (`chat`, `voice`, `mobile`, `cards`) so the right overlays activate per channel.

## What's a sense?

```python
# senses/@rapp/headline_sense.py
name = "headline"
delimiter = "|||HEADLINE|||"
response_key = "headline_response"
wrapper_tag = "headline"
surfaces = ["chat", "mobile"]
system_prompt = (
    "After your main reply, append `|||HEADLINE|||` followed by a single "
    "headline that captures the answer's essence the way a news ticker would. "
    "Verb-driven, present tense, under 10 words. Always emit — empty is not "
    "allowed."
)
```

That's the whole artifact. No `BasicAgent`, no `perform()`, no tools — just a system-prompt fragment + a parsing contract. It's the smallest installable thing in the platform on purpose.

## Three peer stores

| Tier | Repo | Artifact |
|---|---|---|
| Bare agents | [kody-w/RAR](https://github.com/kody-w/RAR) | `*_agent.py` (one file, BasicAgent, perform()) |
| Rapplications | [kody-w/RAPP_Store](https://github.com/kody-w/RAPP_Store) | bundles (agent + UI / service / state) |
| **Senses** | **kody-w/RAPP_Sense_Store** *(this repo)* | `*_sense.py` (per-channel output overlay) |

Per Constitution **Article XXIV** (senses are agent-first, frontends are modular consumers) and **Article XXVII / XXXI** (each artifact has one home).

## Submitting a sense

Recommended path: use the `@rapp/rapp_publish_agent` (in RAR) — it auto-detects sense shape and routes the submission here. Or open a `[SENSE] @<your-username>/<slug>` issue with the sense file in a fenced ```` ```python ```` block. The receiver validates against [SPEC.md](./SPEC.md) and stages for maintainer approval.

See [`SPEC.md`](./SPEC.md) §5 for the full submission flow and §4 for the validation rules.

## Reserved names

`voice` and `twin` are kernel-baked in `kody-w/RAPP/rapp_brainstem/utils/senses/` and cannot be re-published here. Everything else is open territory.

## License

BSD-style.

## Maintainer

`@kody-w`
