---
name: whatnot-create-product
description: |
  Create and fill out product listings on Whatnot.com via Chrome browser automation.
  Use this skill whenever the user wants to list items on Whatnot, add products to their
  Whatnot inventory, create Whatnot listings, or sell items on Whatnot. Also trigger when
  the user mentions "Whatnot", "list on Whatnot", "sell on Whatnot", "Whatnot inventory",
  or "add to Whatnot". This skill knows every dropdown value, form field, and category
  available on the Whatnot product creation page and can fill forms programmatically.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-16"
compatibility:
  - Claude in Chrome (browser automation tools)
  - read_page, form_input, find, get_page_text, navigate, javascript_tool
---

# Whatnot Product Listing Skill

> **Which Whatnot skill?** This one = the single-item create form. NOT for CSV batch import /
> edit-page automation (→ `whatnot-chrome`) or field/category reference (→ `whatnot-catalog`).
> **Idempotency first:** check `label.json → channels.whatnot` before creating — if already
> registered, update the existing product instead. Record the new product id/url back into
> `channels.whatnot` after a create. Deterministic alternative:
> `apps/seller-agent/publish_item.py --platform whatnot` (review-by-default).

## Overview

This skill automates the creation of product listings on Whatnot's Seller Hub. Whatnot
uses React-controlled form components, so understanding the DOM structure and the right
interaction patterns is critical for reliable automation.

## Before You Start

Read the full dropdown reference data before filling any fields:

```
Read references/dropdown-values.md
```

This contains every category, sub-field, and option available on the Whatnot product
creation form. You'll need it to match field values correctly.

## Workflow

### Step 1: Navigate to Create Product

```
navigate to https://www.whatnot.com/dashboard/inventory/new
```

Wait 2 seconds for the page to load, then verify you're on the right page by checking
the tab title contains "Draft Product" or reading the page text.

### Step 2: Read the Form Structure

Use `read_page` with the form region to understand the current field layout. The form
fields change dynamically based on which **category** is selected — book categories
show Author/Publisher/Genre fields, VHS shows different fields, etc.

```
read_page (filter: interactive)  → identify all form fields and their ref IDs
```

### Step 3: Gather Product Details from User

Ask the user for:
- What item they're listing (photos, description, any details)
- Desired price
- Condition
- Any other details they want to specify

Use web search to research the item for pricing guidance and accurate descriptions
if the user hasn't provided those details.

### Step 4: Select Category

**Category selection is the most important step** because it determines which
additional fields appear on the form.

The category field is a combobox. The approach:

1. First check if the desired category appears in "Recent Categories" buttons
2. If so, try clicking that button via `left_click` on the ref
3. If clicks fail (extension overlay issue), use `form_input` on the Category
   combobox (ref for `combobox "Category *"`) and type the category name
4. Verify the hidden field next to the combobox got populated (it stores a base64-encoded ID)

### Step 5: Fill Text Fields

Use `form_input` to set values. These fields reliably accept text input:

| Field | Type | Notes |
|-------|------|-------|
| Title * | text | Descriptive, keyword-rich for SEO |
| Description * | textarea | Detailed, include condition, provenance, features |
| Quantity * | number | Usually 1 for unique items |
| Price (USD) * | currency | Set as number like "10.00", renders as "$10" |
| Cost Per Item | currency | Optional, private to seller |
| SKU | text | Optional, private to seller |

### Step 6: Fill Dropdown/Combobox Fields

This is where it gets tricky. Whatnot uses custom React comboboxes for dropdowns.
Each combobox has a **visible input** (what the user sees) and a **hidden input**
(what gets submitted).

**The `form_input` tool sets the visible text but may not trigger React's state update.**
This means the hidden value may remain empty even though text appears in the field.

**Strategy for comboboxes:**

