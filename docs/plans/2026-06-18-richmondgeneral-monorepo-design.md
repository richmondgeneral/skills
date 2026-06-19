# Richmond General — Monorepo & Inventory-Consistency Design

**Date:** 2026-06-18
**Status:** Design (validated via brainstorming). Implementation plan follows (store-first).
**Trigger:** A live Square reconciliation sweep surfaced systemic drift (pages ↔ Square ↔ index ↔ channels falling out of sync, with no mechanism to detect or prevent it), plus skill/script rot and two-runtime divergence. Rather than hand-fix repeatedly, we step back to a system design.

---

## 1. North star — what Richmond General *is*

Richmond General is **not a store; it is the umbrella for the whole operation** — a personal + business operating system. The retail store is one domain.

**Verticals (what RG does):**
- 🛍️ **Commerce / Retail** — intake → storefront → channels → sale → ROI. Brands: The Violet Moon · Richmond General · Snacks. *The flagship and the first priority.*
- 🏠 **Real Estate** — its own vertical.
- 🙋 **Personal** — the operator's own life-ops.

**Horizontal capabilities (shared services any vertical uses):**
- 🤝 **CRM / contacts** — personal + real estate + retail (not retail-owned).
- 💬 **Comms / iMessage** — fully generic.
- 📅 **Daily Brief** — aggregates across verticals.
- 🔎 **Appraisal** — books / carnival glass / maker's marks; feeds Commerce intake.
- 🎨 **Brand & Content** + 🖼️ **Image processing**.
- ⚙️ **Platform** — skills/plugins library, Mac↔Cowork bridge, env/secrets, launchd automation, reconcile/governance tooling.

**Explicitly OUT of scope:** 📈 **Trading** (`alpha-trader`, `alpaca-*`) is a *separate project* → relocate to `/Users/scottybe/workspace/AlphaTrade`.

---

## 2. Purpose & posture (résumé + eventual product, store first)

RG is simultaneously: **(a)** the operator's private operation with real data, **(b)** a public résumé/portfolio — *the progress is the résumé*, and **(c)** potentially a source of reusable pieces for other small Square retailers.

Decisions:
- **Store first.** Priority #1 is an *operating store* (Commerce end-to-end). Productization and other verticals wait. **The restructure must not block the store.**
- **Default open.** Public-by-default code/framework/skills/docs, properly licensed. The visible build history is the portfolio.
- **No contributions until released + stable** (far off). License/`CONTRIBUTING` reflect "view & learn, rights reserved, contributions closed for now." Likely MIT/Apache-2.0 on the genuinely-reusable pieces (best skills, a possible open-source Square app); main repo source-available pre-release.
- **Not "general store in a box."** The public repo is *proof it can be done* + a home for extractable reusable pieces — **not** a turnkey product. We do **not** build multi-tenant now.
- **Seams, not a split.** Keep real private data out, and keep instance config in one place so a framework/instance extraction is *possible later*. Building those seams **is** the rot cleanup (see §5).

**Public vs private collapses to:** default-open **code**; **private data externalized** — secrets (already), finances/ROI, contacts, real-estate & personal data, comms history.

---

## 3. Data model & field authority (the Commerce core)

The logical entity is an **Item**, keyed by **SKU**. The **page** (`items/RG-XXXX/`) is the universal record — it exists for every item, even ones that sell off-Square. **Square / Whatnot / eBay / Marketplace are per-item channels**; each item records which channels it is actually on.

| Field | Owner | Reconcile behavior |
|---|---|---|
| SKU identity | **page** (spine) | every channel listing must map back to a page SKU; flag orphans |
| Reference / asking price | **page** (`label.json`) | baseline only |
| Per-channel price | **each channel** | flag divergence from reference **only when unintended**; never auto-equalize |
| Reference type/classification | **page** | maps to each channel's own taxonomy |
| Per-channel category | **each channel** | not forced equal (Square ≠ Whatnot ≠ eBay) |
| **Availability / sold-state** | **page = canonical lifecycle, GLOBAL** | **highest-priority invariant:** sold on *any* channel ⇒ sold/unlisted on *all* channels + page. Prevents double-selling a unique item |
| Narrative / condition / photos | **page** | never overwritten from a channel |
| Cost / lot / ROI | **ops** (private) | untouched by reconcile |
| Snapshot / index | **derived** | regenerated from reality; never hand-authored |

