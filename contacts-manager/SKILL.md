---
name: contacts-manager
description: Contact lookup, quick reference, and spam filtering. Use when user asks who a phone number belongs to, needs contact info, wants to lookup or add a contact, identify unknown numbers, or check if a number is spam. Contains detailed profiles with communication style notes for composing personalized replies.
---

# Contacts Manager

## Quick Reference - Core Contacts

| Name | Phone | Service |
|------|-------|---------|
| Freeman (Dad) | +12242308079 | RCS |
| Dawn | +18472871148 | iMessage |
| Sue Miller | +18152362387 | RCS |
| Jennifer | +16305444884 | iMessage |
| Jeff Thompson | +18475677182 | iMessage |
| Mike Giba | +13129143889 | RCS |
| Amy D (HOA) | +17736763930 | iMessage |
| Gary Goza Sr | +18474179386 | iMessage |
| Jamie Boutain | +16519834441 | iMessage |

## Quick Reference - Richmond General Customers

| Name | Phone | Service | Status |
|------|-------|---------|--------|
| Walid Bandar | +13124483219 | iMessage | Hot - New Wave vinyl |
| Lynn | +18473383408 | RCS | Pending - books |
| Steven (Elmhurst) | +12623082827 | iMessage | Active - estate sourcing |
| Joshua Bohlman | +14148757568 | iMessage | Trade - vinyl/laserdiscs |
| Pete (eBay) | +18082228761 | RCS | Partner - 75+ items |

## Group Chats

| Name | Chat ID | Participants |
|------|---------|--------------|
| Dawn & Jennifer | 980 | Dawn, Jennifer |
| HOA Drywall | 1343 | Dawn, Amy, neighbors |
| Shagbark | 1053 | Dawn, Amy, multiple |

## Agent-Friendly Contacts

These contacts know Scott uses AI agents. Can message AS the agent directly:

| Contact | Style Notes |
|---------|-------------|
| Jeff Thompson | Turing test jokes, deep AI/tech talk. Co-founder bond. |
| Jennifer Long | Plays along. "Forewarn" = lookup/pre-qualify a contact. |
| Jamie Boutain | Bot detection jokes. "We won't know till the cutting starts." |

When messaging as agent: identify as "Scott's AI" or "Claude", reference that Scott asked you to reach out, keep it playful.

## Detailed Profiles

For full contact details, style notes, and CRM fields (Promise/Waiting), see:
- `references/contacts.md` - Complete profiles with communication style, history, shared interests

## Spam Filtering

For spam detection patterns and known spam numbers, see:
- `references/spam_numbers.md` - Short codes, toll-free spam, detection patterns

**Quick spam indicators:**
- Short codes (5-6 digits) with promotional URLs
- 800/855/888 numbers with "Reply STOP"
- `wgames.app`, `Nexfund`, `.icu` domains

## Unknown Number Identification

When encountering unknown numbers:

1. Check `references/spam_numbers.md` first - ignore if spam
2. Use MCP `search_contacts` by name if any context available
3. Query recent messages for identity clues
4. If legitimate contact identified, add to `references/contacts.md`

## Composing Personalized Replies

For close contacts, pull 100-200 messages and reference their profile in `references/contacts.md` for:
- Communication style and tone
- Shared jokes and references
- Current life situation
- Relationship depth and history

Match their energy. Reference shared context naturally.
