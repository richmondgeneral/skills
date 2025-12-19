# Square API Version History

**Current Tracking**: December 19, 2025

## Latest Version: 2025-10-16

Released October 16, 2025

**Key Updates:**
- Channels API updates
- Transfer Orders API updates

**SDK Support:**
- Java SDK: Latest
- Node.js SDK: 2025-08-20 (see note below)
- Python SDK: Latest
- PHP SDK: 43.2.0.20251016

## Recent Versions

### 2025-09-24
- New DeviceType enum (HANDHELD) for Square Handheld
- WiFi/Ethernet MAC address fields
- Subscription API: New COMPLETED status and completed_date field
- Subscriptions with fixed billing cycles automatically transition to COMPLETED status

### 2025-08-20
- In-App Payments SDK updates
- Web Payments SDK updates
- Payments API updates

### 2025-07-16
- General maintenance release

### 2025-06-18
- GraphQL updates
- Labor API updates
- Square SDK updates

### 2025-05-21
- Catalog API updates
- GraphQL updates
- Labor API updates
- Payments API (Beta/Deprecated features)

### 2025-04-16
- Catalog API updates
- Invoices API updates
- Locations API updates
- Square SDK updates
- Terminal API updates
- Webhooks updates
- App Marketplace Requirements updates
- **Note**: Python SDK rewritten with Pydantic validation library support
- Location object: Additional validation on address fields (no emojis/control characters)

### 2025-03-19
- Supported by Java SDK, Node.js SDK, Python SDK

### 2025-02-20
- PHP, Java, Node.js SDK support

### 2025-01-23
- **Breaking Change**: Customer object `cards` field retired
  - Replaced by `ListCards` and `ListGiftCards` endpoints with `customer_id` query parameter
  - `CreateCustomerCard` and `DeleteCustomerCard` endpoints deprecated (retirement date TBD)
- Node.js SDK rewritten with native fetch (replaces axios)
- Card.tokenize() method (Beta) for new payment flow

### 2024-12-18
- Customer object: `cards` field deprecation notice for 2025-01-23
- Payments API: New `buyer_phone_number` field on CreatePayment
- Payments API: New `updated_at_begin_time`, `updated_at_end_time`, `sort_field` filters on ListPayments
- TeamMember object: New `wage_setting` field (Beta)
- Terminal API: New `QR_CODE` enum value for payment_type
- CheckoutOptionsPaymentType: `PAYPAY` deprecated in favor of `QR_CODE`

## Webhook Changes

As of 2025-01-23, retry behavior changed:
- Maximum 19 retry attempts (previously different schedule)
- Retry window: up to 48 hours after event
- Applies to all API versions

## SDK Release Pattern

Square typically releases new SDK versions monthly alongside API versions, but SDK versions can be updated independently. Check the specific SDK releases for compatibility:

- **Java SDK**: https://github.com/square/square-java-sdk/releases
- **Node.js SDK**: https://github.com/square/square-nodejs-sdk/releases
- **Python SDK**: https://github.com/square/square-python-sdk/releases
- **PHP SDK**: https://packagist.org/packages/square/square

## Breaking Changes Strategy

<cite index="4-18,4-19,4-20">Breaking changes in the Square API are introduced in versioned releases (with a new major API version). Non-breaking changes can be introduced to an existing API version. The following table provides examples of breaking and non-breaking changes.</cite>

## Deprecation Timeline

- **Reader SDK**: Deprecated as of January 23, 2025; retire date December 31, 2025
  - Migrate to Mobile Payments SDK

- **Customer Cards API**: CreateCustomerCard and DeleteCustomerCard endpoints deprecated (no retirement date announced)
  - Use Cards API and Gift Cards API instead

- **Square Webhooks**: Retry schedule changed 2025-01-23 with no version dependency

## Checking Your API Version

<cite index="4-27,4-28">Each application registered in the Developer Console has a default API version, which you can view or change on the Credentials page for the production or Sandbox environment. The default API version is pinned to the application and used for all API requests unless overridden in the Square-Version header.</cite>

To override the version for a specific request, include the `Square-Version` header:
```
Square-Version: 2025-10-16
```

## Migration Guidance

When upgrading to a new API version:
1. Review release notes for breaking changes
2. Test in Sandbox environment first
3. Update SDK to version supporting the target API version
4. Update `Square-Version` headers in code
5. Test all affected endpoints thoroughly
6. Deploy to production after validation

## Note: SDK Version Lag

The Node.js SDK currently supports 2025-08-20 while the latest API version is 2025-10-16. This is normal—SDKs are released on their own schedule. The SDK still provides full access to APIs; you can override the API version using the `Square-Version` header.
