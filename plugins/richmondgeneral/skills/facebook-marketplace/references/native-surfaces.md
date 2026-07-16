# Native browser route

Use the browser/computer-use capability exposed by the current desktop host when it can safely control the
user's existing authenticated Chrome session.

Common surfaces include Claude in Chrome, the Codex Chrome control plugin, and Gemini cowork/Spark browser
or computer use. Capability matters more than the product name.

## Capability check

Require all of the following before selecting the native route:

- the Facebook session is already authenticated;
- the agent can inspect and edit the listing UI;
- local catalog photos can be uploaded without opening an unmanaged native picker;
- write operations do not require impractical approval prompts for every small action; and
- screenshots or semantic page evidence can be captured for independent review.

For an unattended publish request, also require a controller-enforced final-action boundary. Decide before
the first form mutation. If native Chrome cannot withhold the final action from the executor, choose the
Playwright fallback from the start. Native Chrome remains eligible for a review-only draft or for a flow in
which the explicitly authorized user performs the reserved final click.

Use one bounded recovery attempt for a disconnected tab or stale extension state. Fall back to Playwright
when a required capability remains unavailable or repeated interaction failures make the native route
unreliable. Do not run both writers against the item.

Never copy cookies or credentials between profiles. Pause for user-controlled login, 2FA, CAPTCHA, account
checks, or other identity challenges.

## Execution contract

Give the native executor the listing goal and canonical data, not element-by-element instructions. Prefer
semantic controls when available, but allow the executor to adapt its interaction strategy to the current
page.

The same safety contract applies as with the fallback: frozen evidence, independent facts and quality
review, overseer approval, a durable pre-submit reservation, one final action, live verification, and
evidence-correlated writeback. Use `ops/seller-agent/record_verified_marketplace.py` for reservation,
reconciliation, and finalization.

Do not switch browser writers after either one has edited the form. Do not describe a prompt-only
restriction as a hard capability boundary.

For the native bridge:

1. Construct the same immutable goal used by the reviewers and hash its canonical JSON with
   `facebook_contract.compute_goal_hash`.
2. Immediately before the authorized final click, call `record_verified_marketplace.py reserve` and keep
   its `attempt_id` and goal hash.
3. On ambiguity, call `reconcile`; never repeat the click.
4. After live review, write a `VerifiedListingEvidence` JSON artifact containing the matching attempt/hash,
   canonical item URL, observed title/price/category/condition, affirmative active signal, seller ownership
   proof/method, timestamp, verifier identity, and facts/quality/overseer approvals. Pass that artifact to
   `finalize`.
5. For an uncertain CREATE only, if post-attempt seller-listings/drafts searches for the SKU and reserved
   title prove the final action produced nothing, create a `NoSubmissionEvidence` artifact and call
   `resolve-no-submission`. An uncertain UPDATE needs existing-listing state verification and cannot use
   this transition. Do not hand-edit `label.json`.

Use `record_verified_marketplace.py --help` and its subcommand help for the exact CLI arguments.
