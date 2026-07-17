# eBay Seller Hub — failure matrix

Symptom → cause → agent action. Pair with the Mandatory Field Edit Protocol in `SKILL.md`.

Last updated: 2026-07-16.

| Symptom | Likely cause | Action |
|---|---|---|
| Typed title/price but field still shows old value | Keystroke swallow after form render; ref-click never focused | Screenshot → coordinate-click field → clear → retype → zoom-verify. 2nd try usually lands. Do **not** submit until read-back matches. |
| "Your listing has been revised" but live `/itm` unchanged | Dialog is a soft signal only; form submitted stale values | Treat as **failed edit**. Re-open Revise via Seller Hub (not deep-link). Mandatory Protocol on each field. Verify live again. |
| Active row still shows old price after successful revise | Stale Seller Hub grid | Ignore row price. Trust live `/itm` only. |
| Tab frozen; CDP/browser tools time out | Hang after deep-link or mid-submit renderer freeze | Open **fresh tab**. Do not re-click List/Revise on frozen tab. Reconcile Active + Drafts for the SKU/title. |
| Navigation to `/sh/lst/active?keyword=…` hangs | Deep-link hang class (`document_idle`) | Use plain `/sh/lst/active` only; type into search box after load. |
| ReviseItem / `mode=ReviseItem&itemId=` hang | Deep-link hang class | Enter via Active → search → **Edit**. |
| `find` → click **Revise it** scrolls but does not submit | Ref-click does not fire on that control | Scroll into view → **coordinate-click** blue button (~center bottom of form at ~1290px viewport). Wait 7s for dialog. |
| Search box empty after typing item number | Post-Done re-render swallow | Re-click search → retype → screenshot-verify before Edit. |
| "List it" freezes after click; no dialog | Submit may have succeeded; renderer died | **Do not** click List it again. Fresh tab → Active search title/SKU. If listed, capture ID and verify live. If Drafts only, resume draft. |
| Login / 2FA page | Session expired | Stop. Ask user to sign in + 2FA. Never ask for password. Resume after they confirm. |
| Wrong category / item specifics from eBay.ai | Photo+title suggestions | Do not blind "Apply all". Check each chip; override Brand/Color/etc. |
| Photo upload no-op | File input lost between batches; path not absolute | Reacquire `input[type=file]`; use absolute paths; batch &lt; ~10 MB. |
| Description "updated" but body empty | Wrote Condition description textarea instead of RTE | REVISE: iframe `se-rte-frame__summary`. CREATE: inline contenteditable. Verify visually. |
| JS read of title returns `"on"` | Broad selector matched a checkbox | Read exact ref from find, or screenshot/zoom — do not trust broad `querySelector`. |
| Duplicate listing after retry | Second CREATE after uncertain first submit | Always Active + Drafts search first. Uncertain outcome → reconcile, never re-List. |
| Inventory API listing cannot open in Seller Hub edit | Browser cannot revise API-managed offers | Use `ebay-lister` when `offer_id` present. |
| Playwright TargetClosedError / headed die over bridge | Headed launch over osascript bridge | Use headless for profile fetch tools; clear stale `playwright_profile/Singleton*` only when no run is active. |
| Native Chrome tools missing in this agent host | Host has no Chrome MCP/plugin | Fall back to Playwright per `playwright-fallback.md`, or hand off to Claude/Codex/Gemini with Chrome. |

## Severity triage

- **Stop immediately:** login page, unknown publish authorization, dual writers (native + Playwright) on same listing.
- **Reconcile before any click:** frozen tab after List/Revise, ambiguous dialog, duplicate risk.
- **Retry with protocol:** swallowed keystrokes, failed ref-click submit (once), search swallow.
- **Escalate to user:** 2FA, captcha, policy names missing, category ambiguous.
