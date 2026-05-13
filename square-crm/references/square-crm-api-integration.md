# Square CRM Skill - API Integration Guide

This document outlines API integration patterns specific to the square-crm skill for syncing Richmond General contacts with Square customer records.

## API Version

**Target Version**: 2026-04-21  
**Minimum Version**: 2025-01-23 (due to deprecated Customer.cards field)

## Required Permissions (OAuth Scopes)

For complete customer management via OAuth:
- `CUSTOMERS_READ` - List/search/retrieve customers
- `CUSTOMERS_WRITE` - Create/update customers
- `CUSTOMERS_MANAGE_GROUPS` - Add customers to groups

For personal access token (own account only):
- No scoping required—full access to all APIs

## Location Configuration

**Richmond General Location ID**: `L65JWBQEKPVHF` (from SKILL.md)  
**Note**: Verify this matches current Square account setup

## Endpoint Mapping

### Customer Search (Avoid Duplicates)

**Endpoint**: `POST /v2/customers/search`  
**Scope Required**: `CUSTOMERS_READ`  
**Purpose**: Check if customer exists before creating

```json
{
  "query": {
    "filter": {
      "phone_number": {
        "exact": "+13124483219"
      }
    }
  }
}
```

**Response**:
- Empty result: Customer doesn't exist → proceed with create
- Matching customer: Customer exists → update instead

### Customer Creation

**Endpoint**: `POST /v2/customers`  
**Scope Required**: `CUSTOMERS_WRITE`  
**Idempotency Key**: Required (use `imessage:{phone_number}` format)

```json
{
  "idempotency_key": "imessage:+13124483219",
  "given_name": "Walid",
  "family_name": "Bandar",
  "phone_number": "+13124483219",
  "reference_id": "imessage:+13124483219",
  "note": "[Customer] - New Wave vinyl\nSource: iMessage contact"
}
```

**Response Fields**:
- `customer.id`: Use in subsequent operations
- `customer.version`: Track for concurrent update handling

### Customer Update

**Endpoint**: `PUT /v2/customers/{customer_id}`  
**Scope Required**: `CUSTOMERS_WRITE`  
**Idempotency Key**: Recommended for safety

```json
{
  "idempotency_key": "imessage:+13124483219",
  "note": "[Customer] - New Wave vinyl\nStatus: Active\nPromise: Call re: Estate sale\nSource: iMessage contact"
}
```

**Important**: Only include fields to update. Don't overwrite other data.

### Add Customer to Group

**Endpoint**: `POST /v2/customers/{customer_id}/groups/{group_id}`  
**Scope Required**: `CUSTOMERS_MANAGE_GROUPS`  
**Request Body**: Empty JSON object `{}`

Example: Add to Vinyl Collectors group
```json
POST /v2/customers/JDKYHBWT1D4F8MFH63DBMEN8Y4/groups/4A4AG6K8CYAYC7T2HSE2R04EJE
{}
```

## Customer Groups Reference

| Group | ID | Purpose |
|-------|----|---------| 
| Vinyl Collectors | `4A4AG6K8CYAYC7T2HSE2R04EJE` | Collectors interested in vinyl records |
| Estate Sources | `1HR6MC66JXVC5A1XS7137W7DAX` | Sources for estate sales |
| Resellers | `34THMX8DN921VQ04KGHV7KZ0AA` | eBay/online resellers |
| VIP | `6NGXFHDNJ6MVEFMJKXE8PZ8VMZ` | High-value customers |
| Trades | `7XP6P4G6KDYQZ32HHCRNH9RJKM` | Trade customers |

## Phone Number Format

Square requires E.164 format:
- `+1` country code prefix
- 10-digit North American numbers: `+1` + digits
- International: `+` + country code + local digits
- Valid range: 9-16 digits total

Examples:
- US: `+13124483219` ✓
- Input `3124483219` → normalize to `+13124483219` ✓
- Input `+1-312-448-3219` → normalize to `+13124483219` ✓

## Note Format Convention

Structure customer notes for readability in Square Dashboard:

