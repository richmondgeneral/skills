# RG-Full-Auto Operational Findings (Archived)

**Last updated:** 2026-02-15

This file is retained as a short archival note. The prior long-form findings were based on older runs and older API/tool assumptions, and are now superseded by the current skill workflow.

## Current Operational Baseline

- Catalog creation: Phase 2 uses Square `catalog.batchInsertObjects` with `catalog.upsertCatalogObject` fallback.
- Inventory: Phase 3 uses Square `inventory.batchChange`.
- Image upload: Phase 4 uses `square-image-upload` skill flow.
- Lot/cost/margin logic: delegated to `rg-lot-tracker` (Step 1.1 and Step 1.5).
- Item page publishing: Phase 7 uses the flip-card template and gallery insertion flow.

## Still-Relevant Runtime Constraints

- Binary operations must run on the user's Mac via `osascript`; text file writes can use Filesystem tools.
- Path case mismatches can occur with Filesystem-returned paths; use absolute canonical Mac paths in shell commands.
- Inventory requests still require `quantity` as a string and must not include write-only fields.

## Source of Truth

- Workflow instructions: `rg-full-auto/SKILL.md`
- API/category reference: `rg-full-auto/references/square-catalog.md`
- Path conventions: `rg-full-auto/references/system-paths.md`
- Lot/cost/margin policies: `rg-lot-tracker/SKILL.md` and its references

## Notes

If a new operational incident is discovered, add a dated section with:

1. Reproduction context
2. Confirmed root cause
3. Mitigation/rollback path
4. Permanent fix status
