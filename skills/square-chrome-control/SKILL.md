---
name: square-chrome-control
description: Privileged Chrome automation for Square dashboard with allowlisted JavaScript actions and controlled CSS/script injection. Use when operating browser-side Square workflows that require local app runtime, Chrome tab control, and injected action execution. Triggers on "Square Chrome control", "inject script", "execute Square action", "browser-side automation", "click selector", and "set SEO fields in dashboard".
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-17"
  runtime_tier: "LOCAL_PRIVILEGED"
  required_capabilities:
    - chrome_control
    - js_injection
---

# Square Chrome Control

Privileged skill for browser-side Square operations that cannot be completed via REST APIs alone.

## Runtime Contract

This skill is restricted to `LOCAL_PRIVILEGED` runtime.

Policy references:

- `/Users/scottybe/workspace/square/square-tools/runtime/capability_matrix.json`
- `/Users/scottybe/workspace/square/square-tools/runtime/operation_policy.json`

Preflight examples:

```bash
/Users/scottybe/workspace/square/square-tools/bin/agent_preflight.sh --operation chrome_execute_script --runtime "${SQUARE_RUNTIME_ID:-local_cli}"
/Users/scottybe/workspace/square/square-tools/bin/agent_preflight.sh --operation chrome_insert_css --runtime "${SQUARE_RUNTIME_ID:-local_cli}"
```

## Implementation Targets

Use these extension files as the source of truth:

- `/Users/scottybe/workspace/square/square-chrome-extension/src/utils/chromeApiTools.ts`
- `/Users/scottybe/workspace/square/square-chrome-extension/src/types/scriptActions.ts`
- `/Users/scottybe/workspace/square/square-chrome-extension/manifest.json`

## Allowlisted Action Model

Only these actions are allowed through `executeScript`:

- `getPageInfo`
- `extractItemFields`
- `setSeoFields`
- `clickSelector`
- `insertCssClass`

Do not add free-form JavaScript execution.

## Safety Rules

- Never downgrade to broad host permissions.
- Never add `eval` or equivalent dynamic execution in extension tooling.
- If runtime profile is absent or invalid, treat environment as `WEB_SAFE` and fail closed.
