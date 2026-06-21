# Info Card Publishing Commands (Phase 7)

## Step 7.2: Generate QR code (payment link)

```applescript
do shell script "source ~/.local/bin/env && cd /Users/scottybe/workspace/richmondgeneral/items/RG-XXXX && uv run --project ${CLAUDE_PLUGIN_ROOT} python -c \"import qrcode; qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2); qr.add_data('https://square.link/u/XXXXXXXX'); qr.make(fit=True); img = qr.make_image(fill_color='#2C2C2C', back_color='white'); img.save('qr-code.png'); print('QR code saved')\""
```

## Step 7.3: Add to gallery index (use the builder — do NOT hand-`sed`)

**Run the idempotent gallery reconciler** instead of injecting a card by hand. It
inserts a card (built from `label.json`) for **every** Listed/Sold item that is
missing one, in SKU order, leaving existing curated cards untouched. Re-running is
a no-op, and it recomputes the item count for you (so the old Step 7.4 is gone).

```bash
# from the workspace root
python items/scripts/build_gallery.py --apply
```

> Why this replaced the old `sed`: the hand-run `sed` against the
> `<!-- Coming Soon Placeholder -->` anchor was brittle and easy to skip, which is
> exactly how RG-0028/0029/0034/0052/0053/0054 went live as standalone pages but
> never appeared in the grid. The builder is the single source of truth for the
> gallery and lives in the **`items/` repo** (one copy; deploys with GitHub Pages —
> no plugin dual-copy to sync).

The builder derives `data-category` from the item's reporting category via its own
keyword map (`books / pottery / furniture / tech / media / wearables /
collectibles`) — keep that map (`_SLUG_RULES` in `build_gallery.py`) authoritative;
the old hand-maintained category table here was stale (missing `tech`, `media`,
`wearables`) and has been removed.

## Step 7.4: Verify the gallery gate

```bash
python items/scripts/build_gallery.py --check   # must exit 0
```

Fails (exit 1) if any Listed/Sold item lacks a gallery card, or a card points at a
deleted item dir. Wire this into reconcile/CI: a live item page that isn't in the
grid is **not done**.

## Step 7.5: Cleanup temp files

```applescript
do shell script "rm -f /Users/scottybe/workspace/richmondgeneral/items/RG-XXXX/hero_temp.png 2>/dev/null; echo 'Cleanup complete'"
```

## Step 7.6: Git commit and push

```applescript
do shell script "cd /Users/scottybe/workspace/richmondgeneral/items && git add RG-XXXX/ index.html && git commit -m 'Add RG-XXXX: Item Title' && git push origin main 2>&1"
```
