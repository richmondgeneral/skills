# Richmond General — Public / Private Boundary

**Status:** Spec (concept-first). No files moved yet. Establishes the framework-vs-instance boundary the monorepo restructure will physically realize later.
**Companion:** monorepo design `2026-06-18-richmondgeneral-monorepo-design.md` (§2 posture, §5 seam, §6 layout).

## Why this exists

Richmond General is, at once, three things:
1. **A private operation** with real data (items, finances, contacts, real estate, secrets).
2. **A résumé / portfolio** — the *progress* is the demonstration. Default to building in the open.
3. **A source of reusable pieces** for other small Square retailers — the genuinely-generic skills, maybe an open-source Square app — *if/when* extracted. **Not** a turnkey "store in a box" product.

So the architecture splits along **framework (public) vs instance (private)** — not along repos or "storefront vs finance."

## Framework — public, open-by-default

The reusable, genericizable, showcase-able layer. **No real data, no secrets.**
- `item_model` core: models, page reader/writer, channel registry, diff engine, channel adapters.
- `rg-reconcile` (read/heal) + `rg-set-price` write-path.
- The generic skills, templates, item-card template, architecture docs, plans.
- Brand *as example/template* (not the private specifics).

Genericized via the **seam** (below): another Square merchant overrides `instance_config` via env and supplies their own token — the framework code is instance-agnostic.

## Instance — private

The operator's actual data + the personal verticals. Never public.
- Real item content/data, the live `items/` page content (public *site*, but the data is the operator's).
- `ops/` — finances, ROI, lot costs, internal reports.
- Contacts / CRM data, iMessage history.
- Real-estate and personal verticals (entirely instance — not part of the public product).
- Secrets: `.env`, macOS Keychain.
- Eventual physical home: a `.instance/` subtree (gitignored) or a separate private repo.

## The seam — `item_model/instance.py`

The **single point** where framework code reads per-instance config + secrets:
- `resolve_square_token()` — env → macOS Keychain → workspace `.env` (works over the osascript bridge's bare shell).
- `load_instance_config() -> InstanceConfig(location_id, merchant_id, pages_base, items_dir)` — env with RG defaults; override via env to genericize.

Everything downstream (reconcile, write-path, Square adapter) is instance-agnostic and routes through this seam. Adopted by the `item_model` system in Phase 2a; the older skills migrate onto it later.

## Licensing posture

- **Open by default.** The visible build history is the portfolio.
- **No outside contributions until released + stable** (far off) — a `CONTRIBUTING.md` will say so explicitly.
- **MIT / Apache-2.0** on the genuinely-reusable pieces (the best skills, a possible open-source Square app); the main repo source-available pre-release.
- Public position = *proof it can be done* + a home for extractable pieces. Not a product for sale.

## Remaining instance-config touchpoints (deferred migration)

The framework boundary is enforced for the `item_model` system today. The **older skills still hardcode instance values** and must migrate onto the seam before a clean public/private split:
- `B87BAEZ0NWV34` (location) — ~28 occurrences across `rg-full-auto`, `square-*`, etc.
- `7MM9AFJAD0XHW` (merchant) — ~5.
- `richmondgeneral.github.io` (pages base) — ~9.
- `/Users/scottybe/workspace/...` absolute paths.

These overlap the **actively-edited intake code**, so migration is deliberately deferred (time it so it doesn't collide).

## Deferred (later Phase 2)
- Physical reorg into `core/ domains/ capabilities/ .instance` (design §6).
- Migrate the older skills' hardcoded instance config onto the seam.
- Create the `.instance` private split (gitignored subtree or private repo).
- Add the actual `LICENSE` + `CONTRIBUTING.md` files.