```
[Category] - Descriptor
Status: Active|Inactive|Prospect
Promise: Description of commitment
Waiting: What we're waiting for
Source: iMessage contact
Custom: Any additional notes
```

Example:
```
[Customer] - New Wave vinyl collector
Status: Active
Promise: Selling estate LP collection Q1 2026
Waiting: Price estimates for 15 records
Source: iMessage contact
```

## Reference ID Usage

**Purpose**: Link Square customer records back to source system  
**Format**: `imessage:{phone_number}`  
**Example**: `imessage:+13124483219`  
**Max Length**: 100 characters

Benefits:
- Idempotent operations (use same reference_id across multiple syncs)
- Source tracking
- Bidirectional lookup capability (future Phase 3)

## Handling Concurrent Updates

### Version Field Behavior

<cite index="12-1,12-2,12-3">Square also uses the version to filter events that trigger webhook notifications. If concurrent updates are made to the same customer profile, Square compares the version numbers and sends a notification for the latest version only. Similarly, if you process notifications in batches, you can use the version attribute of the Customer object in the notification to determine the latest version of an updated customer profile.</cite>

**Implementation Strategy**:
- Store customer version locally after each update
- If local version differs from returned version, another update occurred
- Re-fetch customer before next update to get current version
- Don't rely on version field for optimistic locking (not supported)

## Deprecated Fields to Avoid

As of API version 2025-01-23:
- ❌ `customer.cards` (use Cards API instead)
- ❌ `CreateCustomerCard` endpoint
- ❌ `DeleteCustomerCard` endpoint

The square-crm skill doesn't use these, but be aware if adding card management later.

## Error Handling Patterns

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Proceed |
| 201 | Created | Resource created, use returned ID |
| 204 | No Content | Update successful, no response body |
| 400 | Bad Request | Validation error—check phone format, required fields |
| 401 | Unauthorized | Token expired or invalid—refresh OAuth token |
| 403 | Forbidden | Insufficient permissions—check OAuth scopes |
| 404 | Not Found | Resource doesn't exist—check IDs |
| 409 | Conflict | Version mismatch—re-fetch and retry |
| 429 | Rate Limited | Back off exponentially |
| 500+ | Server Error | Retry with exponential backoff |

### OAuth-Specific Errors

<cite index="26-19,26-20,26-21,26-22,26-23,26-24">When your application uses an access token to call a Square API, OAuth-related errors can occur if a token is expired, is revoked, or has insufficient scope (unauthorized). Your application should handle these error codes and display a customer-friendly message that clearly communicates the error to the seller, their customer, or both. Square retains expired access tokens for a limited time. During this time, the Square API returns the ACCESS_TOKEN_EXPIRED error. After that time, the Square API returns an UNAUTHORIZED error. Square API calls that return the UNAUTHORIZED error aren't cases of insufficient scope.</cite>

## Pagination (for List Operations)

When listing all customers:
```
GET /v2/customers?cursor={cursor}&limit=100
```

- First request: omit cursor or use empty string
- Continue with cursor from response until no cursor returned
- Max limit: typically 100

## Rate Limiting Considerations

Not publicly documented, but generally:
- Burst: 100+ requests/minute acceptable
- Sustained: Distribute load over time
- Implement exponential backoff for 429 responses
- Monitor Developer Dashboard for account limits

## Testing in Sandbox

Use Sandbox credentials from Developer Console:
```
https://connect.squareupsandbox.com/v2/customers
```

Sandbox test accounts don't have OAuth authorization requirements for testing.

## Headers Summary

```
POST /v2/customers HTTP/1.1
Host: connect.squareup.com
Authorization: Bearer {ACCESS_TOKEN}
Content-Type: application/json
Square-Version: 2026-04-21
Idempotency-Key: {UNIQUE_KEY}

{...request body...}
```

## Related Documentation

- `square-api-foundational.md` - General Square API concepts
- `api-version-history.md` - Version tracking and deprecations
- `SKILL.md` - square-crm skill definition and workflow
- `parse_contacts.py` - Script that generates API-ready requests
- `lookup_customer.py` - Script for customer search requests
