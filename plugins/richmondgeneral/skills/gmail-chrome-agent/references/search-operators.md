# Gmail Search Operators

Use these operators in the search bar (`/` shortcut) or via JS URL hash navigation.

## Basic Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `from:` | `from:amy@example.com` | Emails from a sender |
| `to:` | `to:john@example.com` | Emails sent to recipient |
| `cc:` | `cc:boss@example.com` | Emails with CC |
| `bcc:` | `bcc:team@example.com` | Emails with BCC |
| `subject:` | `subject:meeting` | Search subject line only |
| `" "` | `"exact phrase"` | Exact phrase match |
| `OR` or `{ }` | `from:amy OR from:bob` | Match either |
| `AND` | `from:amy AND to:bob` | Match both (default) |
| `-` | `dinner -movie` | Exclude term |
| `( )` | `subject:(dinner movie)` | Group terms |
| `AROUND` | `holiday AROUND 10 vacation` | Words near each other |

## Status Filters

| Operator | Example | Description |
|----------|---------|-------------|
| `is:unread` | `is:unread` | Unread messages |
| `is:read` | `is:read` | Read messages |
| `is:starred` | `is:starred` | Starred messages |
| `is:important` | `is:important` | Important messages |
| `is:snoozed` | `is:snoozed` | Snoozed messages |
| `is:muted` | `is:muted` | Muted conversations |

## Content Filters

| Operator | Example | Description |
|----------|---------|-------------|
| `has:attachment` | `has:attachment` | Has any attachment |
| `has:drive` | `has:drive` | Has Google Drive link |
| `has:document` | `has:document` | Has Google Doc |
| `has:spreadsheet` | `has:spreadsheet` | Has Google Sheet |
| `has:youtube` | `has:youtube` | Has YouTube link |
| `filename:` | `filename:pdf` | Attachment filename/type |

## Date Filters

| Operator | Example | Description |
|----------|---------|-------------|
| `after:` | `after:2025/01/01` | After date (YYYY/MM/DD) |
| `before:` | `before:2025/12/31` | Before date |
| `older_than:` | `older_than:1y` | Older than (d/m/y) |
| `newer_than:` | `newer_than:7d` | Newer than (d/m/y) |

## Location Filters

| Operator | Example | Description |
|----------|---------|-------------|
| `in:inbox` | `in:inbox` | In inbox |
| `in:sent` | `in:sent` | In sent |
| `in:drafts` | `in:drafts` | In drafts |
| `in:trash` | `in:trash` | In trash |
| `in:spam` | `in:spam` | In spam |
| `in:anywhere` | `in:anywhere movie` | Search everywhere |
| `label:` | `label:work` | In specific label |
| `category:` | `category:primary` | In category (primary/social/promotions/updates/forums) |

## Size Filters

| Operator | Example | Description |
|----------|---------|-------------|
| `size:` | `size:5000000` | Larger than N bytes |
| `larger:` | `larger:10M` | Larger than 10MB |
| `smaller:` | `smaller:1M` | Smaller than 1MB |

## Useful Combos

### GitHub notifications not from me
```
from:notifications@github.com -from:thescottybe
```

### Unread newsletters
```
is:unread category:promotions
```

### Large old attachments
```
has:attachment larger:5M older_than:6m
```

### Unsubscribe candidates (bulk email)
```
is:unread category:promotions older_than:30d
```

### Everything from a domain
```
from:@example.com
```

### Emails with specific file types
```
filename:pdf newer_than:30d
```
