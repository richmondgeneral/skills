---
name: brand-guidelines
description: Apply Richmond General's brand identity (colors, typography, component patterns) to anything that needs to look on-brand  -  Square Online storefront snippets, marketing emails, social images, print materials, new web pages. Triggers when the user mentions "brand", "make this on-brand", "Richmond General style", "apply our colors", "match the website", or asks for visual treatment that should align with the storefront and item cards. Loads the full brand spec from BRAND.md and provides ready-to-paste CSS variables and font links.
---

# Richmond General brand guidelines

## When to use this skill

Anytime a deliverable needs Richmond General's visual identity. Examples:

- "Make this email/page on-brand"
- "Apply our colors to this snippet"
- "What's our gold hex?"
- "Restyle this category page"
- "Build a brand-consistent marketing card"

This skill is the source-of-truth wrapper around `BRAND.md` in the `brand/` sibling repo (workspace root: `brand/BRAND.md`). Use it before applying any visual treatment so the result matches both the [Square Online storefront](https://www.richmondgeneral.com) AND the [GitHub Pages item cards](https://richmondgeneral.github.io/items/)  -  those two surfaces must always look like the same brand.

## The brand at a glance

### Colors

```css
:root {
  --rg-gold:       #C9A961;   /* Primary accent, CTAs, top borders */
  --rg-gold-light: #D4B978;   /* Gold hover state */
  --rg-cream:      #F5F1E8;   /* Page background */
  --rg-cream-dark: #E8E2D5;   /* Secondary surfaces */
  --rg-charcoal:   #2C2C2C;   /* Primary text, dark surfaces */
  --rg-brown:      #6B4423;   /* Era/secondary text */
  --rg-shadow:     rgba(44, 44, 44, 0.12);
}
```

### Fonts (Google Fonts)

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Source+Sans+Pro:wght@300;400;600&display=swap" rel="stylesheet">
```

- **Headings, prices, item titles**: Playfair Display (serif)
- **Body, labels, buttons, navigation**: Source Sans Pro (sans-serif)

### Quick CSS starter for any new surface

```css
body {
  font-family: 'Source Sans Pro', sans-serif;
  background: var(--rg-cream);
  color: var(--rg-charcoal);
  line-height: 1.6;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Playfair Display', serif;
  color: var(--rg-charcoal);
  font-weight: 500;
}

a {
  color: var(--rg-charcoal);
  text-decoration: none;
  border-bottom: 1px solid var(--rg-gold);
  transition: color 0.2s, border-color 0.2s;
}
a:hover {
  color: var(--rg-gold);
}

.button, button.cta, .shop-button {
  background: var(--rg-gold);
  color: white;
  border: none;
  padding: 0.6rem 1.25rem;
  border-radius: 4px;
  font-family: 'Source Sans Pro', sans-serif;
  font-weight: 600;
  letter-spacing: 0.3px;
  cursor: pointer;
  transition: background 0.2s;
}
.button:hover {
  background: var(--rg-gold-light);
}

.card {
  background: white;
  border-top: 3px solid var(--rg-gold);
  border-radius: 12px;
  box-shadow: 0 8px 25px var(--rg-shadow);
}
```

## Workflow

1. **Always read `brand/BRAND.md` first** if the sibling `brand/` repo is mounted in the workspace  -  it may have local tweaks beyond what's documented in this skill.
2. **Confirm the surface** you're applying brand to (Square Online snippet, email, print, social, new web page).
3. **For Square Online**: brand application happens through the Snippets API. Use the existing `storefront-hero-tiles` skill's structure and inject the brand variables.
4. **For other surfaces**: paste the CSS variables + Google Fonts link into a `<style>` block, then write component CSS using `var(--rg-*)` references.
5. **Verify against item cards**: open `https://richmondgeneral.github.io/items/RG-0001/` (or any item URL) and visually compare  -  the result should feel like the same brand.

## Component recipes

Common pieces you'll be asked to build. Use these as starting points.

### Header (top nav bar)

```css
.rg-header {
  background: var(--rg-charcoal);
  color: white;
  padding: 1rem 2rem;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 10px var(--rg-shadow);
  font-family: 'Source Sans Pro', sans-serif;
}
.rg-header .logo {
  font-family: 'Playfair Display', serif;
  font-size: 1.5rem;
  font-weight: 600;
  color: white;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.rg-header .logo-icon {
  width: 32px;
  height: 32px;
  background: var(--rg-gold);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1rem;
}
```

### Hero band (dark gradient with gold accent text)

```css
.rg-hero {
  background: linear-gradient(135deg, var(--rg-charcoal) 0%, #3D3D3D 100%);
  color: white;
  padding: 4rem 2rem;
  text-align: center;
}
.rg-hero h1 {
  font-family: 'Playfair Display', serif;
  font-size: 2.5rem;
  font-weight: 500;
  letter-spacing: 0.5px;
  margin-bottom: 1rem;
}
.rg-hero p {
  font-size: 1.1rem;
  opacity: 0.9;
  font-weight: 300;
  max-width: 600px;
  margin: 0 auto 1.5rem;
}
.rg-hero .accent {
  color: var(--rg-gold);
}
```

### Item card front face

```css
.rg-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 60px var(--rg-shadow), 0 8px 25px var(--rg-shadow);
  aspect-ratio: 5/7;
  display: flex;
  flex-direction: column;
}
.rg-card .image-area {
  flex: 1;
  background: var(--rg-cream);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}
.rg-card .info-area {
  padding: 1.25rem 1.5rem;
  border-top: 3px solid var(--rg-gold);
}
.rg-card .item-title {
  font-family: 'Playfair Display', serif;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--rg-charcoal);
  line-height: 1.3;
}
.rg-card .item-era {
  font-size: 0.85rem;
  color: var(--rg-brown);
}
.rg-card .item-price {
  font-family: 'Playfair Display', serif;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--rg-charcoal);
}
.rg-card .sku-badge {
  background: var(--rg-charcoal);
  color: white;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.3rem 0.6rem;
  border-radius: 4px;
  letter-spacing: 0.5px;
}
```

## What to avoid

- **Off-brand color substitutions.** Don't approximate the cream (no `#FAF6ED` or `#FFF5E1`  -  use the exact `#F5F1E8`).
- **Substitute fonts.** Don't fall back to Georgia for headings or system-ui for body. Always link Playfair Display + Source Sans Pro.
- **Bright accent colors.** No teals, reds, or saturated blues. The gold IS our color accent. Charcoal + cream + gold + brown is the entire palette.
- **Gradients beyond the hero band.** The dark hero gradient is the only gradient in the system. Everything else is solid fill.
- **Drop shadows beyond the specified opacity.** `rgba(44,44,44,0.12)` is the canonical shadow color. Higher opacity feels heavy.

## Square Online specifics

The Square Online storefront has known places where the platform's defaults will override your brand unless you target them explicitly. These should be in every snippet that applies the brand:

```css
/* Square defaults body to white + Inter  -  override */
body { background: var(--rg-cream) !important; }

/* Square sets --primary-color to #000000  -  override the title-weight vars */
:root {
  --title-font-weight: 500 !important;
  --section-title-font-weight: 500 !important;
}

/* Square's Add to Cart button (class .cart-button) is rgb(0,0,0) by default */
.cart-button, button.cart-button {
  background: var(--rg-gold) !important;
  color: #fff !important;
  border: none !important;
  font-family: 'Source Sans Pro', sans-serif !important;
  font-weight: 600 !important;
  transition: background 0.2s ease !important;
}
.cart-button:hover {
  background: var(--rg-gold-light) !important;
}

/* Product titles + prices already in the right font but force charcoal */
.w-product-title, [class*="product-title"] {
  font-family: 'Playfair Display', serif !important;
  color: var(--rg-charcoal) !important;
}
.w-product-price, [class*="product-price"] {
  font-family: 'Playfair Display', serif !important;
  color: var(--rg-charcoal) !important;
  font-weight: 600 !important;
}

/* Cart slideout "back to cart" link */
.cko__back-btn {
  font-family: 'Source Sans Pro', sans-serif !important;
  color: var(--rg-charcoal) !important;
}
```

## Related skills

- `brand-voice`  -  for writing copy in the curated mercantile voice
- `storefront-hero-tiles`  -  applies this brand to the Square Online storefront via Snippets API
