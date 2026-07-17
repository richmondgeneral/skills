# eBay React combobox interaction

Seller Hub CREATE/REVISE uses React comboboxes for several fields. These are **not** native
`<select>` elements. Typing alone often does not commit React state — you must open the list and
**click an option** (or "Add custom value").

Last updated: 2026-07-16.

---

## General pattern (native Chrome or computer-use)

1. **Screenshot** so the field is settled and coordinates are real.
2. **Find** the combobox by visible label (e.g. "Shipping policy", "Brand", "Color", "Country of Origin").
3. **Click** the control to open (coordinate-click if ref-click fails).
4. **Type** a filter string into the open search/filter box when present.
5. **Screenshot** the option list.
6. **Click** the exact option row (or **"Add custom value: + …"** for free-text brands).
7. **Verify** the closed combobox displays the chosen label — not empty, not a previous value.

### Anti-patterns

- Do **not** set `element.value` via raw JS only — React state often ignores it.
- Do **not** press Enter without confirming the option was selected.
- Do **not** assume the CREATE default shipping policy is correct (it is usually **last-used**).

---

## Shipping policy (CREATE)

| | |
|---|---|
| Control | React combobox next to **Shipping policy** (PRICING / shipping section) |
| Observed options | Local Pickup Only · Local Pickup + Calculated Ship + International · Standard Small Item · Default Shipping (names vary by account) |
| Default | Last-used policy — **verify every CREATE** |
| Pickup-only goods | Select **Local Pickup Only** unless the item should ship |
| After select | Package weight/dims inputs may appear for calculated-ship policies (lbs / oz / L×W×H) — fill only when shipping |

## Brand (item specifics)

1. Open Brand combobox.
2. Type maker name (e.g. `Kreamer`, `Weiss`).
3. If no catalog match: click **Add custom value: + &lt;name&gt;**.
4. Reject eBay.ai suggestions like "Unbranded" when wrong.

## Color / Country of Origin

Same open → type filter → click option. Country often **United States**.

## Yes/No chips (Antique, Vintage, …)

These are chips/toggles, not comboboxes — click the correct Yes/No. Prefer individual review over
"Apply all" on the Suggested item specifics card.

---

## Playwright sketch (fallback)

```python
# Conceptual — prefer helpers in apps/seller-agent/ebay_ui.py
await page.get_by_text("Shipping policy", exact=False).click()
await page.keyboard.type("Local Pickup Only")
await page.get_by_role("option", name=re.compile("Local Pickup Only", re.I)).click()
# read back visible value near the label
```

Always follow with a visual or DOM read-back of the selected policy name before **List it**.
