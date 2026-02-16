---
name: whatnot-catalog
description: Whatnot catalog reference data — category hierarchy, category-specific metadata fields, allowed dropdown values, shipping profile heuristics, and CSV column mapping. Use when building Whatnot CSV rows, filling metadata fields, or looking up valid values for any Whatnot dropdown. Triggers on "whatnot category", "whatnot fields", "shipping profile", "whatnot allowed values", "whatnot CSV", "what category on whatnot". NOT for Chrome automation — use whatnot-chrome for browser interaction.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v1.0 - Initial extraction from rg-full-auto Phase 8:
    - Extracted category hierarchy, allowed values, and shipping heuristics
    - Added Movies > DVDs category-specific metadata fields
    - Documented CSV column mapping with field sources
    - Added Type field disambiguation (CSV listing type vs edit page content type)
---

# Whatnot Catalog Reference

Reference data for Whatnot listings — categories, metadata fields, allowed values, and shipping heuristics. This is a **data-only** skill with no Chrome automation. For browser interaction, see `whatnot-chrome`.

## CSV Import Columns

**Exact header names (must match Whatnot template):**

```
Category,Sub Category,Title,Description,Quantity,Type,Price,Shipping Profile,Offerable,Hazmat,Condition,Cost Per Item,SKU,Image URL 1,Image URL 2,Image URL 3,Image URL 4,Image URL 5,Image URL 6,Image URL 7,Image URL 8
```

### CSV-Level Allowed Values

**Condition:**
`Brand New`, `Like New`, `Very Good`, `Good`, `Fair`, `Poor`

**Type (listing type — NOT content type):**
`Auction`, `Buy it Now`, `Giveaway`

**Shipping Profile (must match dropdown exactly):**
`1-3 oz`, `4-7 oz`, `8-11 oz`, `12-15 oz`, `1 lb`, `1-2 lbs`

**Hazmat:**
`Not Hazmat`

### Price Conversion Rule

Square prices use cents (e.g., `650` = $6.50). Whatnot requires **positive whole-dollar integers**.

**Formula:** `ceil(square_price_cents / 100)`

| Square Price (cents) | Whatnot Price |
|---------------------|---------------|
| 650 | 7 |
| 1050 | 11 |
| 4000 | 40 |
| 1999 | 20 |

---

## Category Hierarchy

**⚠️ CRITICAL:** Some items that seem like categories are actually sub-categories. Always verify parent/child relationships.

### Common Richmond General Mappings

| Item Type | Category (parent) | Sub Category | Notes |
|-----------|-------------------|--------------|-------|
| DVDs | `Movies` | `DVDs` | NOT `DVDs` as top-level! |
| VHS tapes | `Movies` | `VHS` | |
| Blu-ray | `Movies` | `Blu-ray` | |
| Movie memorabilia | `Movies` | `Movie Memorabilia` | |
| Rare/vintage books | `Rare & Vintage Books` | _(empty)_ | Top-level, no sub required |
| Vintage toys | `Vintage Toys` | _(varies)_ | Check Values tab |
| Vinyl records | `Vinyl Records` | _(varies)_ | |
| Art | `Art` | _(varies)_ | |

