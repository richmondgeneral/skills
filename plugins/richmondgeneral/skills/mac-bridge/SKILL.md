---
name: mac-bridge
description: Run Richmond General's Mac-only skills from Cowork by executing them on the Mac over the osascript bridge. LOAD THIS FIRST for any Cowork task that needs the local Mac — the Photos library, local files, intake sweeps, or any RG skill that isn't Cowork-native (photos-library, image-processor, rg-full-auto steps, etc.). Triggers on "from Cowork run …", "pull from the photo library", "check photo lib", "intake sweep", "use the Mac image-processor", "run an RG skill script on my Mac", "control your mac", or when the bridge seems disconnected/unavailable — the osascript tool is usually just DEFERRED (ToolSearch it) rather than off; this skill has the connection-check protocol. NOT needed in Claude Code / code mode — there, run the skills directly.
metadata:
  version: "1.1"
  author: scottybe
  updated: "2026-07-15"
  changelog: |
    v1.1 - note: matte/enhance scripts need their dedicated venvs by absolute path — NOT runnable via rg-skill.sh; plugin-update sync flow
---

# Mac Bridge — run RG skills on the Mac from Cowork

## Connection check — do this BEFORE claiming the bridge is off

The `Control your Mac` osascript tool is usually a **DEFERRED tool**: it does NOT appear in
your active tool list until you fetch it. An empty tool list is NOT evidence the extension is
disconnected (2026-07-15 intake session: the agent told the user to "toggle it on" when it was
already on — the tool was just deferred).

1. `ToolSearch` for `osascript` / "Control your Mac" (e.g. query `+osascript` or
   `select:mcp__Control_your_Mac__osascript`). Deferred tools load on fetch.
2. Probe: `osascript → do shell script "echo bridge-ok"`. If it returns `bridge-ok`, you're live.
3. ONLY if ToolSearch finds nothing AND the probe fails: ask the user to enable
   Cowork → Settings → Extensions → "Control your Mac", then re-run step 1.

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
| Pull an intake album by name | `rg-skill.sh photos-library query_photos.py --album "Intake" --json` |
| Intake an album into an item folder | `rg-skill.sh photos-library intake_to_item.py --sku RG-0028 --album "Intake RG-0028"` |
| Find product-photo clusters | `rg-skill.sh photos-library find_product_clusters.py --days 14 --json` |
| Clean an image (Gemini) | `rg-skill.sh image-processor clean.py --input '<in>' --output '<out>' --remove 'price tag'` |

## ⚠️ The bridge call window is ~30 SECONDS — detach anything longer

Measured 2026-07-16 (binary-searched with sleep probes): an inline bridge call that takes
**28s returns fine; 30s errors** — the MCP client abandons the call at ~30s. Two facts follow:

1. **The error is an ABANDONMENT, not a kill.** The shell command keeps running on the Mac
   to completion (verified: a 120s heartbeat loop ran all 24 beats after the call "failed").
   So after a timeout, do NOT blind-retry — the first run is likely still going and a retry
   races it. Wait, then check for its artifacts (e.g. `file_cluster`'s `.filed.json` manifest)
   or poll with `--status` before re-running. (`file_cluster` re-runs are manifest-safe, but
   only once the first run has written the manifest.)
2. **"Bridge timeout" on file_cluster/matte/enhance-sized jobs is deterministic, not flaky.**
   Before plugin 1.12.1 the tag and album AppleScript stages cost ~1.1s/photo each (the old
   `whose id starts with` did a whole-library scan per photo), putting a full `file_cluster`
   run (mint + sips export + tag + album) at ~45–60s idle — never inside the 30s window.
   1.12.1 switched both to direct `media item id (uuid & "/L0/001")` lookups (~0.01s/photo,
   measured 11 photos: tag 12.5s→0.65s, album 12.3s→0.31s; the scan remains as an on-error
   fallback), so a typical run is now dominated by mint + sips and usually fits inline. But
   Photos mid-iCloud-sync and big clusters still push past 30s — the detach SOP below stays
   the default for full runs.

**SOP for any job that could exceed ~25s:** use the wrapper's detach mode —

```
do shell script ".../rg-skill.sh --detach photos-library file_cluster.py --mint --uuids '...'"
  → returns immediately: {"ok":true,"pid":NNN,"log":"...scratch/bridge-jobs/<ts>.log","poll":"..."}
do shell script ".../rg-skill.sh --status NNN <log>"
  → {"running":true/false,"exit":code-or-null} + the last 20 log lines; poll every ~15-30s
```

The job's `RGEXIT:<code>` trailer in the log records the real exit code (e.g. file_cluster's
exit 3 = tag failures). Logs land in `~/workspace/richmondgeneral/scratch/bridge-jobs/`.
Safe inline: probes, `--list`, `query_photos`, `--plan` dry-runs, single-image sips/enhance.
Detach: `file_cluster` (non-plan), `intake_to_item`, batch matte/enhance/upres, anything Square-bound that loops.

## Rules & gotchas

- **Paths must be Mac-visible.** Inputs/outputs Cowork also needs go under the shared workspace mount (`~/workspace/richmondgeneral/...`) so both sides see them.
- **Env is handled** by the helper (`source ~/.local/bin/env`; `uv` at `~/.local/bin/uv`). Never call `python3` directly over the bridge — that's the system 3.9.6, too old for these skills.
- **Confirm before destructive/outward actions.** The bridge runs real commands on the Mac (file writes, uploads, sends). For anything that changes state or hits a live service (Square, payment links, sending messages), show the user the exact command and get sign-off first.
- **Prefer a dedicated MCP when one exists** (Square, etc.). The bridge is for Mac-local capabilities those don't cover — the Photos library, local image cleanup, local files.
- **Read-only skills with Full Disk Access needs** (photos-library reads `Photos.sqlite`; imessage reads `chat.db`) work over the bridge because they run as the Mac user — but the Mac must have granted FDA to whatever runs osascript.
- **Photo extraction uses `sips`** (macOS built-in — no ImageMagick). `extract_photos.py` converts HEIC→JPEG natively and reports any iCloud-offloaded originals it couldn't reach (download them in Photos, then re-run).

## Notes

- This SKILL.md is the repo source of truth, shipped inside the `richmondgeneral` plugin from the `richmondgeneral/skills` marketplace repo. To pick up changes, update/reinstall the plugin (code-mode: `claude plugin marketplace update richmondgeneral && claude plugin update richmondgeneral@richmondgeneral`; Cowork: refresh the plugin in the plugin manager). Do NOT side-load this skill as a standalone user skill — that creates duplicate resolution. The helper script runs from the repo clone on the Mac (not from Cowork's sandbox).
- In Claude Code / code mode you don't need this — invoke the skills directly (you have the Bash tool).
- ⚠️ `rg-skill.sh` runs everything through the PLUGIN uv env (py3.14) — the image-processor
  enhance/matte scripts (`matte.py`, `upres.py`, `sharpen.py`, `enhance.py`) need their DEDICATED
  venvs instead (torch/rembg have no 3.14 wheels): invoke by absolute interpreter path —
  `~/.cache/rg-matte/bin/python .../matte.py` / `~/.cache/rg-enhance/bin/python .../upres.py` —
  never via rg-skill.sh or `uv run --project`.
