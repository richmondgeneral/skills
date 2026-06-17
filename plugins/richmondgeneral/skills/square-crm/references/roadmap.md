# Square CRM Roadmap

Future features to implement when needed.

## Phase 2: Orders Integration
When Richmond General starts using Square Orders (not just payments):
- Pull purchase history per customer
- Include last purchase date in CRM briefings
- Total spend calculations
- Item-based re-engagement messaging

## Phase 3: Bidirectional Sync
⚠️ **Complexity warning**: This requires careful conflict resolution.

Challenges:
- Which system is source of truth?
- How to handle edits in both places?
- Square notes are free-text, contacts.md is structured

Possible approaches:
1. **One-way only**: contacts.md → Square (current)
2. **Square as read-only enrichment**: Pull data but never push back
3. **Timestamp-based merge**: Last-write-wins with conflict log
4. **Manual review queue**: Flag conflicts for human decision

Recommendation: Start with approach #2 until pain points emerge.

## Phase 4: Contact Source Options
Currently using: iMessage contacts (contacts.md)

Future options to consider:
- **Google Contacts**: Better for cross-device sync, API available
- **Apple Contacts**: Native macOS integration, AppleScript accessible
- **Square as primary**: Use Square CRM as source, sync TO messaging

Evaluation criteria:
- Where do contacts naturally get created?
- Which system has better mobile access?
- API reliability and rate limits

## Phase 5: Automation
- Scheduled sync (launchd daily job)
- New contact detection → auto-create in Square
- Stale contact alerts (no activity 30+ days)
