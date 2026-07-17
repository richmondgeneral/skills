---
name: catalog-classifier
description: Determines Square category assignment based on item attributes. Use when onboarding items, bulk categorization, or when unsure which category an item belongs to. Routes items to the correct type category (Books & Paper, Furniture, Collectibles, Pottery & Ceramics, etc. — reporting category = type) plus the market tier (New Arrivals default on intake; The Vintage Market / The Real Rarities / The General Store as re-tiers); TVM/Food brands handled as explicit exceptions. Triggers on "what category", "classify", "which category", "categorize item".
metadata:
  version: "2.2"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v2.2 - Tier model corrected: New Arrivals = default intake tier (New Finds/Real Rarities = re-tier
    destinations); type category is ALWAYS primary + reporting; square-catalog-ops delegation removed
    (skill deleted 2026-06-20).

    v2.1 - food taxonomy consolidation:
    - Replaced legacy snack split categories with `Food & Pantry`
    - Marked old snack categories as legacy-hidden (do not assign)
    - Added delegation note to `square-catalog-ops` for cleanup verification

    v2.0 - Category refactor:
    - Replaced 2-category RG system (Real Rarities/New Finds) with type-based categories
    - Added: Books & Paper, Furniture, Pottery & Ceramics, Collectibles, Art & Craft Kits
    - Real Rarities and New Finds are now tier (secondary) categories
    - Removed deleted categories: TBDL (TBDLabz Exclusive, TBDL Picks), Mind & Clarity, Energy & Elements, Space & Atmosphere, Faire
    - Added Wellness & Apothecary (absorbed R&L brand products)
    - Updated classification flow diagram
---

# Catalog Classifier

Assigns Square categories based on item attributes. Returns category ID(s) with reasoning.

## Category Reference

### Brand-Level Categories

| Brand | Signal Words | Location |
|-------|--------------|----------|
| **TVM** (Trésor Vintage Market) | French, Paris, 🇫🇷, European vintage | — |
| **RG** (Richmond General) | Vintage, antique, collectible, estate | B87BAEZ0NWV34 |
| **General Store Food** | Food, candy, chips, drinks, imported | — |

### TVM Categories (🇫🇷 branding)

| Category | ID | Use For |
|----------|-----|---------|
| 🇫🇷 Timeless Treasures | `3N3II4W6Q7AA43RWQGEEWELY` | Rare French/European vintage |
| 🇫🇷 Classic Beauty | `FRBSRJRTP5Q5UQXPHK5JB666` | Vintage beauty, fashion, accessories |
| 🇫🇷 Expressly TVM | `JSL7MTE6Y2QRXTV2VCASRF2R` | TVM exclusives, digital art |
| 🇫🇷 Whimsical Gifts | `RXMZRCGB2XUBRSB4FQYZE464` | Giftable vintage items |

### RG Type Categories (pick ONE as primary)

| Category | ID | Criteria |
|----------|-----|----------|
| **Books & Paper** | `CLZCJ62H4TTHDQ3ZBYMZQASQ` | Books, magazines, paper ephemera, cookbooks |
| **Furniture** | `W3EYAJJPTNC46WSLNYI4WH7V` | Stools, trunks, tables, chairs, shelving |
| **Pottery & Ceramics** | `APSTFSN4UXQI44HBFSDTSEX7` | Mugs, vases, plaques, figurines, Hummel |
| **Collectibles** | `YQWBSOJDENMXDGUUQ3TGI3HF` | Games, toys, dolls, ornaments, vintage misc |
| **Art & Craft Kits** | `F4JQYK4Z5MEBV5VFCDYHIAWT` | Watercolor kits, craft supplies, DIY art |
| **Wellness & Apothecary** | `I5PMPWGTVR7IDBL4RUJWN3A4` | Teas, serums, tinctures, natural products, R&L brand |
| **The Apothecary Cabinet** | `QIPW32HGKMU5BDPU3A7YZCM4` | Sage bundles, ritual items, candles, display |
| **Gifts** | `AR3ZTA45KU4BH23AJ7LOLLRA` | Home decor, giftable items |
| **Analog & Vintage Media** | `N35REXL33FZWJNJV24IUQGPN` | Vinyl, pinball, film, analog tech |

### RG Tier Categories (secondary overlay)

