# Design: `richmondgeneral` skills → single installable plugin

**Date:** 2026-06-17
**Status:** Approved (design phase)
**Author:** scottybe (with Claude)

## Problem

Skills live in the `richmondgeneral/skills` git repo, but the user consumes
skills through the **Claude desktop app** and **Cowork** — not the Claude Code
CLI. Those two surfaces load skills from the shared plugin registry
(`~/.claude/plugins/installed_plugins.json`) via **marketplaces → plugins**.
The repo's existing `sync-to-claude.sh` / `sync-skills.sh` copy skills into
`~/.claude/skills`, a path only the CLI reads — so it is a dead drop for this
setup, and the repo has drifted out of sync with what is actually installed
(only a `square-online` upload bundle reached the app).

Goal: **one source of truth that both the desktop app and Cowork read, where a
change made once propagates to both.**

## Decisions (approved)

1. **Granularity:** one plugin, `richmondgeneral`, bundling all active skills.
   Skills surface namespaced as `richmondgeneral:<skill>`.
2. **Marketplace source mechanism:** **local-directory marketplace** pointing at
   the local repo clone (same pattern as the existing `local-desktop-app-uploads`
   marketplace). The repo is private (`git@github.com:richmondgeneral/skills.git`);
   a local-directory marketplace sidesteps private-repo auth while keeping GitHub
   as the upstream source of truth. GitHub-fetch is the fallback if the repo is
   made public or the app confirms private-auth support.
3. **Phasing:** Phase 1 makes the repo installable as a plugin; Phase 2 audits
   intra-repo hardcoded paths for portability. Ship Phase 1 first.
4. **Scope:** every top-level dir containing `SKILL.md` **except**
   `rg-inventory-legacy`, `rg-new-item-legacy`, and `archive/` (~29 skills).
   Personal trading skills (`alpaca-market-data`, `alpha-trader`) are included
   (harmless); revisit if undesired.

## Target repo layout

```
skills/                              # repo root (git@github.com:richmondgeneral/skills.git)
  .claude-plugin/
    marketplace.json                 # advertises one plugin: richmondgeneral
    plugin.json                      # the richmondgeneral plugin manifest
  skills/                            # NEW: all skills move here (git mv, history preserved)
    photos-library/SKILL.md
    imessage-core/...
    daily-briefing/...
    ...all active skills...
  docs/
    build-skill.sh                   # updated to read skills/
    plans/2026-06-17-...-design.md   # this doc
  README.md
  rg-inventory-legacy/               # left at root, NOT in the plugin (excluded)
  rg-new-item-legacy/                # excluded
  archive/                           # excluded (already skipped by tooling)
```

- `marketplace.json` lists a single plugin whose `source` is the repo root (or a
  subdir), modeled on `local-desktop-app-uploads/.claude-plugin/marketplace.json`.
- `plugin.json` modeled on the working `square-online/.claude-plugin/plugin.json`
  (name, version, description, author).
- Plugin auto-discovers skills under `skills/`.

## Phase 1 — make it installable (this plan)

1. Create `skills/` and `git mv` each in-scope skill dir into it.
2. Author `.claude-plugin/plugin.json` (`name: richmondgeneral`, version, etc.).
3. Author `.claude-plugin/marketplace.json` listing the one plugin.
4. Update `docs/build-skill.sh` to resolve skills under `skills/`.
5. Retire `sync-to-claude.sh` / `sync-skills.sh` (wrong target) — delete or
   replace with a short note pointing to the marketplace flow.
6. Update top-level `README.md` to document the marketplace + install/update flow.
7. Verify: marketplace.json / plugin.json parse; every in-scope skill has a
   discoverable `SKILL.md` under `skills/`; build script still produces packages.
8. Commit (scoped) and push to `main`.

## Phase 2 — path portability (follow-up plan)

Audit skills that assume the `~/.claude/skills/...` layout and convert absolute
references to `${CLAUDE_PLUGIN_ROOT}`-relative resolution so they run correctly
from the plugin cache. Known instances:
- `daily-briefing` reads `~/.claude/skills/contacts-manager/references/contacts.md`
- `imessage-*` and `daily-briefing` SKILL.md docs reference `~/.claude/skills/...`
  and `~/scripts/...` invocation paths
- `rg-full-auto` references `~/.claude/skills` in troubleshooting docs

Each fixed skill gets a version bump + changelog entry.

## Install & update runbook (after Phase 1 ships)

**One-time, per surface (desktop app + Cowork):**
- Add a marketplace of type *directory* pointing at the local clone's
  `.claude-plugin/marketplace.json`, then install the `richmondgeneral` plugin.
- Exact UI affordance to confirm at install time (the app exposes marketplace
  add/refresh for the existing public marketplaces; verify the local-directory
  path is accepted, mirroring how `local-desktop-app-uploads` is registered).

**Ongoing:**
1. Edit a skill in the repo; commit; `git push`.
2. `git pull` the local clone the marketplace points at.
3. Refresh the marketplace in each surface → plugin updates in both.

## Risks & safety

- **Non-destructive until install:** the existing `square-online` plugin and all
  current installs are untouched; nothing changes on either surface until the new
  marketplace is added and the plugin installed.
- **History preserved:** skills move via `git mv`.
- **Private-repo fetch** is the reason for the local-directory choice; revisit if
  going public.
- **Phase 2 portability** is required before relying on cross-skill file reads in
  the installed (non-`~/.claude/skills`) layout.

## Open items to confirm at implementation

- Exact desktop-app / Cowork UI for adding a local-directory marketplace.
- Whether the single-plugin `source` should be repo root (`.`) or a dedicated
  subdir; root is simpler and preferred unless packaging requires isolation.
