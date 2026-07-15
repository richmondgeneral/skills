> ⚠️ **Version note (2026-07-15):** the JS scaffolding below is the **v0.2.x single-route**
> implementation (regex `on()` match for `/s/shop` only). The live snippet is **v0.3.0
> multi-route** — a `route()` function returning `{tiles, title, sub, key}` per matched route,
> with a `data-rg-route` idempotency attribute and a `body.rg-hero-active` toggle (see the
> v0.3.0 section of SKILL.md). When building or editing the hero, START from the LIVE snippet
> (`snippets.list` on the site, or `brand/storefront/richmondgeneral-shop-snippet.html`) — use
> this file for the per-variant tile CSS/markup only, not the route scaffolding.

# Hero Tile Variant Templates

These are the exact CSS + JS templates for each of the four design variants. The skill builds the final snippet content by selecting the appropriate template and substituting:

- `{TILES_JSON}`  -  the JS array of tile objects `[{n, t, u, i}]`
- `{TITLE}`  -  hero title (default `"Welcome to {Shop Name}"`)
- `{SUBTITLE}`  -  hero subtitle (default `"Pick a room of the store to explore"`)
- `{OVERLAY_ALPHA}`  -  overlay opacity (variant B only, default `0.78`)
- `{BG_COLOR}`  -  hero background color (default `#faf6ed`)
- `{FONT_FAMILY}`  -  tile font (default `Georgia, 'Times New Roman', serif`)

## Common JS scaffolding (all variants)

```js
(function(){
  var T = {TILES_JSON};
  function on(){return /^\/s\/shop\/?$/.test(location.pathname);}
  function build(){
    if(document.getElementById('rg-hero'))return true;
    if(!on())return false;
    var m = document.querySelector('main');
    if(!m)return false;
    var h = document.createElement('section');
    h.id = 'rg-hero';
    var x = '<h2>{TITLE}</h2><p>{SUBTITLE}</p><div id="rg-tiles">';
    for(var i=0;i<T.length;i++){
      var c = T[i];
      // Variant-specific tile HTML goes here
    }
    x += '</div>';
    h.innerHTML = x;
    m.insertBefore(h, m.firstChild);
    return true;
  }
  var lp = location.pathname;
  function w(){
    if(location.pathname !== lp){
      lp = location.pathname;
      var h = document.getElementById('rg-hero');
      if(h && !on()) h.remove();
      setTimeout(build, 400);
      setTimeout(build, 1200);
    }
  }
  function init(){
    build();
    setTimeout(build, 600);
    setTimeout(build, 1500);
    setTimeout(build, 3000);
    setInterval(w, 400);
  }
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
```

## Variant A  -  Text only

### CSS

```css
#rg-hero{padding:40px 20px 32px;background:{BG_COLOR};border-bottom:1px solid #e5dcc6;text-align:center;font-family:{FONT_FAMILY}}
#rg-hero h2{margin:0 0 8px;font-size:34px;font-weight:400;color:#2a2520}
#rg-hero p{margin:0 0 28px;color:#857357;font-size:14px;font-style:italic}
#rg-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;max-width:1100px;margin:0 auto}
#rg-tiles a{display:flex;flex-direction:column;align-items:center;justify-content:center;aspect-ratio:5/4;background:#fff;border:1px solid #d9cdb1;color:#2a2520;text-decoration:none;text-align:center;padding:18px;transition:all .25s ease}
#rg-tiles a span.rg-n{font-size:18px;display:block}
#rg-tiles a small.rg-t{display:block;font-size:11px;font-style:italic;opacity:.65;margin-top:8px;text-transform:uppercase}
#rg-tiles a:hover{background:#2a2520;color:{BG_COLOR};border-color:#2a2520;transform:translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,.12)}
@media(max-width:600px){#rg-tiles{grid-template-columns:repeat(2,1fr)}#rg-tiles a{aspect-ratio:1/1}}
```

### Tile HTML

```js
x += '<a href="'+c.u+'"><span class="rg-n">'+c.n+'</span><small class="rg-t">'+c.t+'</small></a>';
```

## Variant B  -  Subtle background image with cream overlay

### CSS

