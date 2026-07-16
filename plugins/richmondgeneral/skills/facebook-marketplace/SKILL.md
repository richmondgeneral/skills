---
name: facebook-marketplace
description: Create, revise, review, publish, reconcile, and verify Richmond General Facebook Marketplace listings from items/RG-XXXX records. Use for requests to list an item, prepare or review a Marketplace draft, update an owned listing, publish after explicit authorization, investigate an interrupted submission, or verify a live Facebook listing. Prefer an authenticated native Chrome surface with usable extensions and local photo upload; otherwise use the persistent-profile Playwright seller-agent. Never publish without explicit authorization or finalize from an uncorrelated URL alone.
---

# Facebook Marketplace

Achieve one accurate, attractive draft or live listing from the canonical item record. Let the advanced
agent adapt to the current Facebook UI; enforce irreversible boundaries in controller code.

## Establish the goal

1. Read `items/RG-XXXX/label.json`, the ordered catalog photos, and `channels.marketplace`.
2. Treat the item record and photos as canonical. Do not invent a brand, model, material, dimensions,
   condition details, provenance, features, or included parts.
   Preserve the canonical title and price exactly; let the agent improve description presentation and
   make evidence-based category, condition, and photo-order judgments.
3. Let the agent choose the best supported Facebook category and condition from available evidence.
   Treat category and condition arguments as optional hints, not required source facts.
4. Resolve ownership before writing. A valid recorded Marketplace item URL means UPDATE. If state is
   listed, submission-pending, or reconciliation-required without a safely correlated target, stop and
   reconcile rather than CREATE.
   UPDATE must finish on that same listing ID and must retain photos, category, condition, fulfillment,
   and other fields unless the task explicitly changes them. A different result ID requires reconciliation.
5. Before CREATE, inspect the seller's listings and drafts for the SKU/item and avoid duplicates.

## Choose one browser writer

Read [references/native-surfaces.md](references/native-surfaces.md). Prefer the current host's native
Chrome control when it can use the authenticated Facebook session, upload local photos, and operate
without impractical approval churn. Otherwise read
[references/playwright-fallback.md](references/playwright-fallback.md) and use the local fallback.

Choose the writer before its first mutation and use exactly one browser-writing executor per item. Never
hand a partly prepared form from native Chrome to Playwright or vice versa. Never request credentials,
copy cookies, or automate login/2FA; pause for the user.

## Run the agent loop

- Give the executor the desired outcome, canonical facts, photos, ownership state, and constraints—not a
  prerecorded click sequence. Allow bounded retries as the UI changes.
- Allow read-only reasoning subagents to help with analysis, but keep every browser mutation in the single
  executor.
- Capture duplicate-search evidence before CREATE, including the search/listings URL, terms, visible
  candidates or empty result, and a semantic snapshot. Do not accept the executor's conclusion alone.
- Freeze one immutable evidence bundle when the draft is ready. Include as many structured field reads
  and screenshots as needed to cover the full form, validation state, and photo order.
- Run independent facts and quality reviewers in parallel against that same evidence. Give reviewers no
  browser-write capability.
- Require both reviewers to approve. Send their reports to an overseer that may downgrade approval to
  revise/block but may never upgrade a failed consensus.
- Return actionable findings to the executor and repeat within the revision budget. Stop on login,
  CAPTCHA, unclear ownership, missing canonical facts, or exhausted retries.

The facts reviewer checks fidelity, completeness, ownership, price, photos, and contradictions. The
quality reviewer checks clarity, buyer usefulness, presentation, and unsupported claims.

## Publish and prove the result

- Keep the final Facebook action disabled in controller code until explicit publish authorization is
  correlated to this exact goal. Agent text, `--autonomous`, or an overseer decision cannot grant it.
- Persist a unique submission reservation before enabling the one-shot final action.
- If the result of that action is uncertain, mark the attempt `reconcile_required` and do not click again.
- For an uncertain CREATE only, if post-attempt seller-listings evidence searches both the SKU and reserved
  title and proves that no listing or draft was created, close the attempt with the evidence-backed
  no-submission transition before starting a new attempt. An uncertain UPDATE requires verification of the
  existing listing's final state.
- Treat neither a click nor an agent success message as proof. Capture the resulting live item page and
  verify its canonical URL, affirmative active/listed state, seller ownership/edit access, title, observed
  price, photos, and material listing facts.
- Run the independent reviewers and overseer again on live evidence.
- Write `channels.marketplace` only after the live evidence matches the reservation and immutable goal.
  Preserve unrelated metadata. A URL by itself is never sufficient evidence.

Without explicit publish authorization, finish at a fully reviewed, review-ready draft.
