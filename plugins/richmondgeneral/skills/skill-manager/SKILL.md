---
name: skill-manager
description: Maintain the richmondgeneral plugin-marketplace repo — version bumps, metadata audits, frontmatter validation, plugin-update rollouts, and cleanup across skills. Use for "bump the plugin version", "audit skill metadata", "roll out a skill change", "why isn't my skill update loading", "validate the skills repo". For creating or rewriting skill CONTENT, use the plugin-dev/writing-skills guidance first; this skill is repo hygiene + release mechanics.
metadata:
  version: "2.0"
  author: scottybe
  updated: "2026-07-15"
  changelog: |
    v2.0 - Rewritten for the plugin-marketplace era: update flow = plugin.json version bump +
    `claude plugin marketplace update` / `claude plugin update` (rsync = break-glass only);
    static registry snapshot dropped (drift magnet — generate live instead); packaging demoted
    to legacy; dead .system/skill-creator + deleted square-catalog-ops references removed.

    v1.7 - Full registry refresh (25-skill static snapshot — REMOVED in v2.0).
    v1.5 - Aligned with Anthropic skill-creator conventions.
---

# Skill Manager

Repo maintenance + release mechanics for the **plugin marketplace repo**
`~/workspace/richmondgeneral/skills` (named "skills" for historical reasons — it IS a Claude
plugin marketplace: `.claude-plugin/marketplace.json` at the root defines marketplace
`richmondgeneral` with two locally-sourced plugins).

## Layout (source of truth)

```
skills/                                  <- marketplace repo
├── .claude-plugin/marketplace.json      <- marketplace manifest (local ./plugins/... sources only)
├── docs/                                <- repo-level templates/helpers (NOT shipped in plugins)
└── plugins/
    ├── richmondgeneral/                 <- core ops plugin
    │   ├── .claude-plugin/plugin.json   <- THE version that gates reinstalls
    │   ├── commands/  skills/  pyproject.toml
    └── square-online/                   <- storefront plugin
        └── .claude-plugin/plugin.json
```

## The Update Loop (how a skill change ships)

1. Edit the skill under `plugins/<plugin>/skills/<skill>/`.
2. **Bump the plugin `version` in `plugins/<plugin>/.claude-plugin/plugin.json`** — no bump =
   no reinstall, this is the #1 "why isn't my change loading" cause.
3. Validate before pushing (js-yaml is stricter than pyyaml — unquoted
   `argument-hint: [a] [b]` or a description containing `": "` silently loads as EMPTY metadata):
   ```bash
   claude plugin validate .            # from the repo root — validates marketplace + plugins
   ```
4. Commit (explicit paths, multi-writer git rules per CLAUDE.md) and push.
5. Roll out per machine:
   ```bash
   claude plugin marketplace update richmondgeneral
   claude plugin update richmondgeneral@richmondgeneral   # and/or square-online@richmondgeneral
   ```
   Cache lands at `~/.claude/plugins/cache/richmondgeneral/<plugin>/<version>/` and matches the
   repo exactly. New cache dir needs its venv: `uv sync --project <cache>/<version>`. Restart
   sessions to load it; delete superseded version dirs once nothing holds them (`lsof +D`).
6. Cowork picks up changes separately: refresh the plugin in the desktop plugin manager.

**Bans / fallbacks:** standalone Cowork side-loads of plugin skills are banned (duplicate
resolution). `rsync` into the cache is break-glass ONLY (CLI broken) — and if you must, sync
only the files you changed (a broad `rsync -a` reverts parallel sessions' newer fixes).

## Required Skill Contract

Each active skill directory must have:
1. `SKILL.md` with YAML frontmatter
2. `name` and `description` fields in frontmatter (description = triggers + "do NOT use for")
3. `metadata.version`, `metadata.author`, `metadata.updated`
4. `metadata.changelog` when changes are substantive

Preferred structure: `references/` (progressive disclosure), `scripts/` (deterministic logic),
`assets/` (reusable outputs).

⚠️ **Gotcha:** the repo `.gitignore` has a `*key*` credentials guard — any skill file matching
`*key*` (e.g. `keyboard-shortcuts.md`) needs `git add -f` or it is silently dropped.

## Metadata Audit (generate live — no static snapshot)

The old static registry table drifted immediately; generate the snapshot when needed:

```bash
REPO=~/workspace/richmondgeneral/skills
for d in $REPO/plugins/*/skills/*; do
  [ -f "$d/SKILL.md" ] || continue
  ver=$(awk '/^metadata:/{m=1} m && /version:/{gsub(/"/,"",$2); print $2; exit}' "$d/SKILL.md")
  upd=$(awk '/^metadata:/{m=1} m && /updated:/{gsub(/"/,"",$2); print $2; exit}' "$d/SKILL.md")
  echo "$(basename $(dirname $(dirname $d)))/$(basename $d)|${ver:-?}|${upd:-?}"
done | sort
```

Find missing required frontmatter fields:

```bash
rg -L "^name:|^description:|^metadata:" $REPO/plugins/*/skills/*/SKILL.md
```

Plugin versions (the ones that matter for rollout):

```bash
grep -H '"version"' $REPO/plugins/*/.claude-plugin/plugin.json
```

## Maintenance Workflow

1. Generate the live metadata snapshot; diff against expectations.
2. Patch target skills (frontmatter, stale paths, outdated claims).
3. Validate scripts when changed (`python3 -m py_compile`, or the skill's tests via
   `uv run --project plugins/richmondgeneral --with pytest python -m pytest <skill>/tests/`).
4. `claude plugin validate .` before every push.
5. Bump the plugin version once per batch; commit explicit paths only.
6. Roll out (update loop above) and verify the cache matches the repo.

## Templates / legacy packaging

- Skill template: `<repo>/docs/reference/SKILL_TEMPLATE.md` (repo root — NOT inside the plugin,
  so `${CLAUDE_PLUGIN_ROOT}` paths won't reach it from an installed cache).
- `.skill` zip packaging (`<repo>/docs/build-skill.sh`) is LEGACY: side-loads are banned, so
  packages are only for sharing a skill outside this marketplace. Don't package for deployment.

## Safety Rules

- Do not delete archived skills unless explicitly asked.
- Do not rewrite unrelated skills in bulk just for style.
- Prefer targeted, reversible changes and keep diffs small.
- Multiple parallel sessions share this checkout — fetch first, stage explicit paths,
  never `git add -A`, use a throwaway worktree for co-edited files.
