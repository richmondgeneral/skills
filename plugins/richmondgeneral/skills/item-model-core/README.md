# item-model-core — library module (NOT a skill)

This directory intentionally has **no `SKILL.md`**. It is not a user-facing skill; it
packages the shared `item_model` Python library under `lib/item_model/` (the canonical
read/write path for `items/RG-XXXX/label.json`, catalog state, channel registry, page
read/write, diff, and measurements) that other Richmond General skills import.

A skill loader that scans for `SKILL.md` correctly **skips** this directory, and the
plugin loads normally without it. Packaging/metadata audits that flag "missing SKILL.md"
here can ignore it — it is a library, by design.
