# Square API Foundational Documentation

**Latest API Version**: 2025-10-16  
**Documentation Last Updated**: December 19, 2025  
**Source**: https://developer.squareup.com

## API Overview

<cite index="14-22,14-23">The Square API follows the general patterns of REST. Applications can manage the resources (such as payments, orders, and catalog items) of a Square account by making HTTPS requests to URLs that represent those resources.</cite>

### Base Endpoints
- **Production**: `https://connect.squareup.com/v2/`
- **Sandbox**: `https://connect.squareupsandbox.com/v2/`

## API Versioning

<cite index="4-1,4-2">Square API and SDK versions are updated with every release, typically on a monthly basis. Each release uses a single Square API version number that applies to all Square APIs and might contain major, minor, and patch-level updates.</cite>

<cite index="4-24,4-25,4-26">The Square API uses a YYYY-MM-DD version-naming scheme that indicates the date the API version is released. This versioning scheme is used to control breaking changes and allows you to test newer API versions before upgrading your application. The API version applies to all Square APIs, such as the Payments API, Orders API, and Customers API.</cite>

### Version Headers
All API requests must include the Square-Version header:
```
Square-Version: 2025-10-16
```

## Authentication

### Access Tokens

<cite index="25-1,25-2">Access tokens are credentials that allow applications to securely interact with Square APIs. An access token authenticates your application and authorizes access to resources in a Square account, such as customers, orders, and payments.</cite>

Two types of access tokens:

1. **Personal Access Token** - <cite index="25-6,25-7">Provides unrestricted Square API access to resources in a Square account. You can use your personal access token in Square API calls to perform any activity on any resource in your own Square account.</cite>

2. **OAuth Access Token** - <cite index="25-8,25-9">Provides authenticated and scoped Square API access to resources in a Square account. Applications use OAuth access tokens in Square API calls to access resources on behalf of account owners.</cite>

### Authorization Header
<cite index="25-25">Access tokens are sent as bearer tokens in the Authorization header of Square API requests.</cite>

```
Authorization: Bearer {ACCESS_TOKEN}
```

## OAuth API

### Overview
<cite index="21-16,21-17,21-18">The Square OAuth API uses the OAuth 2 protocol to obtain permission from Square sellers to access specific types of resources in their account. During this process, client applications request specific permissions and receive an authorization code, which is then exchanged for an access token and refresh token. These tokens allow you to manage resources for a seller and call Square APIs on their behalf.</cite>

### OAuth Flows

<cite index="21-34,21-35">The code flow is an OAuth flow that requires a confidential client to pass in the client_id and client_secret values when redeeming an authorization code from Square. Passing these types of sensitive data requires you to use a confidential client.</cite>

<cite index="21-36,21-37,21-38">The PKCE flow is an OAuth flow for public clients that removes the need to pass the client_secret and replaces it with a code_verifier. The code_verifier is a unique string that the client application creates for every authorization request. The PKCE flow must be used by any client that cannot safely store secrets in the application, such as mobile applications, single-page applications, and native desktop applications.</cite>

### Token Expiration and Refresh

- <cite index="21-24,21-25,21-26">Square OAuth access tokens expire after 30 days. To maintain access, you must generate a new OAuth access token using the refresh token received with the original authorization. For more information about managing OAuth access tokens and refresh tokens, see OAuth API Best Practices.</cite>
- <cite index="21-27">Refresh tokens obtained using the code flow don't expire.</cite>
- <cite index="21-28">Refresh tokens obtained using the PKCE flow are single-use tokens and expire after 90 days.</cite>

### Authorization Code Expiration
<cite index="21-23">Authorization codes returned by the Square authorization page expire after 5 minutes.</cite>

## REST API Basics

### HTTP Methods
- `GET` - Retrieve resources
- `POST` - Create resources
- `PUT` - Update resources
- `DELETE` - Delete resources

### Request Headers

```
Content-Type: application/json
Authorization: Bearer {ACCESS_TOKEN}
Square-Version: 2025-10-16
```

### Idempotency

<cite index="14-13">Use Square video: introduction to idempotency for a quick multimedia tutorial of the concept.</cite>

For POST operations that create resources, include an `idempotency_key`:
```json
{
  "idempotency_key": "{UNIQUE_KEY}",
  "given_name": "Lauren",
  "family_name": "Noble"
}
```

