# RG Full Auto v3.2 Remediation Plan

Date: 2026-02-15  
Scope: `rg-full-auto` v3.2 and directly related skills/docs

## Issues Tracked

1. Reporting category rule was ambiguous after moving to type + tier categories.
Status: Completed
Files: `rg-full-auto/references/square-catalog.md`

2. `rg-lot-tracker` was missing required metadata fields (`version`, `author`, `updated`).
Status: Completed
Files: `rg-lot-tracker/SKILL.md`

3. `rg-full-auto` v3.2 changelog did not reflect category/channel changes included in this version.
Status: Completed
Files: `rg-full-auto/SKILL.md`

4. `rg-item-update` v1.3 changelog did not include the category model update.
Status: Completed
Files: `rg-item-update/SKILL.md`

5. `skill-manager` active snapshot had stale versions for `rg-full-auto` and `rg-item-update`, and no version for `rg-lot-tracker`.
Status: Completed
Files: `skill-manager/SKILL.md`

## Implementation Notes

- Kept channel mapping explicit by phase:
  - Phase 2: Square category IDs
  - Phase 7: GitHub Pages slug filters
  - Phase 8: Whatnot CSV labels
- No behavior changes to Whatnot/GitHub phase gating beyond documentation clarity.

## Validation

- Frontmatter still present and valid in edited skill files.
- Script syntax checks already passing for related script/tooling changes:
  - `python -m py_compile rg-item-update/scripts/safe_batch_reprice.py`
  - `bash -n docs/sync-to-claude.sh`
