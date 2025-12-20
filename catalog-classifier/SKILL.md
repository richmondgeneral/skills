---
name: catalog-classifier
description: Determines Square category assignment based on item attributes. Use when onboarding items, bulk categorization, or when unsure which category an item belongs to. Routes items to correct brand (TVM/RG/TBDL/Snacks), premium tier (Real Rarities vs New Finds), and product type categories. Triggers on "what category", "classify", "which category", "categorize item".
---

# Catalog Classifier

Assigns Square categories based on item attributes. Returns category ID(s) with reasoning.

## Category Reference

### Brand-Level Categories

| Brand | Signal Words | Location |
|-------|--------------|----------|
| **TVM** (Trésor Vintage Market) | French, Paris, 🇫🇷, European vintage | — |
| **RG** (Richmond General) | Vintage, antique, collectible, estate | B87BAEZ0NWV34 |
| **TBDL** | Electronics, digital art, tech | — |
| **Snacks** | Food, candy, chips, drinks, imported | — |

### TVM Categories (🇫🇷 branding)

| Category | ID | Use For |
|----------|-----|---------|
| 🇫🇷 Timeless Treasures | `3N3II4W6Q7AA43RWQGEEWELY` | Rare French/European vintage |
| 🇫🇷 Classic Beauty | `FRBSRJRTP5Q5UQXPHK5JB666` | Vintage beauty, fashion, accessories |
| 🇫🇷 Expressly TVM | `JSL7MTE6Y2QRXTV2VCASRF2R` | TVM exclusives, digital art |
| 🇫🇷 Whimsical Gifts | `RXMZRCGB2XUBRSB4FQYZE464` | Giftable vintage items |

### RG Categories (Richmond General)

| Category | ID | Criteria |
|----------|-----|----------|
| **The Real Rarities** | `FL4L42RRUE5UXMWFDLXOCNB5` | Pre-1950, identified maker, documented provenance, showcase-worthy |
| **The New Finds** | `P34KX3L7XRZJJ5RP6W35K4YO` | Standard vintage, common collectibles, quick-flip |

### TBDL Categories

| Category | ID | Use For |
|----------|-----|---------|
| TBDLabz Exclusive | `P66XV6FKW5NP3GL6NJXZ5KFB` | Tech, electronics, digital |
| TBDL Picks | `EHF6OEAAFUPJD72EMJOVPFPM` | Curated tech selections |

### Snack Categories

| Category | ID | Products |
|----------|-----|----------|
| Chips & Crisps | `RZDJCH4X2C725QEU2AQCX2Y6` | Potato chips, rice crackers, savory |
| Cookies & Sweets | `E23E2FWMORU4VLHRVTDMNWKB` | Biscuits, candy, chocolate |
| Drinks | `Z4CC7D2BNM5YLEQZXL6VA7I2` | Beverages, tea, juice |
| Asian Imports | `3NDGJCHLWBB3D7XKRJLYGCPF` | Japanese/Korean/Chinese snacks |

### Wellness Categories

| Category | ID | Use For |
|----------|-----|---------|
| Mind & Clarity | `AQLDKQIDVXESEW4PKHFMNOY4` | Focus, cognitive wellness |
| Energy & Elements | `Q7YSWW72AIB2MZFCGRHCNBHX` | Crystals, candles, spiritual |
| Space & Atmosphere | `ZWSRBQBBUFBRNSP7HY6QPRRV` | Smudge, diffusers, decor |
| The Apothecary Cabinet | `6E7UZYZFNZBGFRJFH272RVBE` | Herbs, tinctures, remedies |

### Utility Categories

| Category | ID | Use For |
|----------|-----|---------|
| Analog | `N35REXL33FZWJNJV24IUQGPN` | Vinyl, film, analog tech |
| Faire | `KGM2TY6LF4W4RPUI43D5P6CW` | Wholesale/Faire items |

## Classification Flow

```
Item Input
    │
    ├─► Is it food/snack? ──────► Snack Categories
    │                              ├─ Sweet → Cookies & Sweets
    │                              ├─ Savory → Chips & Crisps
    │                              ├─ Beverage → Drinks
    │                              └─ Asian packaging → Asian Imports
    │
    ├─► French/Paris/🇫🇷? ──────► TVM Categories
    │                              └─ Apply TVM tier logic
    │
    ├─► Tech/Digital/Electronics? → TBDL Categories
    │
    ├─► Wellness/Spiritual? ────► Wellness Categories
    │
    └─► General Vintage/Antique? → RG Categories
                                    │
                                    ├─► Pre-1950 + Maker + Provenance?
                                    │   → The Real Rarities
                                    │
                                    └─► Standard vintage/collectible?
                                        → The New Finds
```

## Real Rarities Criteria

Assign to **The Real Rarities** when ANY of:
- Pre-1950 with identified maker/manufacturer
- Documented provenance (estate, auction record)
- Significant collectible value ($75+)
- Rare pattern, limited edition, or unusual variant
- Museum-quality condition
- Carnival glass with identified pattern/maker
- Antiquarian books (pre-1900)

Assign to **The New Finds** when:
- Post-1950 common vintage
- Unknown maker, generic manufacturer
- Standard collectibles without special provenance
- Quick-flip items ($1-25 range)
- Good but not exceptional condition

## Multi-Category Assignment

Some items may warrant multiple categories:

| Scenario | Categories |
|----------|------------|
| Japanese candy | Asian Imports + Cookies & Sweets |
| French crystal | 🇫🇷 Timeless Treasures (primary) |
| Vintage radio | Analog + The New Finds (or Real Rarities if rare) |

**Rule:** When multi-assigning, the more specific category is primary.

## Output Format

When classifying, return:

```
Category: The Real Rarities
ID: FL4L42RRUE5UXMWFDLXOCNB5
Confidence: High
Reasoning: Pre-1920 Northwood carnival glass, identified maker mark, documented pattern (Grape & Cable), excellent condition
```

## Usage by Other Skills

This skill is called by:
- `rg-full-auto` - Phase 1 category assignment
- `rg-item-update` - Category changes
- `product-labeler` - Batch categorization
