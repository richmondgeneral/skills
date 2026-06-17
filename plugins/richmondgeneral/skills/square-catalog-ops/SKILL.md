---
name: square-catalog-ops
description: Govern Square catalog taxonomy and channel visibility with version-locked API checks. Use when merging categories, auditing cleanup state, validating site/channel assignment, or proving API-version compliance before/after catalog mutations. Triggers on "catalog cleanup", "merge categories", "audit categories", "site assignment", "compliance check", "Square-Version", or "hidden from all sites".
metadata:
  version: "1.1"
  author: scottybe
  updated: "2026-02-17"
  runtime_tier: "LOCAL_STANDARD"
  required_capabilities:
    - filesystem_full_access
    - mcp_local_tools
    - network_access
---

# Square Catalog Ops

Operational control skill for Square category governance.

This skill wraps the reusable toolkit at:

- `/Users/scottybe/workspace/square/square-tools/catalog-toolkit`

## Runtime Policy Contract

This skill is `LOCAL_STANDARD` because it performs catalog mutations and compliance checks against Square APIs.

Policy references:

- `/Users/scottybe/workspace/square/square-tools/runtime/capability_matrix.json`
- `/Users/scottybe/workspace/square/square-tools/runtime/operation_policy.json`

Use preflight before mutation steps:

```bash
/Users/scottybe/workspace/square/square-tools/bin/agent_preflight.sh --operation square_cache_sync --runtime "${SQUARE_RUNTIME_ID:-local_cli}"
```

## Use This Skill For

- Merging category sets (for example, legacy food categories -> `Food & Pantry`)
- Auditing cleanup integrity (hidden/empty legacy categories, channel assignment coverage)
- Verifying published site/channel mapping
- Proving API compliance to `Square-Version: 2026-01-22`

## Required Preconditions

1. `SQUARE_ACCESS_TOKEN` set (or fallback `SQUARE_TOKEN`)
2. Toolkit exists at default path or `SQUARE_CATALOG_TOOLKIT_ROOT` is set

## Commands

### 1) Compliance Proof

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py compliance
```

Runs REST + SDK version checks and returns docs traceability for each API call.

### 2) List Active Sites

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py list-sites
```

Returns active `ONLINE_SITE` channels and mapped domains.

### 3) Merge Legacy Food Categories

Dry-run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py merge-food
```

Apply:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py merge-food --apply
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--apply` | off (dry-run) | Apply changes instead of previewing |
| `--target-name` | `Food & Pantry` | Override target category name |

### 4) Cleanup Audit

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py audit-cleanup --fail-on-issues
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--fail-on-issues` | off | Exit non-zero if issues found |
| `--expect-new-finds-count` | `10` | Expected item count in The New Finds |
| `--json-out` | _(none)_ | Save audit results to a JSON file |

The audit verifies:

- required categories exist (`Food & Pantry`, `The General Store`, `The Vintage Market`, `New Arrivals`)
- legacy food categories are empty + hidden
- categories with items are visible and assigned to active site/POS channels
- `The New Finds` count matches expected intake cap

## Post-Mutation Workflow (Required)

After any category/visibility mutation:

1. Run cleanup audit (`audit-cleanup --fail-on-issues`)
2. Sync Square cache (`square_cache.sh sync` or `square_cache_mcp:square_cache_sync`)
3. Spot-check affected SKUs in cache

## References

- API calls and compliance links: `references/api_calls.md`
