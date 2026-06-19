---
name: mac-bridge
description: Run Richmond General's Mac-only skills from Cowork by executing them on the Mac over the osascript bridge. Use when working in Cowork and a task needs the local Mac — the Photos library, local files, or any RG skill that isn't Cowork-native (photos-library, image-processor, rg-full-auto steps, etc.). Triggers on "from Cowork run …", "pull from the photo library", "use the Mac image-processor", "run an RG skill script on my Mac", or any intake/photo task in Cowork that needs the Mac. NOT needed in Claude Code / code mode — there, run the skills directly.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-06-18"
---

# Mac Bridge — run RG skills on the Mac from Cowork

Cowork is sandboxed and can't touch the Mac filesystem, Photos, or Python directly. But it **can** run AppleScript via the "Control your Mac" osascript extension, and AppleScript's `do shell script` runs bash on the Mac (verified 2026-06-18). This skill uses that bridge plus a wrapper (`rg-skill.sh`) to run any Richmond General skill script on the Mac in the plugin's `uv` environment and return its output.

## The helper

`rg-skill.sh` lives on the Mac at:
```
/Users/scottybe/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/mac-bridge/scripts/rg-skill.sh
```
It sources the uv env (the bare osascript shell lacks it), finds the plugin root, and runs `uv run --project <plugin> python skills/<skill>/scripts/<script> <args>` (or `bash` for `.sh` scripts).

## How to call it from Cowork

Use the osascript tool with a single `do shell script`:
```
do shell script "/Users/scottybe/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/mac-bridge/scripts/rg-skill.sh <skill> <script> [args...]"
```
The script's stdout (pass `--json` where the script supports it) comes back as the AppleScript result.

### Examples
| Goal | Call |
|---|---|
| Discover runnable scripts | `rg-skill.sh --list` |
| Recent photos from the library | `rg-skill.sh photos-library query_photos.py --days 7 --limit 10 --json` |
| Find product-photo clusters | `rg-skill.sh photos-library find_product_clusters.py --days 14 --json` |
| Clean an image (Gemini) | `rg-skill.sh image-processor clean.py --input '<in>' --output '<out>' --remove 'price tag'` |

## Rules & gotchas

- **Paths must be Mac-visible.** Inputs/outputs Cowork also needs go under the shared workspace mount (`~/workspace/richmondgeneral/...`) so both sides see them.
- **Env is handled** by the helper (`source ~/.local/bin/env`; `uv` at `~/.local/bin/uv`). Never call `python3` directly over the bridge — that's the system 3.9.6, too old for these skills.
- **Confirm before destructive/outward actions.** The bridge runs real commands on the Mac (file writes, uploads, sends). For anything that changes state or hits a live service (Square, payment links, sending messages), show the user the exact command and get sign-off first.
- **Prefer a dedicated MCP when one exists** (Square, etc.). The bridge is for Mac-local capabilities those don't cover — the Photos library, local image cleanup, local files.
- **Read-only skills with Full Disk Access needs** (photos-library reads `Photos.sqlite`; imessage reads `chat.db`) work over the bridge because they run as the Mac user — but the Mac must have granted FDA to whatever runs osascript.
- **Photo extraction uses `sips`** (macOS built-in — no ImageMagick). `extract_photos.py` converts HEIC→JPEG natively and reports any iCloud-offloaded originals it couldn't reach (download them in Photos, then re-run).

## Notes

- This SKILL.md is the repo source of truth. For Cowork to load it, sync it via the Skills UI. The helper script runs from the repo clone on the Mac (not from Cowork's sandbox).
- In Claude Code / code mode you don't need this — invoke the skills directly (you have the Bash tool).