### Pagination

<cite index="14-4,14-5,14-6,14-7">Check the cursor for list and search operations. Make sure you get all items returned in a list call by checking for the cursor value returned in the response. When you call a list or search endpoint the first time, you set the cursor to an empty string or omit it in the request. If the response contains a cursor value, you call the API again to get the next page of items using that cursor value and continue to call that API with the cursor from the previous call until a cursor isn't returned in the response.</cite>

### Query Parameters

<cite index="14-14,14-15,14-16">List operations use query string parameters to specify how to return the list of resources. For example, the ListPayments endpoint lets you filter the list of payments returned by the card brand, last four digits of the credit card, and other attributes.</cite>

## Error Handling

<cite index="14-8,14-9">Non-200 HTTP status codes are errors. For more information, see Handling Errors.</cite>

## Customers API

### Overview
<cite index="15-4,15-5">The Customers API is a RESTful web service hosted on Square servers. You can use the Customers API to create and manage customer profiles for Square sellers, including membership in customer groups.</cite>

### Key Operations
<cite index="12-18,12-19,12-20,12-21,12-22,12-23">CreateCustomer - Create a single customer profile. UpdateCustomer - Update a single customer profile. DeleteCustomer - Delete a single customer profile. BulkCreateCustomers - Create multiple customer profiles. BulkUpdateCustomers - Update multiple customer profiles. BulkDeleteCustomers - Delete multiple customer profiles.</cite>

### Best Practices
<cite index="12-24,12-25">You should avoid creating duplicate customer profiles. Before you create a new profile, call the SearchCustomers endpoint and search by phone number, email address, or reference ID to make sure a profile doesn't already exist for the customer.</cite>

### Search Filters
<cite index="12-9,12-10">The SearchCustomers endpoint doesn't support searching by name, location, or the employee who created the customer profile. For information about supported search query filters, such as email address and phone number, see Search for Customer Profiles.</cite>

### Customer Fields

**Phone Number**
- <cite index="17-5,17-6">The phone number must be valid and can contain 9–16 digits, with an optional + prefix and country code.</cite>

**Reference ID**
- <cite index="17-8,17-9">An optional second ID used to associate the customer profile with an entity in another system. The maximum length for this value is 100 characters.</cite>

**Note**
- <cite index="17-10">A custom note associated with the customer profile.</cite>

### Example: Create Customer

```bash
curl https://connect.squareup.com/v2/customers \
  -X POST \
  -H 'Square-Version: 2025-10-16' \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "given_name": "Amelia",
    "family_name": "Earhart",
    "email_address": "[email protected]",
    "phone_number": "+1-212-555-4240",
    "reference_id": "YOUR_REFERENCE_ID",
    "note": "a customer"
  }'
```

### Customer Versions
<cite index="12-1,12-2,12-3">Square also uses the version to filter events that trigger webhook notifications. If concurrent updates are made to the same customer profile, Square compares the version numbers and sends a notification for the latest version only. Similarly, if you process notifications in batches, you can use the version attribute of the Customer object in the notification to determine the latest version of an updated customer profile.</cite>

## Environments

### Sandbox
<cite index="21-12,21-13">Production is the live environment where Square sellers process real transactions and conduct business operations. The Square Sandbox is an isolated testing environment that developers can use to test integrations without affecting real users or data.</cite>

### Sandbox URL
Use `connect.squareupsandbox.com` instead of `connect.squareup.com` for all endpoints.

## SDK Availability

<cite index="13-23">Create a Square integration in PHP, Java, Python, Node.js, Ruby, .NET, and Go.</cite>

## Rate Limits

Square API rate limits are not specified in the foundational documentation. Check your Developer Dashboard for account-specific limits.

## Webhooks

<cite index="21-7,21-8">A webhook is a subscription that notifies you when a Square event occurs. For more information about using webhooks, see Square Webhooks.</cite>

## Resources

- **API Reference**: https://developer.squareup.com/reference/square
- **Developer Documentation**: https://developer.squareup.com/docs
- **Release Notes**: https://developer.squareup.com/docs/changelog/connect
- **OAuth API**: https://developer.squareup.com/docs/oauth-api/overview
- **Customers API**: https://developer.squareup.com/docs/customers-api/what-it-does