```css
#rg-hero{padding:40px 20px 32px;background:{BG_COLOR};border-bottom:1px solid #e5dcc6;text-align:center;font-family:{FONT_FAMILY}}
#rg-hero h2{margin:0 0 8px;font-size:34px;font-weight:400;color:#2a2520}
#rg-hero p{margin:0 0 28px;color:#857357;font-size:14px;font-style:italic}
#rg-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;max-width:1100px;margin:0 auto;padding:0 8px}
#rg-tiles a{position:relative;overflow:hidden;display:flex;flex-direction:column;align-items:center;justify-content:center;aspect-ratio:5/4;background:#fff;background-size:cover;background-position:center;border:1px solid #d9cdb1;color:#2a2520;text-decoration:none;text-align:center;padding:18px;transition:all .25s ease}
#rg-tiles a::before{content:'';position:absolute;inset:0;background:rgba(250,246,237,{OVERLAY_ALPHA});transition:background .25s ease;z-index:1}
#rg-tiles a span.rg-n,#rg-tiles a small.rg-t{position:relative;z-index:2}
#rg-tiles a span.rg-n{font-size:18px;line-height:1.3;display:block}
#rg-tiles a small.rg-t{display:block;font-size:11px;font-style:italic;opacity:.65;margin-top:8px;text-transform:uppercase}
#rg-tiles a:hover{color:{BG_COLOR};border-color:#2a2520;transform:translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,.18)}
#rg-tiles a:hover::before{background:rgba(42,37,32,0.85)}
@media(max-width:600px){#rg-tiles{grid-template-columns:repeat(2,1fr)}#rg-tiles a{aspect-ratio:1/1}}
```

### Tile HTML

```js
x += '<a href="'+c.u+'" style="background-image:url(\''+c.i+'\')"><span class="rg-n">'+c.n+'</span><small class="rg-t">'+c.t+'</small></a>';
```

Recommended overlay alpha values:
- `0.88`  -  whisper (image barely visible)
- `0.78`  -  soft (default)
- `0.60`  -  bold (image dominates)

## Variant C  -  Dark gradient with white text bottom-aligned

### CSS

```css
#rg-hero{padding:40px 20px 32px;background:{BG_COLOR};border-bottom:1px solid #e5dcc6;text-align:center;font-family:{FONT_FAMILY}}
#rg-hero h2{margin:0 0 8px;font-size:34px;font-weight:400;color:#2a2520}
#rg-hero p{margin:0 0 28px;color:#857357;font-size:14px;font-style:italic}
#rg-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;max-width:1100px;margin:0 auto;padding:0 8px}
#rg-tiles a{position:relative;overflow:hidden;display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-end;aspect-ratio:5/4;background-size:cover;background-position:center;border:1px solid rgba(0,0,0,0.1);color:#fff;text-decoration:none;text-align:left;padding:20px;transition:all .25s ease}
#rg-tiles a::before{content:'';position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,0.65) 0%,rgba(0,0,0,0.25) 60%,rgba(0,0,0,0.1) 100%);transition:background .25s ease;z-index:1}
#rg-tiles a span.rg-n,#rg-tiles a small.rg-t{position:relative;z-index:2;color:#fff}
#rg-tiles a span.rg-n{font-size:20px;line-height:1.2;display:block;font-weight:400}
#rg-tiles a small.rg-t{display:block;font-size:11px;font-style:italic;opacity:.85;margin-top:6px;text-transform:uppercase;letter-spacing:0.5px}
#rg-tiles a:hover{transform:translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,.25)}
#rg-tiles a:hover::before{background:linear-gradient(to top,rgba(0,0,0,0.8) 0%,rgba(0,0,0,0.4) 60%,rgba(0,0,0,0.2) 100%)}
@media(max-width:600px){#rg-tiles{grid-template-columns:repeat(2,1fr)}#rg-tiles a{aspect-ratio:1/1}}
```

### Tile HTML

Same as variant B.

## Variant D  -  Side image + text panel (5:3 aspect)

### CSS

```css
#rg-hero{padding:40px 20px 32px;background:{BG_COLOR};border-bottom:1px solid #e5dcc6;text-align:center;font-family:{FONT_FAMILY}}
#rg-hero h2{margin:0 0 8px;font-size:34px;font-weight:400;color:#2a2520}
#rg-hero p{margin:0 0 28px;color:#857357;font-size:14px;font-style:italic}
#rg-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;max-width:1100px;margin:0 auto;padding:0 8px}
#rg-tiles a{display:flex;flex-direction:row;align-items:stretch;aspect-ratio:5/3;background:#fff;border:1px solid #d9cdb1;color:#2a2520;text-decoration:none;overflow:hidden;transition:all .25s ease}
#rg-tiles a .rg-img{flex:0 0 38%;background-size:cover;background-position:center}
#rg-tiles a .rg-text{flex:1;display:flex;flex-direction:column;justify-content:center;padding:14px 18px;text-align:left}
#rg-tiles a span.rg-n{font-size:17px;line-height:1.2;display:block}
#rg-tiles a small.rg-t{display:block;font-size:10px;font-style:italic;opacity:.65;margin-top:8px;text-transform:uppercase;letter-spacing:0.5px}
#rg-tiles a:hover{background:#2a2520;color:{BG_COLOR};border-color:#2a2520;transform:translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,.15)}
@media(max-width:600px){#rg-tiles{grid-template-columns:1fr}}
```

