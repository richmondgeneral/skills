---
name: whatnot-chrome
description: Chrome automation patterns for Whatnot dashboard — inventory navigation, React combobox interaction, CSV import, batch field editing, and page save workflows. Use when automating any Whatnot dashboard action via Claude in Chrome. Triggers on "whatnot edit", "whatnot fields", "fill whatnot", "whatnot automation", "whatnot chrome", "edit whatnot listing". NOT for category/field reference data — use whatnot-catalog for allowed values and field maps.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v1.0 - Initial extraction from rg-full-auto Phase 8:
    - Extracted Chrome automation patterns from rg-full-auto v3.4
    - Documented React combobox interaction workflow
    - Added inventory navigation patterns
    - Added CSV import via DataTransfer API
    - Added batch field-editing workflow
    - Added publish drafts workflow
    - Added page element discovery patterns
---

# Whatnot Chrome Automation

> **Which Whatnot skill?** This one = CSV batch import + edit-page automation. Single-item create
> form → `whatnot-create-product`; field/category reference → `whatnot-catalog`.
> **Idempotency first:** before importing a CSV row / creating a draft, check that SKU's
> `label.json → channels.whatnot` — skip SKUs already registered (blind imports = duplicate
> listings). Deterministic alternative: `apps/seller-agent/publish_item.py --platform whatnot`.

Reusable Chrome automation primitives for Whatnot's dashboard. This skill owns the *how* — how to interact with Whatnot's React UI. For field values and category data, see `whatnot-catalog`.

## Prerequisites

- Claude in Chrome MCP tools must be available
- User must be logged into whatnot.com in the browser
- Tab must be in the MCP tab group (use `tabs_context_mcp` to verify)

## Tab Setup

Always start by getting the current tab context:

1. Call `tabs_context_mcp` to get available tabs
2. If no Whatnot tab exists, call `tabs_create_mcp` then `navigate` to `https://www.whatnot.com/dashboard/inventory`
3. Store the tab ID — all subsequent calls use this ID

**⚠️ Tab IDs change between sessions.** Never cache tab IDs across conversations.

---

## Inventory Navigation

### Inventory List
**URL:** `https://www.whatnot.com/dashboard/inventory`
**Drafts tab:** `https://www.whatnot.com/dashboard/inventory?tab=drafts`

### Item Edit Page
**URL pattern:** `https://www.whatnot.com/dashboard/inventory/TGlzdGluZ05vZGU6XXXXXXXXXX==`

The path segment is a Base64-encoded Whatnot node ID. You get these by clicking items from the inventory list — there's no way to construct them from SKU or title.

### Navigation Pattern (List → Edit → List)

1. Navigate to inventory list URL
2. Scroll to find the target item (use `find` tool with item title)
3. Click the item to open edit page
4. Make edits (see Combobox Interaction below)
5. Click **Save** button
6. After save, Whatnot auto-returns to inventory list OR navigate back manually

---

## React Combobox Interaction

Whatnot uses React comboboxes for dropdown fields (Genre, Type, Edition, Shipping Profile, etc.). These are NOT standard HTML `<select>` elements.

**⚠️ IMPORTANT:** There are TWO different "Type" fields on Whatnot. The CSV column "Type" = listing type (Buy it Now / Auction / Giveaway). The edit page "Type" dropdown = content type (Movie / Mini Series / TV Series). Always check `whatnot-catalog` to know which values are valid for which field.

### The Pattern (with exact tool calls)

**Example: Setting Genre to "Horror" on a DVD edit page (tab ID = 1781225804)**

Step 1: FIND — Locate the combobox by label
  Tool: `find(query: "Genre combobox", tabId: 1781225804)`
  Returns: ref_8054 (a combobox input element)

Step 2: TYPE — Filter the dropdown options
  Tool: `form_input(ref: "ref_8054", tabId: 1781225804, value: "Horror")`
  Effect: Opens the dropdown AND filters to show only "Horror"

Step 3: CLICK — Select the dropdown option
  Option A (preferred): Take a screenshot to see exact coordinates of the dropdown option
    Tool: `computer(action: "screenshot", tabId: 1781225804)`
    Then: `computer(action: "left_click", coordinate: [163, 634], tabId: 1781225804)`
  Option B (when coordinates are tricky): Use find to locate the option
    Tool: `find(query: "Horror option in dropdown list", tabId: 1781225804)`
    Then: `computer(action: "left_click", ref: "ref_8055", tabId: 1781225804)`

Step 4: VERIFY — Confirm selection persisted
  Tool: `computer(action: "screenshot", tabId: 1781225804)`
  Check: The Genre field should now display "Horror" as the selected value

### Complete Single-Item Example (all fields for a DVD)

On a Movies > DVDs edit page, fill all 4 metadata fields:

1. find("Movie/TV Show Title" input) → form_input(ref, "Boogeyman 2")
2. find("Genre combobox") → form_input(ref, "Horror") → screenshot → click "Horror" option
3. find("Type combobox") → form_input(ref, "Movie") → screenshot → click "Movie" option
4. find("Edition combobox") → form_input(ref, "Unrated") → screenshot → click "Unrated Edition" option
5. Scroll down to Shipping Profile if needed → find("Shipping Profile combobox") → verify it shows "4-7 oz"
6. find("Save button") → click Save
7. Wait for "Product Updated" toast confirmation

### Known Quirks

| Quirk | Symptom | Workaround |
|-------|---------|------------|
| Invalid value typed | "No options available" shown | Stop — this value doesn't exist. Check `whatnot-catalog` for valid values |
| Dropdown closes on scroll | Selected value disappears | Re-open by clicking the combobox, re-type filter text |
| Value doesn't persist after save | Field reverts to empty | Must CLICK a dropdown option — typing alone doesn't update React state |
| Multiple comboboxes on page | Wrong dropdown opens | Scroll to target field first, verify ref matches the right field label |
| Free text field (Movie/TV Show Title) | No dropdown appears | This is correct — it's a text input, not a combobox. Just form_input the value |

