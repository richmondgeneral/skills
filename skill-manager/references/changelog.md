# Skills Changelog

Tracking changes to all skills in `~/skills/`.

---

## rg-inventory

### 2025-11-27 (v2)
#### Changed
- Replaced rigid shipping decision tree with judgment-based guidance
- Removed price threshold ($100) from shipping criteria - price doesn't determine shippability
- Clarified: furniture = pickup/local, easily boxable items = ship regardless of price
- Philosophy: don't make rules/filters for things that require actual judgment

### 2025-11-27
#### Changed
- `track_inventory` changed from `false` to `true` in Phase 3 catalog creation
- Added **Phase 3b: Set Inventory Count** section with `inventory.batchChange` API
- Updated Square API Services section to mark inventory as REQUIRED
- Updated `references/square-catalog.md` with same inventory changes

#### Fixed
- Items no longer show as "sold out" in Square Online after creation

---

## skill-manager

### 2025-11-27
#### Added
- Initial creation of skill-manager meta-skill
- Active skills registry
- Workflow documentation for updating skills
- Changelog format specification

---

## vintage-appraiser

(No changes tracked yet)

---

## book-appraiser

(No changes tracked yet)

---

## product-labeler

(No changes tracked yet)

---

## imessage-assistant

(No changes tracked yet)
