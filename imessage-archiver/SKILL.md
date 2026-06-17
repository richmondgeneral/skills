---
name: imessage-archiver
description: Archive iMessage/RCS/SMS conversations to Apple Notes with inline images and attachments. Use when user wants to save, archive, or export text message conversations to Notes. Handles media embedding correctly using sequential attachment pattern. Supports date ranges, contact filtering, and automatic image resizing.
metadata:
  version: "1.2"
  author: scottybe
  updated: "2026-06-17"
  changelog: |
    v1.2 - Safe database access (critical fix):
    - archive_to_notes.py now opens chat.db with mode=ro&immutable=1 (was a
      plain read-write connection). Prevents taking locks / checkpointing the
      live WAL, which could disrupt Messages/iCloud sync. Reads only; the
      archive is written to Apple Notes via AppleScript.

    v1.1 - Anthropic skills update:
    - Added author and updated fields
---

# iMessage Archiver

Archive conversations from Messages app to Apple Notes with proper inline media rendering.

## Key Insight: Sequential Attachment Pattern + Timing

**CRITICAL**: Apple Notes renders attachments inline only when:
1. Added sequentially with text between them
2. Given time (0.5-1s delay) to process each attachment

```
✅ WORKS: text → attach → [delay] → text → attach → [delay]
❌ FAILS: text → attach, attach, attach (no delays, batched)
```

## Quick Start

### 1. Get Messages + Attachments

```bash
# Get conversation with phone number
python3 ~/scripts/get_imessage_convo.py +1XXXXXXXXXX 30

# Get attachments for date range
sqlite3 ~/Library/Messages/chat.db "
SELECT datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as ts,
       a.filename, a.mime_type, a.total_bytes
FROM message m
JOIN handle h ON m.handle_id = h.ROWID
JOIN message_attachment_join maj ON maj.message_id = m.ROWID
JOIN attachment a ON maj.attachment_id = a.ROWID
WHERE h.id LIKE '%PHONE_LAST_10%'
AND datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') >= 'YYYY-MM-DD'
ORDER BY m.date
"
```

### 2. Prepare Images (Required for Inline Rendering)

```bash
# Resize to max 800px (prevents rendering issues)
mkdir -p ~/tmp
sips -Z 800 "SOURCE_PATH" --out ~/tmp/resized_image.png

# Copy to Desktop for reliable AppleScript access
cp ~/tmp/resized_image.png ~/Desktop/
```

### 3. Create Note with Sequential Attachments

**Step-by-step pattern** (each step is a separate osascript call):

```applescript
-- Step 1: Create note with initial content
tell application "Notes"
    make new note at folder "Notes" with properties {name:"TITLE", body:"<h1>TITLE</h1><p>First message...</p><p><b>TIME:</b> Description of attachment ⬇️</p>"}
end tell

-- Step 2: Add first attachment
tell application "Notes"
    tell account "iCloud"
        set theNote to first note whose name is "TITLE"
        tell theNote
            make new attachment at end of attachments with data (POSIX file "/Users/scottybe/Desktop/image1.png")
        end tell
    end tell
end tell

-- Step 3: Add more text + next attachment indicator
tell application "Notes"
    tell account "iCloud"
        set theNote to first note whose name is "TITLE"
        set currentBody to body of theNote
        set body of theNote to currentBody & "<p><b>NEXT_TIME:</b> Next attachment description ⬇️</p>"
        tell theNote
            make new attachment at end of attachments with data (POSIX file "/Users/scottybe/Desktop/image2.png")
        end tell
    end tell
end tell

-- Repeat Step 3 pattern for each attachment
```

## File Type Handling

| Type | Max Size | Preparation | Notes |
|------|----------|-------------|-------|
| PNG/JPG | 2MB | Resize to 800px | Renders inline |
| HEIC | 2MB | Convert to PNG first | `sips -s format png` |
| PDF | 5MB | Copy to Desktop | May show as icon |
| Links | N/A | Use `<a href='URL'>text</a>` | Embed in HTML body |

## Workflow Checklist

1. [ ] Query messages for date range
2. [ ] Query attachments for same range
3. [ ] Copy/resize images to ~/Desktop/
4. [ ] Create note with first section + attachment indicator
5. [ ] Add first attachment
6. [ ] Loop: add text section → add attachment
7. [ ] Add final text (links, summary)
8. [ ] Clean up ~/Desktop/ temp files (optional)

## Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Images show as file icons | Batch attachment | Use sequential pattern |
| Attachment not found | Path escaping | Use POSIX file with full path |
| Note not found | Name mismatch | Use exact `name is "TITLE"` |
| Large images fail | Size limit | Resize with `sips -Z 800` |
| HEIC won't attach | Format issue | Convert: `sips -s format png` |

## Integration with imessage-core

This skill complements `imessage-core`. Use imessage-core for:
- Reading/sending messages
- Contact lookup
- Service detection (RCS/iMessage/SMS)

Use this skill (imessage-archiver) for:
- Saving conversations to Notes
- Archiving with media
- Date-range exports