**Two mechanisms:**
1. **Intended-vs-unintended price divergence** — `label.json` carries an optional per-channel intended-price map. Reconcile flags any channel price ≠ reference that isn't recorded as intended → operator accepts-as-intended (recorded, stops flagging) or fixes. This formalizes the judgment calls made during the 2026-06-18 sweep.
2. **Channel state lives in the `channels` registry** (CLAUDE.md operating rule) — the single per-channel record (`channels.<chan>.status` + platform IDs, the upsert idempotency key). `item_model.listed_on` is a **derived view** of it (sales channels whose status ∈ `LISTED_STATUSES`, excluding `github_page`), not a separately-authored field. `sold` is **unified** across `status.json`, item `state ∈ {Sold, Archived}`, and any channel `status == sold`. **Presence** findings (INFO) fire only for a listed channel an adapter actually *checked* and found absent — never for channels with no adapter (marketplace/eBay), so "not checked" is never misreported as "absent."

**Canonical `label.json` channel schema (implemented in Slice B):** item-level `state` ∈ {Acquired, In Intake, Priced, Listed, Sold, Archived}; `channels: {<chan>: {status, …platform ids}}`, `<chan>` ∈ {square, whatnot, ebay, marketplace, github_page}; per-channel `status` ∈ {not_listed, pending, listed, sold, ended} with `LISTED_STATUSES = {listed, active, live}`; `intended_channel_prices` a distinct top-level map. Legacy minimal `label.json` (no registry) stays valid — `listed_on` derives empty. `item_model` reads this via `page_reader` + `channel_registry`; `page_writer` merge-maintains it (preserves platform IDs, never downgrades a sold channel).

Retire the ad-hoc `catalog_index.jsonl` (undefined `t` field, no generator) in favor of a defined, regenerated `catalog_state.json` owned by the reconcile tool. Default market tier for newly-created items is **"New Arrivals."** Categorize by **type** (= reporting category) + market tier; the legacy "every item in Timeless Treasures + New Finds" rule is wrong (0 live matches) and must die at its source.

---

## 4. The reconcile system (on-demand) + shared core

Three tools over **one shared "item model" module**, so intake / update / reconcile never diverge:

- **Shared core — `item-model`.** Knows how to (i) read an item's state from each channel, (ii) write/project a field to a channel, (iii) read/write the page record. Channel adapters: Square (API, full), Whatnot (CSV/chrome), eBay, **Marketplace (computer-use only on the Mac)**.
- **`rg-reconcile` (read & heal).** Walk the spine (pages) → gather reality from each item's channels → diff against §3 in priority order (sold-state → price-vs-reference → orphans → snapshot) → report to `ops/reports/` → heal only with `--heal` + dry-run + confirm; never touches page narrative.
- **Write helper (extends `safe_batch_reprice.py`).** The *one* path for commercial changes: "set price/state for SKU on channel(s)" → writes channel(s) + records page reference / intended-override + regenerates snapshot. Reuses the sweep's retrieve-modify-upsert safety (full-object preserve, dry-run, idempotency).
- **Intake (`process_batch.py`)** calls the same core to **create** items (page spine + listed-on + reference price + per-channel listings). This is the batch-intake work currently in progress — it must be built on the shared core.