**Full category/sub-category list:** See Values tab (columns E & F) of the [Whatnot CSV template](https://docs.google.com/spreadsheets/d/1UNxbyQoXjpjuqYcCE_Ie94OTCEB7lXR7Yz84aynILW4/edit#gid=0)

---

## Category-Specific Metadata Fields

These fields appear on the Whatnot **edit page** after CSV import. They CANNOT be set via CSV — they must be filled via Chrome automation (see `whatnot-chrome` skill).

**⚠️ TWO DIFFERENT "TYPE" FIELDS:**

| Field | Where | Values | Meaning |
|-------|-------|--------|---------|
| CSV "Type" column | CSV import | `Buy it Now`, `Auction`, `Giveaway` | Listing format |
| Edit page "Type" dropdown | Edit page only | Varies by category (see below) | Content classification |

These are completely unrelated. The CSV "Type" sets the listing format. The edit page "Type" classifies the content.

---

### Movies > DVDs

| Field | Required | Type | Valid Values | Notes |
|-------|----------|------|-------------|-------|
| Movie/TV Show Title | Yes | Free text | _(any)_ | Use actual film title, not listing title |
| Genre | Yes | Combobox | `Action`, `Comedy`, `Drama`, `Horror`, `Sci-Fi`, `Thriller`, `Romance`, `Documentary`, `Animation`, `Family`, `Western`, `Musical`, `Mystery`, `Adventure`, `Fantasy`, `War`, `Crime` | Typeahead filtering |
| Type (content) | Yes | Combobox | `Movie`, `Mini Series`, `TV Series` | NOT the CSV "Type" |
| Edition | No | Combobox | `Standard Edition`, `Collector's Edition`, `Unrated Edition`, `Special Edition`, `Director's Cut`, `Widescreen Edition`, `Limited Edition`, `Anniversary Edition` | Typeahead filtering |

### Movies > VHS

> **TODO:** Document after first VHS batch onboarding. Expected to share most fields with DVDs.

### Movies > Blu-ray

> **TODO:** Document after first Blu-ray batch. Likely identical to DVDs.

### Vinyl Records

> **TODO:** Document after first vinyl batch. Expected fields: Artist, Album Title, Genre, Speed (33/45/78), Format (LP/EP/Single).

### Rare & Vintage Books

> **TODO:** Document after first book batch. Expected fields: Author, Title, Year, Publisher, Condition Notes.

### Vintage Toys

> **TODO:** Document after first toy batch.

---

## Shipping Profile Weight Heuristic

Use this table to select the correct Shipping Profile value during CSV generation or post-import correction.

### By Item Type

| Item Type | Weight Estimate | Shipping Profile |
|-----------|----------------|-----------------|
| Single DVD (standard case) | ~4-5 oz | `4-7 oz` |
| DVD multi-pack (2-4 discs) | ~5-6 oz | `4-7 oz` |
| DVD box set (5-8 discs) | ~6-7 oz | `4-7 oz` |
| DVD large box set (9+ discs) | ~8-10 oz | `8-11 oz` |
| Single Blu-ray | ~4-5 oz | `4-7 oz` |
| VHS tape (single) | ~8-10 oz | `8-11 oz` |
| Paperback book (under 300 pages) | ~4-7 oz | `4-7 oz` |
| Hardcover book (small) | ~8-12 oz | `8-11 oz` |
| Hardcover book (large/coffee table) | ~1-2 lbs | `1-2 lbs` |
| Vinyl record (single LP in sleeve) | ~8-10 oz | `8-11 oz` |
| Vinyl record (gatefold/double LP) | ~12-14 oz | `12-15 oz` |
| Small collectible / figurine | ~4-6 oz | `4-7 oz` |
| VHS box set (2-3 tapes) | ~14-16 oz | `1 lb` |
| Board game (standard) | ~1-2 lbs | `1-2 lbs` |

### Quick Lookup by Weight

| Actual Weight | Shipping Profile |
|--------------|-----------------|
| Under 3 oz | `1-3 oz` |
| 4-7 oz | `4-7 oz` |
| 8-11 oz | `8-11 oz` |
| 12-15 oz | `12-15 oz` |
| ~1 lb (16 oz) | `1 lb` |
| Over 1 lb | `1-2 lbs` |

> When in doubt, weigh the item. Underestimating loses money on shipping; overestimating deters buyers.

---

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `whatnot-chrome` | Uses this skill's values when filling fields via Chrome |
| `rg-full-auto` | Phase 8 uses this for CSV generation and field reference |
| `catalog-classifier` | Square-side classification; this skill handles Whatnot-side |
| `rg-item-update` | May reference this when updating Whatnot listings |
