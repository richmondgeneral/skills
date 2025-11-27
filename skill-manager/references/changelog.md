# Skills Changelog

Tracking changes to all skills in `~/skills/`.

---

## rg-inventory

### 2025-11-27 (v4)
#### Changed
- Both label layouts now 2"×1" (was 2"×1" default + 2"×2" QR)
- QR layout: drops Condition Notes, shortens Product Name to ~20 chars
- Added ASCII art label diagrams to skill and reference
- Updated Print Master settings with font sizes

### 2025-11-27 (v3)
#### Restored
- Phase 6 now includes full label format specs (was just "use product-labeler skill")
- CSV format with columns: Product Name, Attributes, Price, Condition, Condition Notes, SKU, QR Code URL
- QR code decision guidance
- Attributes format and condition abbreviations

#### Changed
- QR code now links to info card URL (not payment link) - customer reads story first, then clicks Buy
- Updated `references/label-format.md` to match

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