1. **Try `form_input` first** — set the visible combobox text to match an option exactly
2. **Check if the hidden field got populated** — read the hidden textbox ref next to the combobox
3. **If hidden field is empty**, the selection didn't register. Options:
   a. Try `left_click` on the matching option ref from the dropdown dialog
   b. Try `javascript_tool` to dispatch input events
   c. Tell the user which fields need manual confirmation (click the dropdown, select the value)

**Important:** The dropdown dialogs exist in the DOM even when not visible. You can
read their option values at any time using `read_page` on the dialog ref.

### Step 7: Category-Specific Fields

After selecting a category, new fields appear. For "Rare & Vintage Books":

| Field | Type | Options Reference |
|-------|------|-------------------|
| Topic | combobox | See dropdown-values.md |
| Condition | combobox | Brand New, Like New, Very Good, Good, Fair, Poor |
| Binding | combobox | Softcover, Hardcover, Leather, Fine Binding |
| Publication Period | combobox | 2010-Present, 2000-2009, 1950-1999, 1900-1949, 1800-1899, 1700-1799, Pre-1700 |
| Author | combobox | Extensive list, see dropdown-values.md |
| Publisher | combobox | Extensive list, see dropdown-values.md |
| Genre | combobox | Biography, Childrens, Classics, Cookbook, Fantasy, etc. |
| Group | combobox | Fiction, Non-fiction |
| Features | combobox | 1st Edition, Signed, Illustrated, Dust Jacket, etc. |

Other categories will have different fields. Always `read_page` after setting the
category to discover what fields appeared.

### Step 8: Set Shipping & Hazmat

| Field | Default | Options |
|-------|---------|---------|
| Shipping Profile * | Usually pre-set | Weight-based options (see dropdown-values.md) |
| Hazardous Materials * | NOT_HAZMAT | No Hazardous Materials, Contains Hazardous Materials, Contains Lithium Batteries |

### Step 9: Set Pricing Format

The form defaults to "Buy It Now". If the user wants Auction format, click the
"Auction" button in the Format section.

Optional toggles:
- **Flash Sale** — enables flash sale pricing
- **Accept Offers** — allows buyers to make offers
- **Reserve for Live** — only purchasable during a live show

### Step 10: Verify and Save

Before publishing:

1. Read back the form state using `get_page_text` or `read_page` to confirm all fields
2. Check that required fields are filled: Category, Title, Description, Quantity, Price, Shipping Profile
3. Check hidden field values for comboboxes to ensure selections registered

Then either:
- **Save Draft** — saves without publishing (button ref for "Save Draft")
- **Publish** — makes listing live (button ref for "Publish", type="submit")

Always confirm with the user before clicking Publish.

## SEO Tips for Listings

When writing titles and descriptions, maximize searchability:

- **Title**: Include year, brand/maker, condition keywords, key identifying details
  - Example: `Atlanta Cooks for Company (1968) - Junior Associates of the Atlanta Music Club - Vintage Cookbook`
- **Description**: Include all relevant keywords naturally: vintage, rare, collectible,
  the specific category, condition details, dimensions, provenance, notable features
- **Fill ALL optional fields**: Every filled field improves discoverability in Whatnot's
  search and filtering. Even if a field seems minor, fill it.

## Troubleshooting

### "Cannot access a chrome-extension:// URL" Error

This means another Chrome extension has a popup or overlay in focus. Solutions:
- Ask user to close any extension popups
- Ask user to click on the Whatnot tab to bring it to focus
- `form_input` and `read_page` often still work even when `screenshot` and `left_click` fail

### Combobox Values Not Sticking

If `form_input` sets the visible text but the hidden value stays empty:
- The React component needs an actual DOM event (click, keydown) to update state
- Try `javascript_tool` to dispatch events on the input element
- As a fallback, tell the user exactly which dropdowns to confirm manually

### Category Not Loading Sub-Fields

After setting a category, if the category-specific fields don't appear:
- The category selection may not have registered with React
- Try clicking the category from "Recent Categories" buttons if available
- Navigate away and back to `/dashboard/inventory/new` to reset
