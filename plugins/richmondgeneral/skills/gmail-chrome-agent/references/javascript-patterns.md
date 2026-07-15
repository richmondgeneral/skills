# Gmail JavaScript Patterns

Use `javascript_tool` with the active Gmail tab for fast DOM operations.
Gmail's DOM uses obfuscated class names — these selectors work as of 2025/2026 but may change.

## Navigation via URL Hash

The fastest way to navigate Gmail — no waiting for UI elements:

```javascript
// Go to inbox
window.location.hash = '#inbox';

// Go to search results directly
window.location.hash = '#search/' + encodeURIComponent('is:unread');

// Go to label
window.location.hash = '#label/MyLabel';

// Go to sent
window.location.hash = '#sent';

// Go to drafts
window.location.hash = '#drafts';

// Go to all mail
window.location.hash = '#all';

// Go to trash
window.location.hash = '#trash';

// Go to spam
window.location.hash = '#spam';

// Complex search
window.location.hash = '#search/' + encodeURIComponent('from:github.com is:unread after:2025/01/01');
```

## Extracting Email List Data

### Get All Visible Emails
```javascript
Array.from(document.querySelectorAll('tr.zA')).map((row, i) => ({
  index: i,
  sender: row.querySelector('.yW span')?.getAttribute('email') || 
          row.querySelector('.yW')?.textContent?.trim(),
  senderName: row.querySelector('.yW .bA4 span, .yW .zF')?.getAttribute('name') || 
              row.querySelector('.yW')?.textContent?.trim(),
  subject: row.querySelector('.bog')?.textContent?.trim(),
  snippet: row.querySelector('.y2')?.textContent?.trim(),
  date: row.querySelector('.xW.xY span')?.getAttribute('title') || 
        row.querySelector('.xW.xY')?.textContent?.trim(),
  isUnread: row.classList.contains('zE'),
  isStarred: row.querySelector('.T-KT-Jp') !== null,
  isSelected: row.querySelector('div[role="checkbox"]')?.getAttribute('aria-checked') === 'true',
  labels: Array.from(row.querySelectorAll('.at')).map(l => l.textContent?.trim()).filter(Boolean)
}))
```

### Count Emails by Sender
```javascript
const counts = {};
document.querySelectorAll('tr.zA').forEach(row => {
  const sender = row.querySelector('.yW')?.textContent?.trim() || 'Unknown';
  counts[sender] = (counts[sender] || 0) + 1;
});
Object.entries(counts).sort((a, b) => b[1] - a[1])
```

### Get Only Unread Emails
```javascript
Array.from(document.querySelectorAll('tr.zA.zE')).map(row => ({
  sender: row.querySelector('.yW')?.textContent?.trim(),
  subject: row.querySelector('.bog')?.textContent?.trim()
}))
```

### Get Result Count
```javascript
// From the result count text like "1–10 of many" or "1–50 of 127"
document.querySelector('.Dj .ts')?.textContent || 
document.querySelector('.amH .Dj')?.textContent ||
document.querySelectorAll('tr.zA').length + ' visible'
```

## Selection Operations

### Select All Visible
```javascript
document.querySelectorAll('tr.zA div[role="checkbox"]').forEach(cb => {
  if (cb.getAttribute('aria-checked') !== 'true') cb.click();
});
'Selected all visible emails'
```

### Deselect All
```javascript
document.querySelectorAll('tr.zA div[role="checkbox"]').forEach(cb => {
  if (cb.getAttribute('aria-checked') === 'true') cb.click();
});
'Deselected all'
```

### Select by Sender Pattern
```javascript
let count = 0;
document.querySelectorAll('tr.zA').forEach(row => {
  const sender = (row.querySelector('.yW')?.textContent || '').toLowerCase();
  if (sender.includes('TARGET_PATTERN')) {
    const cb = row.querySelector('div[role="checkbox"]');
    if (cb && cb.getAttribute('aria-checked') !== 'true') {
      cb.click();
      count++;
    }
  }
});
count + ' emails selected'
```

### Select Unread Only
```javascript
let count = 0;
document.querySelectorAll('tr.zA.zE').forEach(row => {
  const cb = row.querySelector('div[role="checkbox"]');
  if (cb && cb.getAttribute('aria-checked') !== 'true') {
    cb.click();
    count++;
  }
});
count + ' unread emails selected'
```

