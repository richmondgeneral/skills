# Square Catalog Ops API Calls

All operations are pinned to:

- `Square-Version: 2026-04-21`
- Release log: https://developer.squareup.com/docs/changelog/connect-logs/2026-04-21

## Core Catalog Calls

- List catalog objects: https://developer.squareup.com/reference/square/catalog-api/list-catalog
- Search catalog objects (use to LIST objects; supports `include_deleted_objects`): https://developer.squareup.com/reference/square/catalog-api/search-catalog-objects
- Batch update catalog objects: https://developer.squareup.com/reference/square/catalog-api/batch-upsert-catalog-objects
- Search catalog items: https://developer.squareup.com/reference/square/catalog-api/search-catalog-items
- Retrieve catalog object: https://developer.squareup.com/reference/square/catalog-api/retrieve-catalog-object

> ⚠️ **Catalog WRITES must be sparse.** Use the batch write with `sparse_update: true`,
> sending **only** the changed fields. A non-sparse upsert REPLACES the whole object and
> can DROP item variations (price/SKU) — always sparse, then re-verify `variations`,
> `price_money`, and `image_ids` in the response. Via the Square MCP the catalog method is
> **`batchUpdateObjects`** (there is no `batchUpsertObjects` MCP method; note the case
> quirks — `batchGetobjects`/`batchDeleteobjects` use a lowercase "o").

## Channel / Site Calls

- List channels: https://developer.squareup.com/reference/square/channels-api/list-channels
- List sites: https://developer.squareup.com/reference/square/sites-api/list-sites

## Webhook Calls

- List webhook event types: https://developer.squareup.com/reference/square/webhook-subscriptions-api/list-webhook-event-types
- List webhook subscriptions: https://developer.squareup.com/reference/square/webhook-subscriptions-api/list-webhook-subscriptions
- Create webhook subscription: https://developer.squareup.com/reference/square/webhook-subscriptions-api/create-webhook-subscription
- Test webhook subscription: https://developer.squareup.com/reference/square/webhook-subscriptions-api/test-webhook-subscription
- Rotate signature key: https://developer.squareup.com/reference/square/webhook-subscriptions-api/update-webhook-subscription-signature-key
- Webhook validation: https://developer.squareup.com/docs/webhooks/step3validate

## SDK / Versioning

- SDK overview: https://developer.squareup.com/docs/sdks
- Python SDK quickstart: https://developer.squareup.com/docs/sdks/python/quick-start
- Versioning overview: https://developer.squareup.com/docs/build-basics/versioning-overview