### Tile HTML

```js
x += '<a href="'+c.u+'"><div class="rg-img" style="background-image:url(\''+c.i+'\')"></div><div class="rg-text"><span class="rg-n">'+c.n+'</span><small class="rg-t">'+c.t+'</small></div></a>';
```

## Subcategory tile overrides (v0.2.1)

This CSS block restyles Square's native subcategory tiles on category pages to match the chosen hero variant. Append it to the same `<style>` block as the hero CSS. Variant B is shown  -  for variants C / D, swap the overlay/positioning rules accordingly.

```css
a.sub-category-group__link {
  position: relative !important;
  display: block !important;
  aspect-ratio: 5 / 4 !important;
  overflow: hidden !important;
  background: #faf6ed !important;
  border: 1px solid #d9cdb1 !important;
  text-decoration: none !important;
  font-family: Georgia, 'Times New Roman', serif !important;
  transition: all .25s ease !important;
}

/* Square wraps the image in nested divs  -  flatten them */
a.sub-category-group__link > div:first-child {
  position: absolute !important;
  inset: 0 !important;
  height: 100% !important;
  width: 100% !important;
}
a.sub-category-group__link .product-image__link-wrapper,
a.sub-category-group__link .product-image__link,
a.sub-category-group__link .figure__aspect-ratio {
  position: absolute !important;
  inset: 0 !important;
  width: 100% !important;
  height: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
}
a.sub-category-group__link img {
  width: 100% !important;
  height: 100% !important;
  object-fit: cover !important;
  position: absolute !important;
  inset: 0 !important;
}

/* Cream overlay above image */
a.sub-category-group__link::after {
  content: '' !important;
  position: absolute !important;
  inset: 0 !important;
  background: rgba(250, 246, 237, {OVERLAY_ALPHA}) !important;
  z-index: 5 !important;
  transition: background .25s ease !important;
  pointer-events: none !important;
}

/* Title overlay */
a.sub-category-group__link .sub-category-title__padding {
  position: absolute !important;
  inset: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 18px !important;
  z-index: 6 !important;
  pointer-events: none !important;
  text-align: center !important;
}
a.sub-category-group__link .sub-category-title__padding p {
  font-family: Georgia, 'Times New Roman', serif !important;
  font-size: 18px !important;
  font-weight: 400 !important;
  color: #2a2520 !important;
  margin: 0 !important;
  letter-spacing: 0.3px !important;
  line-height: 1.3 !important;
}

/* Hover */
a.sub-category-group__link:hover::after {
  background: rgba(42, 37, 32, 0.85) !important;
}
a.sub-category-group__link:hover .sub-category-title__padding p {
  color: #faf6ed !important;
}
a.sub-category-group__link:hover {
  border-color: #2a2520 !important;
  transform: translateY(-3px) !important;
  box-shadow: 0 8px 20px rgba(0,0,0,.18) !important;
}

/* Grid layout */
.content-grid.tight-grid:has(a.sub-category-group__link) {
  gap: 14px !important;
  padding: 0 8px !important;
  max-width: 1100px !important;
  margin: 0 auto !important;
}
.sub-category-group.tight-product-group {
  margin: 0 !important;
}
```

For variant C (dark gradient overlay): replace the `::after` rule with a `linear-gradient(to top, rgba(0,0,0,0.65), rgba(0,0,0,0.1))` background, swap the title color to `#fff`, and bottom-align it via `align-items: flex-end`. For variant D (side image + text): change `aspect-ratio` to `5/3`, set `display: flex !important` on the anchor, give the image wrapper `flex: 0 0 38%`, and put the title in its own flex child.

## Reference: Richmond General v0.2.1 deployment

The skill was first shipped with variant B (soft, 0.78 overlay) on the Richmond General site (`site_649797114786509406`). Snippet ID: `snippet_97ff7460-4d48-11f1-8477-2def9fd33632`. v0.2.1 added subcategory tile overrides to the same snippet. See the live result at https://www.richmondgeneral.com/s/shop and any child category page like https://www.richmondgeneral.com/shop/the-general-store/QLM2GZ643LOCYHB653YIDJWT.