### Select by Subject Pattern
```javascript
let count = 0;
document.querySelectorAll('tr.zA').forEach(row => {
  const subject = (row.querySelector('.bog')?.textContent || '').toLowerCase();
  if (subject.includes('TARGET_PATTERN')) {
    const cb = row.querySelector('div[role="checkbox"]');
    if (cb && cb.getAttribute('aria-checked') !== 'true') {
      cb.click();
      count++;
    }
  }
});
count + ' emails selected by subject'
```

## Open Email Extraction

### Get Current Email Details
```javascript
({
  subject: document.querySelector('h2.hP')?.textContent,
  sender: document.querySelector('.gD')?.getAttribute('email'),
  senderName: document.querySelector('.gD')?.getAttribute('name'),
  date: document.querySelector('.g3')?.textContent,
  to: document.querySelector('.g2')?.textContent,
  labels: Array.from(document.querySelectorAll('.ar .at')).map(l => l.textContent?.trim()),
  hasUnsubscribe: !!document.querySelector('[data-tooltip="Unsubscribe"]') || 
                  document.body.innerText.toLowerCase().includes('unsubscribe'),
  unsubscribeLink: document.querySelector('a[href*="unsubscribe"]')?.href
})
```

### Get Email Body Text
```javascript
// Get the expanded message body
Array.from(document.querySelectorAll('.a3s.aiL')).map(el => el.innerText).join('\n---\n')
```

### Find Unsubscribe Link in Email Body
```javascript
const links = Array.from(document.querySelectorAll('a[href]'));
const unsub = links.filter(a => 
  a.textContent.toLowerCase().includes('unsubscribe') ||
  a.href.toLowerCase().includes('unsubscribe')
);
unsub.map(a => ({ text: a.textContent.trim(), href: a.href }))
```

## Compose Helpers

### Fill Compose Form
```javascript
// After pressing 'c' to open compose, use these to fill fields
// Note: Gmail compose uses contenteditable divs, not regular inputs

// Set To field
const toField = document.querySelector('textarea[name="to"], input[name="to"]');
if (toField) { toField.value = 'recipient@example.com'; toField.dispatchEvent(new Event('input', {bubbles: true})); }

// Set Subject
const subjectField = document.querySelector('input[name="subjectbox"]');
if (subjectField) { subjectField.value = 'Subject here'; subjectField.dispatchEvent(new Event('input', {bubbles: true})); }
```

### Check if Compose Window is Open
```javascript
!!document.querySelector('.AD, .nH .Am')
```

## Utility Patterns

### Wait for Gmail to Load
```javascript
// Check if Gmail main view is loaded
!!document.querySelector('.aDP, .aeH, tr.zA, h2.hP')
```

### Get Current View
```javascript
const hash = window.location.hash;
if (hash.includes('#inbox')) 'inbox';
else if (hash.includes('#search')) 'search: ' + decodeURIComponent(hash.split('#search/')[1] || '');
else if (hash.includes('#sent')) 'sent';
else if (hash.includes('#drafts')) 'drafts';
else if (hash.includes('#label/')) 'label: ' + decodeURIComponent(hash.split('#label/')[1] || '');
else hash;
```

### Get Gmail User Email
```javascript
document.querySelector('a[aria-label*="Google Account"]')?.getAttribute('aria-label')?.match(/\(([^)]+)\)/)?.[1] ||
document.title.match(/- (.+@.+) -/)?.[1] || 
'unknown'
```

### Check if Keyboard Shortcuts are Active
```javascript
// Dispatch a known shortcut and see if Gmail responds
// Safer: just check the URL or DOM state
document.querySelector('[data-tooltip="Compose"]') ? 'Gmail loaded, shortcuts should work' : 'Gmail not fully loaded'
```

## Performance Tips

1. **URL hash navigation** is always faster than keyboard shortcuts for jumping between views
2. **Batch JS selection** is faster than `x, j, x, j` keyboard sequences for >5 emails
3. **`get_page_text`** is faster than `read_page` for just extracting text content
4. **Combine operations**: Extract data + select in one JS call rather than separate calls
5. **Avoid screenshots** when JS can tell you what's on screen — screenshots are slow
6. Use screenshots strategically: before starting, after errors, for confirmation dialogs
