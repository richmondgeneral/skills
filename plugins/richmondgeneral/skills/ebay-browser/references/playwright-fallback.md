# Playwright fallback

Use the local seller-agent only after the native route in `native-surfaces.md` is unavailable or fails
its bounded retry.

## Authentication model

Persistent profile: `apps/seller-agent/playwright_profile/`. One headed interactive login, then reuse.
Never copy cookies from another profile or ask for credentials. If expired, pause for user login + 2FA.

## Shared UI helpers

`apps/seller-agent/ebay_ui.py` implements driver-side settle/fill/verify helpers used by fast paths:

- Hang URL detection (reject `keyword=` Active deep-links, ReviseItem deep-links)
- `fill_and_verify` / `click_revise_or_list` patterns
- Live item page price/title reads for post-submit proof

Fast paths:

| Module | Role |
|---|---|
| `fast_paths/ebay_UPDATE_fast_path.py` | UPDATE revise with live verification |
| `fast_paths/ebay_CREATE_fast_path.py` | CREATE happy path (pickup-oriented); draft-safe |

The main `publish_item.py` orchestrator uses the reviewed Vision agent loop; fast paths are the
**deterministic** entry when invoked explicitly or re-wired by the orchestrator. Prefer them over
ad-hoc scripts.

## Commands

From `richmondgeneral/apps/seller-agent`:

```bash
# Resolve the item and goal without opening a browser.
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay --dry-run

# Deterministic fast path first (UPDATE live-verifies; CREATE stops before List it
# unless --yes-publish). Falls back to Vision agent unless --fast-path-only.
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay

# Fast path only (no Vision fallback) — good for smoke:
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay --fast-path-only

# Skip fast path; Vision agent loop only:
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay --force-agent

# CREATE/List it only when the user explicitly authorized going live.
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay --yes-publish --fast-path-only

# Non-destructive Seller Hub probe (Active, End listings labels, hang guards):
uv run python ebay_smoke_probe.py

# Unit tests for pure ebay_ui helpers (no browser):
uv run python test_ebay_ui.py

# Headless e2e against mock Seller Hub (no credentials):
uv run python tests/test_ebay_e2e.py
```

## Guardrails

- CREATE vs UPDATE from `channels.ebay.url`; never run CREATE when an owned URL exists without
  Active+Drafts reconcile.
- Do not delete or reset `playwright_profile/` while a run is active.
- Do not interrupt a live automation unless it requests help; half-completed CREATE may have auto-saved
  a draft or submitted.
- Apply the same live-page verification as native: **dialog is not proof**.
- On uncertainty: mark reconcile; never re-click List it / Revise it.
