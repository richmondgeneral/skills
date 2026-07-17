---
name: square-webhook-monitor
description: Operate Square webhook subscriptions and a local webhook monitor with signature validation. Use when creating/listing/testing Square webhooks, rotating signature keys, validating webhook integrity, or monitoring catalog/account events. Triggers on "Square webhook", "webhook subscription", "signature key", "catalog.version.updated", "webhook monitor", and "validate webhook signature".
metadata:
  version: "1.1"
  author: scottybe
  updated: "2026-02-17"
  runtime_tier: "LOCAL_STANDARD"
  required_capabilities:
    - filesystem_full_access
    - network_access
---

# Square Webhook Monitor

Operational skill for webhook lifecycle + monitoring.

Uses toolkit:

- `/Users/scottybe/workspace/square/square-tools/catalog-toolkit`

## Runtime Policy Contract

This skill is `LOCAL_STANDARD` because it manages webhook subscriptions and runs a local monitor service.

Policy references:

- `/Users/scottybe/workspace/square/square-tools/runtime/capability_matrix.json`
- `/Users/scottybe/workspace/square/square-tools/runtime/operation_policy.json`

## Use This Skill For

- listing webhook event types and current subscriptions
- creating/updating webhook operational subscriptions
- sending deterministic test webhook events
- rotating webhook signature keys
- running a local monitor endpoint with signature validation + event persistence

## Required Environment

For subscription operations:

1. `SQUARE_ACCESS_TOKEN` (or `SQUARE_TOKEN`)

For local monitor runtime:

1. `SQUARE_WEBHOOK_SIGNATURE_KEY`
2. `SQUARE_WEBHOOK_NOTIFICATION_URL`

Optional:

- `SQUARE_WEBHOOK_MONITOR_DB` — local SQLite path (default: `catalog-toolkit/data/webhook_events.db`)
- `SQUARE_WEBHOOK_MONITOR_HOST` — bind address for local monitor (default: `0.0.0.0`)
- `SQUARE_WEBHOOK_MONITOR_PORT` — port for local monitor (default: `8087`)
- `SQUARE_CATALOG_TOOLKIT_ROOT` — override toolkit path resolution

## Commands

### List event types + subscriptions

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-webhook-monitor/scripts/webhook_ops.py list
```

### Create subscription

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-webhook-monitor/scripts/webhook_ops.py create \
  --name "Catalog Monitor" \
  --notification-url "https://example.com/webhooks/square" \
  --event-type "catalog.version.updated"
```

### Test subscription

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-webhook-monitor/scripts/webhook_ops.py test \
  --subscription-id "<SUBSCRIPTION_ID>" \
  --event-type "catalog.version.updated"
```

### Rotate signature key

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-webhook-monitor/scripts/webhook_ops.py rotate-signature-key \
  --subscription-id "<SUBSCRIPTION_ID>"
```

### Run local monitor

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-webhook-monitor/scripts/webhook_ops.py run-monitor --host 0.0.0.0 --port 8087
```

Endpoints:

- `GET /healthz` — liveness check
- `GET /events?limit=50` — recent events (limit range: 1-500)
- `POST /webhooks/square` — webhook receiver with HMAC-SHA256 signature validation

All subscription commands (`list`, `create`, `test`, `rotate-signature-key`) output JSON to stdout.

## Operational Sequence (Recommended)

1. `list` to confirm existing subscriptions
2. `create` (if missing) for required event types
3. `test` to validate callback reachability
4. start `run-monitor` in process manager/terminal session
5. rotate key on schedule and update `SQUARE_WEBHOOK_SIGNATURE_KEY`

## References

- API links and event guidance: `references/webhook-api.md`
