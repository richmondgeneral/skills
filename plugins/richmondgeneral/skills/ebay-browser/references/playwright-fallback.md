# Playwright fallback

Use the existing local seller-agent only after the native route in `native-surfaces.md` is unavailable or
fails its bounded retry.

## Authentication model

The publisher uses the persistent profile at `ops/seller-agent/playwright_profile/`. It requires one
headed interactive login, then reuses the saved eBay session. Never copy cookies from another profile or
ask the user to provide credentials. If the session expired, pause the headed run for user login and 2FA.

## Commands

From the local `richmondgeneral/ops/seller-agent` checkout:

```bash
# Resolve the item and prompt without opening a browser.
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay --dry-run

# Fill through the persistent profile and stop for review (safe default).
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay

# Publish only when the user explicitly authorized going live.
uv run publish_item.py --item ../../items/RG-XXXX --platform ebay --yes-publish
```

## Guardrails

- Keep CREATE/UPDATE idempotency based on `channels.ebay.url`; never load a CREATE fast path for UPDATE.
- The publisher tries a cached deterministic fast path first. If none exists, its Vision Agent fallback
  may use Gemini and incur cost/latency; this is why native browser control is preferred.
- Do not delete or reset `playwright_profile/`. Do not clear profile locks while another browser run is
  active.
- Do not interrupt a live automation unless it requests help; a half-completed CREATE may already have
  auto-saved a draft or submitted.
- Apply the same live-page verification as the native route. Neither the agent's success claim nor eBay's
  confirmation dialog proves that fields landed.
