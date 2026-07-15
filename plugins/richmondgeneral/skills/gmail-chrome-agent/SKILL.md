---
name: gmail-chrome-agent
description: >
  Automate Gmail operations using Claude in Chrome browser tools. Use this skill whenever the user
  wants to manage email — reading, searching, filtering, unsubscribing, deleting, composing, labeling,
  archiving, or any batch email operations in Gmail. Prefer Chrome browser tools (read_page, find,
  form_input, javascript_tool, computer) over Gmail API tools for interactive tasks. Always use
  keyboard shortcuts over mouse clicks when possible. Trigger on: "check my email", "clean up inbox",
  "unsubscribe", "delete emails from X", "label these", "archive", "compose email", "email cleanup",
  "inbox zero", or any Gmail management request.
---

# Gmail Chrome Agent

Operate Gmail efficiently through Chrome browser automation. Prioritize speed via keyboard shortcuts,
JavaScript injection, and batch operations.

## Setup — Run Once Per Session

### 1. Get Tab Context
```
tabs_context_mcp (createIfEmpty: true)
```

### 2. Navigate to Gmail
```
navigate → https://mail.google.com
```

### 3. Set Standard Viewport
```
resize_window → 1920x1080
```

### 4. Enable Keyboard Shortcuts Verification
Use `javascript_tool` to verify Gmail is loaded and ready:
```javascript
document.title.includes('Gmail') || document.title.includes('mail')
```

## Tool Priority

ALWAYS prefer tools in this order:
1. **`javascript_tool`** — Fastest. Use for DOM queries, form filling, bulk selection, extracting email data
2. **`find`** — Locate elements by natural language when JS selectors are unclear
3. **`form_input`** — Set search queries, compose fields
4. **Keyboard shortcuts via `computer` key action** — Navigate and act on emails
5. **`computer` left_click** — Last resort when shortcuts/JS don't work
6. **Gmail API tools (`search_gmail_messages`, `read_gmail_thread`)** — Only for data extraction that's faster than scraping, or when Chrome tools can't access content

## Keyboard Shortcuts Reference

Read `references/keyboard-shortcuts.md` for the full reference. Key shortcuts used constantly:

| Action | Keys | Notes |
|--------|------|-------|
| Search | `/` | Focus search bar instantly |
| Select conversation | `x` | Toggle selection checkbox |
| Delete | `#` | Delete selected/open email |
| Archive | `e` | Archive selected/open |
| Reply | `r` | Reply to open email |
| Reply All | `a` | Reply all |
| Forward | `f` | Forward |
| Compose | `c` | New email |
| Send | `Cmd+Enter` | Send composed email |
| Go to Inbox | `g` then `i` | Two-key sequence |
| Back to list | `u` | Return to message list |
| Next message | `j` | Older conversation |
| Prev message | `k` | Newer conversation |
| Mark read | `Shift+i` | |
| Mark unread | `Shift+u` | |
| Star | `s` | Toggle star |
| Label | `l` | Open label picker |
| Move | `v` | Move to folder |
| Select all | `* a` | Select all visible |
| Deselect all | `* n` | Deselect all |
| Open | `o` or `Enter` | Open conversation |
| Undo | `z` | Undo last action |
| Help | `?` | Show shortcut overlay |

## Core Workflows

### Search Emails
```
1. computer → key "/" (focuses search)
2. computer → type "search query"  
3. computer → key "Return"
```
Use Gmail search operators: `from:`, `to:`, `is:unread`, `has:attachment`, `label:`, `subject:`, `after:`, `before:`, `newer_than:`, `older_than:`

### Open & Read Email
```
1. From list: computer → key "o" or "Return" (open)
2. Read: use get_page_text or read_page for content
3. Back: computer → key "u"
```

### Delete Email (Open)
```
computer → key "#"
```

### Delete Email (From List — Batch)
```
1. x (select first), j (move down), x (select next) — repeat
2. # (delete all selected)
```

### Archive Batch
```
1. Select with x/j/x pattern
2. computer → key "e"
```

### Unsubscribe Flow
When inside an open email:
```
1. find → "Unsubscribe" link/button
2. left_click the Unsubscribe element
3. If Gmail dialog appears → click "Unsubscribe" button in dialog
4. If redirected to external page → navigate back
5. Delete: computer → key "#"
```

### Compose Email
```
1. computer → key "c" (opens compose)
2. computer → type "recipient@email.com" in To field
3. computer → key "Tab" (move to subject)
4. computer → type "Subject line"
5. computer → key "Tab" (move to body)
6. computer → type "Email body"
7. computer → key "cmd+Return" (send)
```