| Category | ID | Criteria |
|----------|-----|----------|
| **New Arrivals** | `TGWDFETSQPR6BF67YJCTOLW6` | **Default intake tier** — every new item lands here; re-tier later as it ages |
| **The Real Rarities** | `FL4L42RRUE5UXMWFDLXOCNB5` | Truly rare/showcase-worthy — re-tier destination |
| **The New Finds** | `P34KX3L7XRZJJ5RP6W35K4YO` | Re-tier destination (NO LONGER the intake default) |
| **The Vintage Market** | `TX6SBQLJDMZOCVXBUD3KT3CL` | Room category — auto-attached when the type lives under it (Furniture, Collectibles, Analog & Vintage Media) |

### Food Category

| Category | ID | Products |
|----------|-----|----------|
| Food & Pantry | `CYTCL6ES7TSG2XCUVHIDG5B2` | Snacks, candy, drinks, imported foods |

Legacy categories (do not assign; kept hidden for history): `Chips & Crisps`, `Cookies & Sweets`, `Drinks`, `Asian Imports`.

### Wellness Categories (subset of RG Type)

| Category | ID | Use For |
|----------|-----|---------|
| Wellness & Apothecary | `I5PMPWGTVR7IDBL4RUJWN3A4` | Teas, serums, natural products, R&L brand |
| The Apothecary Cabinet | `QIPW32HGKMU5BDPU3A7YZCM4` | Sage bundles, ritual items, candles, display |

## Classification Flow

```
Item Input
    │
    ├─► Is it food/snack? ──────► Food & Pantry
    │
    ├─► French/Paris/🇫🇷? ──────► TVM Categories
    │                              └─ Apply TVM tier logic
    │
    ├─► Wellness/Spiritual? ────► Wellness & Apothecary OR The Apothecary Cabinet
    │                              ├─ Teas, serums, natural products → Wellness & Apothecary
    │                              └─ Sage, ritual, candles → The Apothecary Cabinet
    │
    └─► General Vintage/Antique? → RG Type Categories
                                    │
                                    ├─► Book/magazine/paper? → Books & Paper
                                    ├─► Furniture/trunk? → Furniture
                                    ├─► Pottery/ceramic/figurine? → Pottery & Ceramics
                                    ├─► Game/toy/doll/misc? → Collectibles
                                    ├─► Craft kit/art supplies? → Art & Craft Kits
                                    ├─► Home decor/gift? → Gifts
                                    └─► Vinyl/pinball/analog? → Analog & Vintage Media

                                    THEN add tier as secondary:
                                    └─► + New Arrivals (default intake tier — ALWAYS on intake;
                                        re-tier later to The Real Rarities / The New Finds as it ages)
```

## Tier Assignment (Secondary Category)

**New Arrivals** — the DEFAULT intake tier. Every new RG-typed item gets it as secondary on intake (TVM/Food follow their own routing),
no judgment required. Items age out of it via re-tiering.

**The Real Rarities** — a RE-TIER destination (may be applied at intake for obvious showcase
pieces) when ANY of:
- Pre-1950 with identified maker/manufacturer
- Documented provenance (estate, auction record)
- Significant collectible value ($75+)
- Rare pattern, limited edition, or unusual variant
- Museum-quality condition
- Carnival glass with identified pattern/maker
- Antiquarian books (pre-1900)

**The New Finds** — a re-tier destination only (NO LONGER the intake default; the old
"every item gets New Finds" rule matched zero live items and is retired).

## Multi-Category Assignment

Some items may warrant multiple categories:

| Scenario | Categories |
|----------|------------|
| Japanese candy | Food & Pantry |
| French crystal | 🇫🇷 Timeless Treasures (primary) |
| Vintage radio | Analog & Vintage Media + New Arrivals (re-tier to Real Rarities if rare) |

**Rule:** When multi-assigning, the more specific category is primary.

## Output Format

When classifying, return:

```
Square Primary Category: Books & Paper
Square Primary ID: CLZCJ62H4TTHDQ3ZBYMZQASQ
Square Secondary Category: New Arrivals (default intake tier)
Square Secondary ID: TGWDFETSQPR6BF67YJCTOLW6
Square Reporting Category ID: CLZCJ62H4TTHDQ3ZBYMZQASQ
Confidence: High
Reasoning: Item is a catalog/book-format publication; standard intake tier applies.
```

## Usage by Other Skills

This skill is called by:
- `rg-full-auto` - Phase 1 category assignment
- `rg-item-update` - Category changes
- `product-labeler` - Batch categorization

After bulk category changes, verify against live Square (source of truth) and re-sync
`catalog_state.json` via the reconcile tool.