### Error Handling

| Situation | Action |
|-----------|--------|
| "No options available" in dropdown | Value is invalid. Stop. Read `whatnot-catalog` for valid values. Do NOT save. |
| Combobox ref not found by `find` | Page may not have loaded. Screenshot to verify. Try scrolling down. Retry `find`. |
| Save button click doesn't trigger toast | Screenshot to check for validation errors. A required field may be missing. |
| After save, field reverted to empty | You typed but didn't CLICK a dropdown option. Re-open edit page, redo the field. |
| Session expired (login page shown) | Stop. Tell user to log in again. Then `tabs_context_mcp` to re-acquire tab. |
| Category has TODO in whatnot-catalog | Fields are undocumented for this category. Screenshot the edit page. Ask user what values to use. Document in whatnot-catalog for next time. |

### Anti-Patterns (DO NOT DO)

- **DO NOT** use `javascript_tool` to set `element.value` — React won't pick up the change
- **DO NOT** type a value and press Enter without clicking the dropdown option
- **DO NOT** assume typing "DVD" into a "Type" field will work — always check `whatnot-catalog` for valid values first
- **DO NOT** skip the screenshot verify step — silent failures are the #1 time waster

---

## CSV Import via Chrome

### DataTransfer API Injection

Whatnot's CSV import uses a native file picker. Bypass it with JavaScript:

```javascript
// Build CSV content as a string (header + data rows)
const csvContent = `Category,Sub Category,Title,Description,Quantity,Type,Price,Shipping Profile,Offerable,Hazmat,Condition,Cost Per Item,SKU,Image URL 1,Image URL 2,Image URL 3,Image URL 4,Image URL 5,Image URL 6,Image URL 7,Image URL 8
"Movies","DVDs","Item Title","Description",1,Buy it Now,7,4-7 oz,TRUE,Not Hazmat,Good,1,RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/hero.png,,,,,,,,`;

const blob = new Blob([csvContent], { type: 'text/csv' });
const file = new File([blob], 'whatnot-import.csv', { type: 'text/csv' });
const fileInput = document.querySelector('input[type="file"]');
const dataTransfer = new DataTransfer();
dataTransfer.items.add(file);
fileInput.files = dataTransfer.files;
fileInput.dispatchEvent(new Event('change', { bubbles: true }));
fileInput.dispatchEvent(new Event('input', { bubbles: true }));
```

### Import Flow

1. Navigate to `https://www.whatnot.com/dashboard/inventory`
2. Find the upload/cloud icon:
   - **Preferred:** `find(query: "import CSV button", tabId: TAB_ID)` or `find(query: "upload icon near Create Product", tabId: TAB_ID)`
   - **Fallback:** Screenshot and click approximate coordinate (1122, 110) — this is layout-dependent and may shift
3. Execute the JavaScript above via `javascript_tool`
4. Modal shows "filename.csv — Ready to import" with yellow **Import** button
5. Click **Import** → server-side validation runs
6. On success: "Your products have successfully imported" with "View Drafts" link
7. Items import as **Drafts** — verify at `?tab=drafts`

### Validation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "Subcategory not provided" | Category requires a sub-category | Check `whatnot-catalog` hierarchy |
| "Subcategory X is not part of Category Y" | Wrong parent/child pairing | Check `whatnot-catalog` hierarchy |
| "Price must be a positive integer" | Decimal price like `6.50` | Use `ceil(price)` |
| No file input found on page | Whatnot changed their import UI | Screenshot → find the new upload element → adapt selector |
| DataTransfer injection fails silently | File input selector changed | Screenshot the modal → inspect for `input[type="file"]` → update selector |

### Manual Fallback

If Chrome automation fails entirely:
1. Save the CSV content to a local file
2. Tell user: "Please upload `whatnot-import.csv` manually through the Whatnot dashboard → Inventory → Import"
3. Continue to metadata editing after user confirms import

---

## Batch Field Editing Pattern

When multiple items need the same field set (e.g., Type = "Movie" on 5 DVDs):

### Fast Single-Field Pass

For setting ONE field across N items:

```
For each item in inventory list:
  1. Click item → opens edit page
  2. Scroll down ~7 ticks to reach the field area
  3. Click the target combobox (use known coordinates if field position is consistent)
  4. Click the option value
  5. Click Save
  6. Auto-return to inventory list → repeat
```

**Estimated time:** ~30 seconds per item for a single field.

### Full Metadata Pass

For setting ALL category-specific fields on each item:

```
For each item in inventory list:
  1. Click item → opens edit page
  2. Scroll down to metadata section
  3. For each field (use whatnot-catalog to know which fields + valid values):
     a. find combobox → form_input filter → click option
  4. Verify Shipping Profile matches whatnot-catalog weight heuristic
  5. Click Save
  6. Return to inventory list → repeat
```

**Estimated time:** ~2 minutes per item for 4-5 fields.

---

## Publish Drafts Pass

After metadata is filled, drafts need to be published:

1. Navigate to `?tab=drafts`
2. For each draft item:
   a. Click item
   b. Find and click "Publish" or toggle from Draft to Live
   c. Confirm if prompted
   d. Return to drafts list

---

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `whatnot-catalog` | Provides valid values for fields this skill fills |
| `rg-full-auto` | Phase 8 delegates to this skill for Chrome ops |
| `rg-item-update` | May call this for Whatnot-side edits to existing items |
