# Richmond General Plugin Marketplace — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Package the `richmondgeneral/skills` repo as a local-directory marketplace exposing one `richmondgeneral` plugin, so the desktop app and Cowork load all skills from one source.

**Architecture:** Add `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json` at the repo root; move all in-scope skills under `skills/`; update `docs/build-skill.sh` for the new path; retire the dead `sync-*` scripts; document the install/update flow in `README.md`. The change is non-destructive — no surface loads anything new until the marketplace is added and the plugin installed.

**Tech Stack:** Claude Code plugin/marketplace manifests (JSON), bash, git, `jq`.

**Companion design:** `docs/plans/2026-06-17-richmondgeneral-plugin-marketplace-design.md`

**Working dir:** `~/workspace/richmondgeneral/skills` (the local clone the marketplace will point at).

**Scope reminder:** every top-level dir with a `SKILL.md` **except** `rg-inventory-legacy`, `rg-new-item-legacy`, and `archive/`.

---

### Task 1: Safety branch + frozen inventory

**Files:** none (git + a scratch inventory file)

**Step 1: Branch off main**
```bash
cd ~/workspace/richmondgeneral/skills
git switch -c feat/plugin-marketplace
```

**Step 2: Capture the in-scope skill inventory (the move list + the count to verify against)**
```bash
for d in */; do
  name="${d%/}"
  case "$name" in skills|docs|dist|archive|rg-inventory-legacy|rg-new-item-legacy) continue;; esac
  [ -f "$name/SKILL.md" ] && echo "$name"
done | sort | tee /tmp/rg-inscope-skills.txt
wc -l < /tmp/rg-inscope-skills.txt
```
Expected: ~29 skill names; record the exact count `N`.

**Step 3: Commit nothing yet** — proceed to Task 2.

---

### Task 2: Move skills under `skills/`

**Files:** `git mv` every in-scope skill dir → `skills/<skill>/`

**Step 1: Write the verification first (it should fail now)**
```bash
find skills -mindepth 2 -maxdepth 2 -name SKILL.md 2>/dev/null | wc -l
```
Expected now: `0` (no `skills/` dir yet).

**Step 2: Perform the move**
```bash
cd ~/workspace/richmondgeneral/skills
mkdir -p skills
while IFS= read -r name; do
  git mv "$name" "skills/$name"
done < /tmp/rg-inscope-skills.txt
```

**Step 3: Re-run the verification — it should now pass**
```bash
find skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l   # expect N (from Task 1)
git status --short | rg '^R' | wc -l                         # expect renames, not delete+add
ls rg-inventory-legacy rg-new-item-legacy >/dev/null && echo "legacy left at root: OK"
```
Expected: count == `N`; changes show as renames (`R`); legacy dirs still at root.

**Step 4: Commit**
```bash
git add -A
git commit -m "refactor: move skills under skills/ for plugin packaging

Relocates all in-scope skills into skills/ so a single richmondgeneral
plugin can auto-discover them. Excludes rg-inventory-legacy,
rg-new-item-legacy, archive/. History preserved via git mv.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Plugin manifest

**Files:** Create `.claude-plugin/plugin.json`

**Step 1: Verify absent**
```bash
test -f .claude-plugin/plugin.json && echo EXISTS || echo MISSING   # expect MISSING
```

**Step 2: Create the manifest** (modeled on the working `square-online/.claude-plugin/plugin.json`)
```json
{
  "name": "richmondgeneral",
  "version": "1.0.0",
  "description": "Richmond General's full skill set — Square catalog & storefront ops, item lifecycle (intake, lotting, mark-sold), iMessage/CRM, photo library, image processing, appraisal, and Whatnot tooling. Single source of truth for the Claude desktop app and Cowork.",
  "author": { "name": "Scott Beilfuss" },
  "keywords": ["richmond-general", "square", "inventory", "storefront", "imessage", "photos", "appraisal", "whatnot"]
}
```

**Step 3: Verify it parses**
```bash
jq . .claude-plugin/plugin.json >/dev/null && echo "plugin.json OK"
```
Expected: `plugin.json OK`.

---

### Task 4: Marketplace manifest

**Files:** Create `.claude-plugin/marketplace.json`

**Step 1: Create the manifest** (shape matches `local-desktop-app-uploads/.claude-plugin/marketplace.json`)
```json
{
  "name": "richmondgeneral",
  "version": "1.0.0",
  "description": "Richmond General skills — single-plugin marketplace read by the desktop app and Cowork.",
  "owner": { "name": "Scott Beilfuss" },
  "plugins": [
    { "name": "richmondgeneral", "version": "1.0.0", "source": "." }
  ]
}
```

**Step 2: Verify it parses**
```bash
jq . .claude-plugin/marketplace.json >/dev/null && echo "marketplace.json OK"
```

**Step 3: Validate the plugin shape with the authoritative validator**
- Use the **plugin-dev:plugin-validator** agent (or `claude plugin validate .` if that CLI exists in this environment) against the repo root.
- **If the validator rejects `"source": "."`** (marketplace root doubling as the plugin root): fall back to a dedicated plugin subdir — move `.claude-plugin/plugin.json` + `skills/` under `richmondgeneral/`, and set the marketplace plugin `source` to `"./richmondgeneral"`. Re-validate.

**Step 4: Commit**
```bash
git add .claude-plugin/
git commit -m "feat: add richmondgeneral plugin + marketplace manifests

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Update `build-skill.sh` for the `skills/` layout

