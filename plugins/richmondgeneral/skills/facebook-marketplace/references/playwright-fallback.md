# Playwright fallback

Use `apps/seller-agent/publish_item.py` when native Chrome control is unavailable or unreliable. The local
fallback uses a persistent browser profile; the first run may require the user to complete Facebook login
or 2FA in the headed browser.

From `apps/seller-agent`:

```bash
# Resolve and validate the goal without opening Facebook.
uv run publish_item.py --item ../../items/RG-XXXX --platform facebook --dry-run

# Build and independently review a draft; do not publish.
uv run publish_item.py --item ../../items/RG-XXXX --platform facebook

# Publish only after explicit authorization for this exact item and goal.
uv run publish_item.py --item ../../items/RG-XXXX --platform facebook --yes-publish
```

`--category` and `--condition` may supply useful hints, but they are not mandatory catalog fields. The agent
must choose values supported by the item evidence and current Facebook taxonomy. Use `--replace-photos`
only when an UPDATE should replace its existing photos. `--autonomous` changes interaction behavior; it
never grants publish authority.

The fallback is a goal-driven agent loop. It uses one browser writer, parallel read-only facts and quality
reviewers, and a read-only overseer. The controller alone owns the publish gate and durable state
transitions.

For CREATE, the evidence bundle must include a captured search of the seller's listings/drafts, not only
the executor's statement that no duplicate exists. For UPDATE, the verified live item ID must equal the
recorded starting ID and unchanged fields remain intact unless the goal explicitly replaces them.

Expected safe outcomes include a reviewed draft, a verified live listing, a login/user-action pause, a
blocked result with findings, or `reconcile_required`. Never retry an uncertain final action. Never record a
bare item URL as success; final writeback requires evidence correlated to the persisted submission attempt.