**Error handling:** per-item isolation (one channel error → collect + report, never abort the batch). Production writes always dry-run → confirm. Adapters degrade gracefully (Marketplace unavailable ⇒ flag "manual", don't fail).

---

## 5. Seams = the cleanup (instance config extraction)

The skills hardcode instance config (`B87BAEZ0NWV34`, `7MM9AFJAD0XHW`, `/Users/scottybe/...`, brand specifics). Extracting that into a single **instance-config interface** (injected, not hardcoded) is simultaneously:
- the "make it genericizable later" seam (framework vs instance), and
- the fix for the rot in `rg-full-auto-review.md` (broken SKU-verify, hardcoded category IDs, dual-category assignment, stale timestamps, path mismatches) and the duplicated legacy `process_new_item.py` copies that still carry the dead category rule.

---

## 6. Target monorepo layout (north-star — refined during restructure, executed store-first)

Concept-first: this is the *direction*, not a big-bang migration. Principles are firm; the exact tree evolves.

```
richmondgeneral/                  # public-by-default monorepo
├── README.md / LICENSE / CONTRIBUTING.md   # the manifest (public), licensing, "no contrib yet"
├── manifest/                     # domain manifest, architecture, ADRs
├── core/                         # shared spine
│   ├── item-model/               # read/write/project an item across channels
│   ├── channels/                 # square · whatnot · ebay · marketplace adapters
│   └── instance-config/          # THE SEAM: location/merchant/paths/brand — injected
├── domains/
│   ├── commerce/                 # intake (batch) · reconcile · storefront generator
│   ├── appraisal/
│   ├── real-estate/              # code public, data private
│   └── personal/                 # code public, data private
├── capabilities/                 # crm · comms(imessage) · daily-brief · image · brand
├── platform/                     # skills/plugins packaging · mac-bridge · runtimes · automation
├── apps/storefront/              # the public Pages site (items) — published subtree
└── .instance/                    # GITIGNORED or private submodule: real data, secrets, finances, contacts, RE, personal
```

**Maps from today's 5 repos:** `items`→`apps/storefront` + `domains/commerce/storefront` · `ops`→`.instance` (finance/records) · `skills`→`platform`+`domains`+`capabilities` · `plugins`→`platform` · `brand`→`capabilities/brand` (public template) + `.instance` (private specifics) · root loose state→`core`/`platform`/`.instance`.

---

## 7. Execution sequencing — STORE FIRST

- **Phase 1 — Operating store (now).** Build the shared `item-model` core + Square/Whatnot adapters; land `rg-reconcile` (read/heal) and the write helper; put batch intake on the core; kill the dead category rule + the store-blocking rot; retire `catalog_index.jsonl` → `catalog_state.json`. Outcome: Commerce runs end-to-end, drift is detectable/healable, intake is reliable. **No monorepo migration required for this phase** — build the core/seam in place.
  - **Slice A — DONE.** `item-model` core (models, page reader, diff engine), Square + Whatnot read adapters, `rg-reconcile` read-only CLI + report, presence reconciliation (`listed_on`).
  - **Slice B — DONE.** Canonical `label.json` channel registry: registry helpers + reader derivation, `page_writer` merge-maintain (preserves platform IDs, never downgrades a sold channel), schema documented.
  - **Slice C — DONE (write-path + safe heal).** `catalog_state.json` snapshot (always written by `reconcile.py main()`, retiring `catalog_index.jsonl`); `rg-set-price` write-path; `rg-reconcile --heal` (SAFE, page-side only — (re)writes the snapshot and prints per-finding guidance routing each drift to the right confirmed tool: `rg-set-price`, `rg-item-mark-sold`, or "verify the listing"; **no production channel writes**).
    - *Deferred (not blocking the store):* auto-record-intended-price on confirm (currently the operator records an intended override by hand); full production auto-heal (apply fixes to live channels, not just route to tools); Whatnot CSV write-back (reconcile reads the Whatnot CSV but doesn't yet write corrections to it).
- **Phase 2 — Restructure toward the manifest.** Introduce `core/instance-config` seam fully; reorganize toward §6; establish the public/private boundary (`.instance`); licensing + README/CONTRIBUTING.
- **Phase 3 — Genericize & share.** Extract reusable skills / possible open-source Square app; make the public repo a clean demonstration.
- **Phase 4 — Other verticals.** Real Estate, Personal, cross-vertical capabilities (CRM/daily-brief) formalized.

---

## 8. Carried-over open items (from the 2026-06-18 sweep)
- **RG-0009 payment link** — order-based link charges $44.99 vs the now-$95 listing, mislabeled "RG-0008." Needs decision: mint new $95 link + regenerate QR/buy-button, or leave (task #9). *Exactly the sold-state/price global-invariant the system is meant to enforce.*
- **Cache MCP** — preflight fix staged in `~/.config/claude-mcp/bin/start-square-cache-mcp.sh`; confirm healthy after app/session restart.
- **AlphaTrade relocation** — move trading out (task #16).

## 9. Deferred backlog (not blocking the store)
- Full image-pipeline consolidation (local vs Cowork divergence beyond what the store needs).
- SKU-scheme unification (`RG-00XX` vs `RG-TOY-*` vs `RG-APPAREL-*`) + page coverage for the 4 RG + 58 vendor items.
- The non-store-blocking items from `rg-full-auto-review.md`.
- Two-runtime doc reconciliation beyond the instance-config seam.
