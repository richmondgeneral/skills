# Cloudinary Removal + Mac-Bridge Cleanup Routing — Plan

**Date:** 2026-06-18
**Status:** Approved — replacement = **A** (route image cleanup to the Mac `image-processor` / Gemini via the osascript bridge)

## Goal
Remove the Cloudinary MCP and all use of it; replace the Cowork image-cleanup engine
(background removal, price-tag removal) with the Mac `image-processor` (Gemini),
reached over the "Control your Mac" osascript bridge. One cleanup engine (Gemini)
across both Mac and Cowork paths.

## Footprint (scoped 2026-06-18)
- Only `square-image-upload-cowork` uses Cloudinary, and only at the **model/MCP level**
  via connector `mcp__09c02195-…`. `upload_to_square.py` does NOT call Cloudinary.
- `image-processor` mentions Cloudinary only in two comments (`clean.py`, `lib/cleanup_prompts.md`).

## Bridge — verified 2026-06-18 (code-mode layer)
- `mcp__Control_your_Mac__osascript` runs AppleScript → `do shell script` → bash. Proven:
  reaches the repo (`repo-reachable`), macOS 26.6/arm64, can run `uv`.
- **Env gotcha:** `do shell script` is a bare non-login shell — system Python is 3.9.6 and
  `uv` is NOT on its PATH. Must `source $HOME/.local/bin/env` first (`uv` = `$HOME/.local/bin/uv`,
  v0.10.2). Then `uv run` provisions Python ≥3.11.
- **PREREQUISITE (unverified):** confirm the osascript extension is callable from a **Cowork**
  session (the test above was code-mode). 10-sec check: in Cowork, ask it to run a trivial
  osascript (e.g. `do shell script "echo hi"`). If unavailable → see Fallback.

## Remove
1. Disconnect the Cloudinary MCP connector (`mcp__09c02195-…`) in Cowork's connector settings
   (it is an account/app connector — NOT in `claude_desktop_config.json`).
2. Rewrite `square-image-upload-cowork/SKILL.md`: delete Step 2 (Cloudinary processing path),
   the "Cloudinary URL transforms" row in the engine table, the Cloudinary gotchas, and the
   Cloudinary future-enhancements. Replace with the Mac-bridge cleanup path (below).
3. Remove the two Cloudinary comment mentions in `image-processor/scripts/clean.py` and
   `image-processor/lib/cleanup_prompts.md`.

## Replace — cleanup via Mac image-processor (Gemini) over the bridge
The cowork cleanup step becomes an osascript bridge call:
```
do shell script "source $HOME/.local/bin/env && \
  uv run --project $HOME/workspace/richmondgeneral/skills/plugins/richmondgeneral \
  python $HOME/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/image-processor/scripts/clean.py \
  <INPUT> --output <OUTPUT> [--remove 'price tag'] [--fix-damage]"
```
- Input/output files live on the Mac or the shared workspace mount.
- Then upload the cleaned file via the existing `upload_to_square.py` path.
- Keep the existing **sign-off before upload** step.

## Fallback (if the osascript bridge is NOT available in Cowork)
- `computer-use` to drive the Mac (clunky for image work), OR
- do cleanup in **code mode** (native `image-processor`) and hand the cleaned file to Cowork
  via the workspace mount, OR
- a minimal Cowork-native Gemini call (the earlier option **B**) as a stopgap.

## Verify
- `rg -i cloudinary plugins/` → only historical/none remain.
- `square-image-upload-cowork/SKILL.md` documents the bridge cleanup path; no Cloudinary steps.
- A test image runs through the bridge cleanup → cleaned file produced → Square upload succeeds → sign-off intact.

## Open decision recorded
Replacement engine = **A** (Mac Gemini via bridge). Viability of the *Cowork* half depends on
the bridge-in-Cowork prerequisite above.
