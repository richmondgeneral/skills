# Square Description Formatting Rules

**Square's `description` field is DEPRECATED.** Always use `description_html` instead.

## Supported HTML Tags

`<p>`, `<br>`, `<b>`, `<strong>`, `<i>`, `<em>`, `<u>`, `<ul>`, `<ol>`, `<li>`, `<h1>`-`<h6>`, `<a>`, `<div>`, `<code>`

**NOT supported:** Inline styles, `<style>` tags, CSS classes. No `style="..."` attributes.

## Rules

| Rule | Correct | WRONG |
|------|---------|-------|
| Paragraph spacing | `</p><p>&nbsp;</p><p>` (spacer paragraph) | `<p>` alone (no visible gap on Square) |
| Paragraph breaks | `<p>Paragraph one.</p><p>&nbsp;</p><p>Paragraph two.</p>` | `<br><br>` in `description` field |
| Bold labels | `<b>Condition:</b> Good` | Plain text (no visual hierarchy) |
| Ampersand | `&amp;` (only entity needed) | `&amp;amp;` (double-escaped) |
| Copyright | Unicode `©` directly | `&copy;` entity |
| Em dash | Unicode `—` directly | `&mdash;` entity |
| En dash | Unicode `–` directly | `&ndash;` entity |

## Why `<p>&nbsp;</p>` Spacers

Square Online CSS strips `<p>` margins to zero, so back-to-back `<p>` tags render as line breaks with no visible gap. A `<p>&nbsp;</p>` spacer paragraph forces a visible blank line between sections.

## Template Pattern

```html
<p>Opening paragraph -- what this item is.</p>
<p>&nbsp;</p>
<p>History/provenance paragraph.</p>
<p>&nbsp;</p>
<p>Additional context paragraph.</p>
<p>&nbsp;</p>
<p>Production/technical details. Copyright © Year Holder.</p>
<p>&nbsp;</p>
<p><b>Condition:</b> Grade. Specific notes. Shipping info.</p>
```

## Why Not `description`

When you put `<br>` tags or HTML entities into the plain `description` field, Square wraps everything in `<p>` tags and escapes the HTML, so `<br>` becomes visible as literal text on the website.

**Correct approach:** Use `description_html` with `<p>` tags + `<p>&nbsp;</p>` spacers + Unicode characters. Square auto-generates `description` and `description_plaintext` from `description_html`.
