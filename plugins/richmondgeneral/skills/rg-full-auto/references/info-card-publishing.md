# Info Card Publishing Commands (Phase 7)

## Step 7.2: Generate QR code (payment link)

```applescript
do shell script "source ~/.local/bin/env && cd /Users/scottybe/workspace/richmondgeneral/items/RG-XXXX && uv run --project ${CLAUDE_PLUGIN_ROOT} python -c \"import qrcode; qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2); qr.add_data('https://square.link/u/XXXXXXXX'); qr.make(fit=True); img = qr.make_image(fill_color='#2C2C2C', back_color='white'); img.save('qr-code.png'); print('QR code saved')\""
```

## Step 7.3: Add to gallery index

Use osascript (Filesystem tools may return wrong-case paths):

```applescript
do shell script "sed -i '' 's|<!-- Coming Soon Placeholder -->|<!-- RG-XXXX: Item Title -->\\
            <a href=\"./RG-XXXX/\" class=\"item-card\" data-category=\"CATEGORY\">\\
                <div class=\"item-image\">\\
                    <span class=\"item-badge\">New</span>\\
                    <span class=\"item-sku\">RG-XXXX</span>\\
                    <img src=\"./RG-XXXX/hero.png\" alt=\"Item Title\" style=\"max-width: 100%; max-height: 200px; object-fit: contain; border-radius: 4px;\">\\
                </div>\\
                <div class=\"item-info\">\\
                    <p class=\"item-category\">Category</p>\\
                    <h3 class=\"item-title\">Item Title</h3>\\
                    <p class=\"item-era\">Era • Origin • Feature</p>\\
                    <div class=\"item-footer\">\\
                        <span class=\"item-price\">$XX.XX</span>\\
                        <span class=\"view-story\">\\
                            View Story\\
                            <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\">\\
                                <path d=\"M5 12h14M12 5l7 7-7 7\"/>\\
                            </svg>\\
                        </span>\\
                    </div>\\
                </div>\\
            </a>\\
            \\
            <!-- Coming Soon Placeholder -->|' /Users/scottybe/workspace/richmondgeneral/items/index.html"
```

**Categories for `data-category` filter on index card:**

| data-category | Square types |
|---|---|
| `books` | Books & Paper |
| `furniture` | Furniture |
| `pottery` | Pottery & Ceramics |
| `collectibles` | Collectibles, Art & Craft Kits, Wellness & Apothecary, The Apothecary Cabinet, Home & Gifts, Analog |

## Step 7.4: Update item count

```applescript
do shell script "sed -i '' 's|<div class=\"stat-number\" id=\"item-count\">[0-9]*</div>|<div class=\"stat-number\" id=\"item-count\">NEW_COUNT</div>|' /Users/scottybe/workspace/richmondgeneral/items/index.html"
```

## Step 7.5: Cleanup temp files

```applescript
do shell script "rm -f /Users/scottybe/workspace/richmondgeneral/items/RG-XXXX/hero_temp.png 2>/dev/null; echo 'Cleanup complete'"
```

## Step 7.6: Git commit and push

```applescript
do shell script "cd /Users/scottybe/workspace/richmondgeneral/items && git add RG-XXXX/ index.html && git commit -m 'Add RG-XXXX: Item Title' && git push origin main 2>&1"
```
