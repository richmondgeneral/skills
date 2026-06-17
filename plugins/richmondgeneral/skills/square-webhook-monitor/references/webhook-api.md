# Square Webhook API References

## Subscription APIs

- Event types: https://developer.squareup.com/reference/square/webhook-subscriptions-api/list-webhook-event-types
- Subscriptions list: https://developer.squareup.com/reference/square/webhook-subscriptions-api/list-webhook-subscriptions
- Create subscription: https://developer.squareup.com/reference/square/webhook-subscriptions-api/create-webhook-subscription
- Test subscription: https://developer.squareup.com/reference/square/webhook-subscriptions-api/test-webhook-subscription
- Rotate signature key: https://developer.squareup.com/reference/square/webhook-subscriptions-api/update-webhook-subscription-signature-key

## Signature Validation

- Webhook validation guide: https://developer.squareup.com/docs/webhooks/step3validate
- Webhook overview: https://developer.squareup.com/docs/webhooks/overview

## Versioning and SDK

- Versioning: https://developer.squareup.com/docs/build-basics/versioning-overview
- SDK overview: https://developer.squareup.com/docs/sdks
- Python SDK quickstart: https://developer.squareup.com/docs/sdks/python/quick-start

## Recommended Events

- `catalog.version.updated`
- `inventory.count.updated`
- `order.created`
- `payment.created`

Select only events needed by your workflow to reduce webhook noise.
