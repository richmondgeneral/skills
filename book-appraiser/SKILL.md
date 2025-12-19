---
name: book-appraiser
description: Antiquarian and antique book appraisal, identification, and valuation. Use when the user presents a book that appears to be from before 1970, asks about old/antique/vintage books, needs help identifying publisher/edition/printing, wants to research book value, or asks about Library of Congress holdings or public domain status.
---

# Book Appraiser: Antiquarian & Vintage Books

Specialized appraisal workflow for books, with Library of Congress cross-reference and public domain status checking.

## When to Use This Skill

- Book appears to be pre-1970
- User asks about first editions, rare books, or antiquarian value
- Identifying publisher, edition, or printing
- Researching book value for resale
- Checking if a work is in public domain
- Looking for digital copies via LOC or Internet Archive

## Core Workflow

### Step 1: Initial Assessment

**Gather key identifiers:**
1. Title and author
2. Publisher and location
3. Copyright date / publication date
4. Edition statement ("First Edition", "Third Printing")
5. Physical description (binding, size, illustrations)

**Age indicators:**
| Feature | Typical Era |
|---------|-------------|
| Marbled endpapers | Pre-1900 |
| Gilt edges | Victorian era |
| Sewn binding visible | Pre-1950 |
| Perfect binding (glued) | 1950s+ |
| Dust jacket present | 1920s+ (common 1940s+) |
| ISBN number | 1970+ |
| Bar code | 1980s+ |

### Step 2: Edition Identification

**First edition indicators by publisher:**

| Publisher | First Edition Markers |
|-----------|----------------------|
| **Random House** | "First Edition" on copyright page |
| **Scribner's** | Scribner's seal + "A" on copyright page |
| **Little, Brown** | "First Edition" stated |
| **Harper** | Date on title page matches copyright |
| **Doubleday** | "First Edition" stated |
| **Dover** | Reprint publisher - note original publication |

**Number line guide:**
- `10 9 8 7 6 5 4 3 2 1` → First printing
- `10 9 8 7 6 5 4 3 2` → Second printing
- Lowest number = printing number

**Book club editions (lower value):**
- Blind stamp on back cover
- "Book Club Edition" on flap
- No price on dust jacket
- Smaller/lighter than trade edition

### Step 3: Library of Congress Cross-Reference

**LOC Catalog search:** https://catalog.loc.gov/

**Search strategy:**
1. Search by title + author
2. Note LOC call number (for research visits)
3. Check for digital copy availability
4. Compare publication details to confirm edition

**LOC record provides:**
- Authoritative publication date
- Original publisher information
- Subject headings for categorization
- LCCN (Library of Congress Control Number)

**Digital availability check:**
1. **LOC Digital Collections**: https://www.loc.gov/collections/
2. **Internet Archive**: https://archive.org/
3. **HathiTrust**: https://www.hathitrust.org/
4. **Google Books**: https://books.google.com/

### Step 4: Public Domain Status

**US Public Domain rules (simplified):**

| Publication Date | Status |
|------------------|--------|
| Before 1929 | ✅ Public domain |
| 1929-1963 | ⚠️ Check if copyright renewed |
| 1964-1977 | ❌ Likely protected (95 years from publication) |
| 1978+ | ❌ Protected (life + 70 years) |

**Copyright renewal check:**
- Stanford Copyright Renewal Database: https://exhibits.stanford.edu/copyrightrenewals
- Search by title, author, or registration number
- No renewal found (1929-1963) = public domain

**Why this matters for Richmond General:**
- Public domain books can be reproduced/quoted freely
- Digital copies available for research
- Affects collectibility (reprints less valuable than originals)

### Step 5: Condition Grading

**Standard book grading scale:**

| Grade | Description |
|-------|-------------|
| **Fine (F)** | As new, no defects |
| **Near Fine (NF)** | Almost fine, minor signs of handling |
| **Very Good (VG)** | Shows some wear but intact, no major defects |
| **Good (G)** | Average used copy, all pages present |
| **Fair** | Heavy wear, may have loose pages |
| **Poor** | Reading copy only, significant damage |

**Condition factors:**
- Binding tight or loose?
- Spine intact, faded, or damaged?
- Pages: foxing, tanning, tears, writing?
- Dust jacket: present, torn, price-clipped?
- Odor: musty, smoke, mildew?

**Dust jacket condition (if present):**
- DJ adds significant value to 20th century books
- Price-clipped = reduced value
- Tears, chips, fading all noted separately

### Step 6: Valuation Research

**Primary sources for comparable sales:**

1. **AbeBooks** (https://abebooks.com)
   - Search sold listings when possible
   - Note condition matches

2. **Biblio** (https://biblio.com)
   - Antiquarian specialist marketplace

3. **ViaLibri** (https://vialibri.net)
   - Aggregates multiple book sites

4. **eBay Sold Listings**
   - Filter by "Sold items"
   - Good for common titles

5. **Auction Records**
   - Heritage Auctions (ha.com)
   - Sotheby's, Christie's for high-end

**Valuation factors:**
- First edition vs. later printing (10x+ difference)
- Dust jacket present (2-10x difference)
- Author signature (2-5x or more)
- Association copy (provenance to notable person)
- Condition relative to typical survivors

### Step 7: Integration with RG-Inventory

After appraisal, proceed to `rg-inventory` workflow:

1. **Square Catalog**: Create listing with detailed description
2. **Photography**: Capture title page, copyright page, binding, any defects
3. **Info Card**: Include provenance story, edition details
4. **Pricing**: Based on comparable sales research

**Book-specific SEO title formula:**
`[Date] [Author] [Title] - [Edition/Printing] | [Condition] [Binding Type]`

Example: `1930 Harold Gray Little Orphan Annie - 1979 Dover Reprint | VG Softcover`

## Special Categories

### Children's Books
- Illustration quality matters greatly
- Caldecott/Newbery winners command premiums
- Condition typically worse (handled by children)
- Little Golden Books: pre-1955 more valuable

### Comic Strip Collections
- Original newspaper strip compilations
- Dover reprints (1970s) = affordable entry point
- Cupples & Leon editions (1920s-30s) = more valuable

### Americana
- Local histories
- State/regional publications
- Maps and atlases
- Political ephemera

## Quick Reference: Red Flags

**Signs of lesser value:**
- Book club edition
- Ex-library (stamps, pockets, labels)
- Remainder mark (spray paint on bottom edge)
- Facsimile/reprint without noting as such
- Modern reprint of public domain work

**Signs of potential value:**
- First edition stated
- Limited/numbered edition
- Author signature
- Original dust jacket
- Association copy (inscribed to notable person)
- Illustrated by notable artist
- Pre-1900 publication date

## References

- `references/condition-grading.md` - Detailed grading standards with examples
- `references/publisher-points.md` - Publisher-specific first edition identification