**Files:** Modify `docs/build-skill.sh`

**Step 1: Write the check (fails until fixed)**
```bash
bash docs/build-skill.sh photos-library 2>&1 | rg -q 'Created' && echo PASS || echo FAIL
```
Expected now: `FAIL` (it looks for `photos-library/` at repo root, now moved).

**Step 2: Make the edits** — introduce a skills dir and point lookups + packaging at it.
- After `DIST_DIR=...` add: `SKILLS_DIR="${SKILLS_DIR:-$SKILLS_ROOT/skills}"`
- `build_skill()`: change `local skill_dir="$SKILLS_ROOT/$skill_name"` → `local skill_dir="$SKILLS_DIR/$skill_name"`
- The zip step: change `(cd "$SKILLS_ROOT" && zip -r ...)` → `(cd "$SKILLS_DIR" && zip -r ...)` (keeps each `.skill`'s internal layout `<skill>/SKILL.md` unchanged)
- `build_all()`: change the loop `for skill_dir in "$SKILLS_ROOT"/*/` → `for skill_dir in "$SKILLS_DIR"/*/`
- `--help` listing loop: same `"$SKILLS_ROOT"/*/` → `"$SKILLS_DIR"/*/`

**Step 3: Re-run the check — should pass, and the archive layout must be unchanged**
```bash
bash docs/build-skill.sh photos-library 2>&1 | rg 'Created'
unzip -l dist/photos-library-v1.3.skill | rg 'photos-library/SKILL.md'   # internal path unchanged
bash docs/build-skill.sh --all 2>&1 | tail -3
```
Expected: build succeeds; archive still contains `photos-library/SKILL.md` at root; `--all` reports N built.

**Step 4: Commit**
```bash
git add docs/build-skill.sh
git commit -m "build: resolve skills under skills/ in build-skill.sh

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Retire dead sync scripts + document the new flow

**Files:** Delete `docs/sync-to-claude.sh`, `docs/sync-skills.sh`; update `README.md`

**Step 1: Remove the scripts that target the unused `~/.claude/skills` path**
```bash
git rm docs/sync-to-claude.sh docs/sync-skills.sh
```

**Step 2: Add an install/update section to `README.md`** documenting:
- This repo is a local-directory marketplace exposing the `richmondgeneral` plugin.
- One-time: add a directory-type marketplace in the desktop app and Cowork pointing at this clone's `.claude-plugin/marketplace.json`; install `richmondgeneral`.
- Ongoing: edit a skill → commit → `git push`; `git pull` the clone; refresh the marketplace in each surface.

**Step 3: Verify**
```bash
test ! -e docs/sync-to-claude.sh && test ! -e docs/sync-skills.sh && echo "sync scripts removed"
rg -q 'marketplace' README.md && echo "README documents marketplace flow"
```

**Step 4: Commit**
```bash
git add -A
git commit -m "chore: retire ~/.claude/skills sync scripts; document marketplace flow

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Final verification + land

**Step 1: Full sanity pass**
```bash
cd ~/workspace/richmondgeneral/skills
jq . .claude-plugin/marketplace.json .claude-plugin/plugin.json >/dev/null && echo "manifests OK"
find skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l   # expect N
bash docs/build-skill.sh --all 2>&1 | tail -2
git status -sb   # only the unrelated square-crm/scripts/auto_sync.sh should remain dirty
```

**Step 2: Push the branch**
```bash
git push -u origin feat/plugin-marketplace
```

**Step 3: Land** — confirm with the user: open a PR (matches the convention used for big features like rg-full-auto), or fast-forward `main` directly. Then push `main`.

---

## Phase 2 (separate plan, after Phase 1 installs cleanly)

Audit and fix skills that hardcode `~/.claude/skills/...` paths so they run from
the plugin cache (`${CLAUDE_PLUGIN_ROOT}`-relative). Known: `daily-briefing`
(reads `contacts-manager` by absolute path), `imessage-*` / `daily-briefing`
SKILL.md invocation examples, `rg-full-auto` troubleshooting docs. Per-skill
version bump + changelog. Write as `docs/plans/2026-06-17-...-phase2-portability.md`.
