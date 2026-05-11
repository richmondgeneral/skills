# rg-full-auto Changelog

## v3.6 - Catalog governance delegation
- Added delegation to `square-catalog-ops` for compliance and cleanup audits
- Added post-write category integrity audit in Step 4.1
- Added `square-webhook-monitor` as operational monitoring companion

## v3.5 - Phase 8 refactor: extract Whatnot skills
- BREAKING: Phase 8 refactored from ~210 inline lines to ~70-line thin orchestrator
- Extracted Chrome automation patterns to `whatnot-chrome` skill (v1.0)
- Extracted catalog reference data to `whatnot-catalog` skill (v1.0)
- Phase 8 now delegates to both skills instead of inlining all Whatnot knowledge
- Added Step 8.4: Publish Drafts (previously undocumented)
- CSV append command stays here (RG-specific file path)

## v3.4 - Phase 8.3: Post-import metadata editing & shipping profile fix
- BREAKING: Fixed Shipping Profile values — old values (0-1 oz, 1-4 oz, etc.) were wrong
- Correct values: 1-3 oz, 4-7 oz, 8-11 oz, 12-15 oz, 1 lb, 1-2 lbs
- Added Phase 8.3: Post-Import Metadata Editing (Chrome Automation)
- Documents category-specific fields (Movie/TV Show Title, Genre, Type, Edition) for Movies > DVDs
- Clarifies two "Type" fields: CSV listing type vs. edit page content type
- Added React combobox interaction patterns and known quirks
- Added Shipping Profile weight heuristic table (DVDs, VHS, books, vinyl, collectibles)
- Updated CSV example and append command to use 4-7 oz default

## v3.3 - Whatnot Phase 8 overhaul (post DVD batch learnings)
- BREAKING: Category hierarchy fix — DVDs is Sub Category under Movies, not a Category
- BREAKING: Prices must be positive integers (no decimals) — added ceil() conversion rule
- Added Chrome automation upload process with DataTransfer API JavaScript injection
- Added category hierarchy reference table (Movies>DVDs, Movies>VHS, etc.)
- Added validation error troubleshooting table
- Added Whatnot price conversion rule (Square cents → Whatnot whole dollars)
- Cost Per Item must also be integer

## v3.2 - Fix Square description HTML formatting
- BREAKING: Switched from deprecated `description` field to `description_html`
- Use `<p>` tags for paragraphs instead of `<br>` tags in plain text
- Use Unicode characters (©, –, —) instead of HTML entities (&copy;, &ndash;, &mdash;)
- Added "Description Formatting Rules" reference table in Phase 2
- Updated Square category model to type + tier assignments with `reporting_category` guidance
- Added per-phase channel classification rules (Square IDs vs GitHub slugs vs Whatnot labels)
- Prevents double-escaping that rendered raw `<br>` and `&amp;` on richmondgeneral.com

## v3.1 - square-cache reconciliation after writes
- Added Step 4.1 to sync square-cache after Phase 2/3/4 write operations
- Added post-sync verification for exact SKU + cached image linkage
- Added fallback sync command via square-cache wrapper script

## v3.0 - Photos library cleanup phase + sold-state flow
- Added Phase 9: Photos Library Archive — organizes source photos into per-item albums under "Richmond General Archive" folder in Photos.app
- Two archive modes: direct UUID (from cluster discovery) and reverse-lookup (filename-to-UUID for Desktop/Downloads imports)
- New scripts: archive_photos.py (Python wrapper), archive_to_album.scpt (AppleScript)
- Now a 10-phase workflow (Phases 0-9)

## v2.9 - Whatnot workflow metadata alignment
- Updated skill description to reflect 9-phase workflow
- Added Whatnot CSV listing to top-level capability summary
- Bumped metadata version to match current Phase 8 coverage

## v2.8 - Square Phase 2 connector compatibility hardening
- Added method fallback path (`batchInsertObjects` -> `upsertCatalogObject`)
- Clarified `idempotency_key` must remain top-level for both payloads
- Added resilient ID extraction using `id_mappings` before object traversal

## v2.7 - Background removal quality hardening
- Phase 0.7 now requests premium remove.bg path (`--model removebg --quality premium`)
- Aligns onboarding workflow with improved image-processor model preference handling

## v2.6 - Photos Library auto-cluster intake
- Added Step 0.4 to discover product photo clusters via photos-library
- Added UUID-based photo copy flow for the selected cluster
- Added manual fallback path when clustering is unavailable

## v2.5 - Lot tracking delegation refinement
- Moved margin validation before catalog write (Step 1.5)
- Delegated lot assignment/cost allocation to rg-lot-tracker
- Removed lot/pricing references moved to rg-lot-tracker

## v2.4 - Review & consistency fixes
- Fixed SKU verification: replaced broken searchItems text_filter with cache-based exact match
- Updated occurred_at guidance to use dynamic ISO timestamp (not hardcoded)
- Fixed phase count references (8-phase, not 7)
- Cross-file path consistency fixes

## v2.3 - Anthropic skills update
- Enhanced triggers: "list item", "sell this"
- Aligned with Anthropic Agent Skills best practices

## v2.2 - Post RG-0014 improvements
- Added Step 1.0: View image for appraisal using copy_file_user_to_claude
- Emphasized exact Square MCP method names (batchInsertObjects, batchChange)
- Gallery index update now uses osascript/sed exclusively (Filesystem:str_replace unreliable)
- Added reminder to check ~/Desktop for images

## v2.1 - Template enforcement
- Created references/info-card-template.html with complete flip card template
- Phase 7.1 now REQUIRES flip card template with explicit checklist
- Added placeholder reference table for template variables
- Added explicit "DO NOT" list to prevent wrong template usage

## v2.0 - Post RG-0013 improvements
- Added 20MB file size check before remove.bg (Phase 0.5)
- Strengthened book-appraiser routing for pre-1970 books (Phase 1)
- Added explicit inventory API example without catalog_object_type (Phase 3)
- Documented path case sensitivity issue with Filesystem tools (Phase 7)
- Added cleanup step for temp files (Phase 7.5)
- Added remove.bg credit monitoring
