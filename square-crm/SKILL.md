---
name: square-crm
description: Sync Richmond General contacts with Square CRM. Use when creating/updating Square customers, looking up customers by phone, adding notes, or syncing contact data from iMessage assistant to Square. Triggers on "add to Square", "customer lookup", "sync contacts", "Square customer".
---

# Square CRM Skill

Bridges `iMessage-assistant` contacts with Square customer records.

**Location ID**: `B87BAEZ0NWV34` (Richmond General - ACTIVE)

**Dependency**: Requires `~/skills/imessage-assistant/references/contacts.md` with Richmond General Customers section.

## Scripts

### Parse Contacts for Sync
```bash
python3 ~/skills/square-crm/scripts/parse_contacts.py              # All
python3 ~/skills/square-crm/scripts/parse_contacts.py --category Lead
python3 ~/skills/square-crm/scripts/parse_contacts.py --phone +1312...
```
Outputs JSON with `square_request` ready for API calls.

### Lookup Customer
```bash
python3 ~/skills/square-crm/scripts/lookup_customer.py +13124483219
```
Outputs search request for Square MCP.

## Sync Workflow: contacts.md → Square

1. Run `parse_contacts.py` to get customer data
2. For each contact, search Square by phone first
3. If not found → create with `customers.create`
4. If found → update note with `customers.update`
5. Add to appropriate group(s)

## Customer Groups

| Group | ID |
|-------|-----|
| Vinyl Collectors | `4A4AG6K8CYAYC7T2HSE2R04EJE` |
| Estate Sources | `1HR6MC66JXVC5A1XS7137W7DAX` |
| Resellers | `34THMX8DN921VQ04KGHV7KZ0AA` |
| VIP | `6NGXFHDNJ6MVEFMJKXE8PZ8VMZ` |
| Trades | `7XP6P4G6KDYQZ32HHCRNH9RJKM` |

## API Examples

**Search by phone:**
```javascript
Square:make_api_request
  service: "customers"
  method: "search"
  request: { query: { filter: { phone_number: { exact: "+13124483219" }}}}
```

**Create customer:**
```javascript
Square:make_api_request
  service: "customers"
  method: "create"
  characterization: "Creating customer from iMessage contact"
  request: {
    given_name: "Walid",
    family_name: "Bandar",
    phone_number: "+13124483219",
    reference_id: "imessage:+13124483219",
    note: "[Customer]\nInterest: New Wave records\nStatus: Active\nSource: iMessage contact"
  }
```

**Add to group:**
```javascript
Square:make_api_request
  service: "customers"
  method: "addGroupTo"
  request: { customer_id: "ID", group_id: "4A4AG6K8CYAYC7T2HSE2R04EJE" }
```

## Note Format Convention
Script generates notes in this format:
```
[Category]
Interest: ...
Status: ...
Promise: ...
Waiting: ...
<additional notes>
Source: iMessage contact
```

## Reference ID Convention
Use `reference_id: "imessage:+1234567890"` to link Square ↔ contacts.md.

## Future Features
See `references/roadmap.md` for:
- Orders integration (when using Square Orders)
- Bidirectional sync considerations
- Google/Apple Contacts as source options
