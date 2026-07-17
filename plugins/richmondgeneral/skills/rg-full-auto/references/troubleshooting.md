# Troubleshooting

## Image too large for remove.bg
- remove.bg limit is 22MB
- Compress first: `sips -Z 3000 image.png --out hero_temp.png`

## Image upload fails
- Ensure catalog item created FIRST (need ITEM_ID for image upload)
- Check token: `source ~/.env && echo $SQUARE_ACCESS_TOKEN`
- Verify image is PNG or JPEG (WebP not supported)

## Background removal fails
- Check API keys on user's Mac: `source ~/.env && echo $REMOVEBG_API_KEY`
- Ensure image is accessible on user's Mac (not just in Claude's container)
- Check remaining credits in script output

## Photos cluster discovery fails
- Check Photos DB path exists: `~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite`
- Ensure terminal/Codex has Full Disk Access on macOS
- If you see `sqlite3.OperationalError: unable to open database file`, this is usually a macOS privacy permission issue
- Fall back to Step 0.5 manual image selection

## Binary file transfer fails
- Binary files (PNG, JPEG) cannot transfer between Claude's container and user's Mac
- Solution: Generate binaries via osascript on user's Mac directly

## Square 401 Unauthorized
- Token expired: Check `$SQUARE_ACCESS_TOKEN`

## Inventory API rejects request
- Do NOT include `catalog_object_type` -- Square rejects it as a write-only field
- Ensure `quantity` is a string, not integer

## Image upload 413 Too Large
- Compress: `sips -Z 2000 image.png`

## Item shows "sold out"
- Missing inventory count (Phase 3)

## Path case mismatch
- Filesystem tools may return `/Workspace/` instead of `/workspace/`
- Use osascript + sed for file edits on user's Mac