### Label Emails
```
1. Select emails with x
2. computer → key "l" (open label picker)
3. computer → type "label name"
4. computer → key "Return" (apply)
```

### Batch Operations Loop Pattern

For repetitive operations (unsubscribe+delete loop, label+archive, etc.):

```
PATTERN:
  1. Search/filter to target set
  2. Open first email (o or Enter)
  3. Perform action (unsubscribe, read, etc.)
  4. Delete (#) or Archive (e) — Gmail auto-advances to next
  5. Repeat step 3-4 until done
  6. Press u to return to list if needed
```

Gmail's auto-advance means after deleting/archiving, the next email in the search results loads automatically. Exploit this for fast looping.

## JavaScript Speed Patterns

Read `references/javascript-patterns.md` for advanced JS patterns. Key patterns:

### Extract Email List Data
```javascript
// Get all visible email rows with sender, subject, date
Array.from(document.querySelectorAll('tr.zA')).map(row => ({
  sender: row.querySelector('.yW span')?.getAttribute('email') || row.querySelector('.yW')?.textContent?.trim(),
  name: row.querySelector('.yW .bA4 span, .yW .zF')?.getAttribute('name') || row.querySelector('.yW')?.textContent?.trim(),
  subject: row.querySelector('.bog')?.textContent?.trim(),
  snippet: row.querySelector('.y2')?.textContent?.trim(),
  date: row.querySelector('.xW.xY span')?.getAttribute('title') || row.querySelector('.xW.xY')?.textContent?.trim(),
  isUnread: row.classList.contains('zE'),
  isStarred: row.querySelector('.T-KT-Jp') !== null
}))
```

### Bulk Select by Criteria
```javascript
// Select all emails matching a sender pattern
document.querySelectorAll('tr.zA').forEach(row => {
  const sender = row.querySelector('.yW')?.textContent || '';
  if (sender.toLowerCase().includes('TARGET_SENDER')) {
    const checkbox = row.querySelector('div[role="checkbox"]');
    if (checkbox && checkbox.getAttribute('aria-checked') !== 'true') {
      checkbox.click();
    }
  }
});
```

### Count Results
```javascript
document.querySelectorAll('tr.zA').length
```

### Get Current Email Details (When Open)
```javascript
({
  subject: document.querySelector('h2.hP')?.textContent,
  sender: document.querySelector('.gD')?.getAttribute('email'),
  senderName: document.querySelector('.gD')?.getAttribute('name'),
  date: document.querySelector('.g3')?.textContent,
  hasUnsubscribe: !!document.querySelector('a[href*="unsubscribe"], span.gn')
})
```

### Fast Search via URL
```javascript
// Navigate directly to search results — faster than using the search bar
window.location.hash = '#search/' + encodeURIComponent('is:unread from:github.com');
```

## Decision Matrix

| Task | Best Approach |
|------|--------------|
| Find specific emails | JS URL hash search or `/` + type |
| Read email content | `get_page_text` (fastest) or `read_page` |
| Identify senders in list | `javascript_tool` to extract email data |
| Single email actions | Keyboard shortcuts (`#`, `e`, `r`, `s`) |
| Batch select by sender | `javascript_tool` bulk select, then shortcut |
| Batch select visible | `* a` shortcut |
| Unsubscribe | `find` → click Unsubscribe link → confirm dialog |
| Compose/reply | Keyboard shortcuts + `computer type` |
| Navigate between views | `g+i`, `g+s`, `g+t`, `g+d`, `u` |
| Check if shortcuts enabled | `?` key — if overlay appears, they're on |

## Error Handling

- **Search returns nothing**: Verify search syntax. Try broader terms.
- **Keyboard shortcut doesn't work**: Shortcuts may be disabled. Check Settings → General → Keyboard shortcuts.
- **Unsubscribe link missing**: Look in email body with `find → "unsubscribe"` or check footer text.
- **Gmail loads slowly**: Use `computer → wait 2` between actions.
- **Auto-advance didn't happen**: Press `j` to go to next, or `u` to return to list.
- **Dialog/popup blocks action**: Take screenshot, identify dialog, handle it before continuing.

## Important Notes

- Always take a **screenshot** before starting to understand current Gmail state
- After batch operations, report a **summary** of actions taken
- When looping, count iterations and report progress
- If an email is from the user themselves (thescottybe, beilsco), skip unless told otherwise
- Gmail's DOM classes can vary — if JS selectors fail, fall back to `find` or `read_page`
- Use `computer → wait 1` after navigation to let Gmail render
