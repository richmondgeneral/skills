# Intake Photo Sorter + Downloads Router — Design

**Date:** 2026-06-19 · **Author:** scottybe · **Skill:** `photos-library` (extended, no new skill)

## Problem

Two related needs:

1. **Sorter** — get the photos sitting in the **"Richmond General Intake"** Photos album (24 as of
   2026-06-19) *out* of Intake and into each item's "SKU lib": the per-SKU Photos album
   (`RG-XXXX` under the **"Richmond General"** folder) **and** the filesystem `items/RG-XXXX/` folder.
2. **Downloads router** — a way to add photos sitting in `~/Downloads` into the proper Photos album.

Constraints surfaced while brainstorming: the folders **and** albums must stay in sync ("manage them
correctly"), and the **Intake album must end up clear** (it is the unprocessed queue).

## Decisions (brainstorming 2026-06-19)

| Question | Decision |
|---|---|
| How do intake photos map to items? | **Shot item-by-item** → consecutive timestamps cluster cleanly per item. |
| Where does a SKU's photos live? | **Both** the per-SKU Photos album **and** `items/RG-XXXX/`. |
| New vs existing items? | **Mix** — per cluster, assign an existing SKU or mint a new one. |
| Review UX? | **Agent loop** — the agent clusters, *looks at* the photos, proposes assignments; deterministic scripts execute the irreversible parts. |
| Downloads routing? | **Agent decides per photo** (vision): product → Intake (or matching SKU); non-product → leave alone. |
| Home for the code? | **Extend `photos-library`** — one canonical filing path, no new/parallel skill. |
| Keep Intake clear? | **Tag + queue-filter (soft delete).** Filing tags `rg-sorted`; the intake scan runs with `--hide-sorted` so sorted photos drop out of the queue. PhotoKit remove (denied) and AppleScript album rebuild (async-delete → duplicate albums → broken refs) were both tried and **rejected**. Physical photos stay in Intake until mass-deleted by hand. |

## Architecture

**Model (both flows): the agent is the brain, deterministic scripts are the hands.** The agent
clusters, renders photos to look at them, matches against existing items, and proposes assignments;
scripts perform everything irreversible (mint SKU, import, move/export files, clear Intake) only after
per-cluster confirmation.

**One canonical filing path.** A single `file_cluster.py` is the *only* thing that moves item photos
between Photos albums and `items/`. The intake sorter and the downloads router both call it; later
`rg-full-auto` / `rg-item-update` can adopt it too (follow-up, not this build). One implementation ⇒
folder and album cannot drift.

## Flow A — Intake → SKU lib (agent loop)

1. **Cluster** — `find_product_clusters.py --album "Richmond General Intake"` → time-gap groups.
2. **See** — extract each cluster to downscaled temp JPEGs (`extract_photos.py --uuids …`); agent
   `Read`s them (real vision). Offloaded originals are reported, not skipped.
3. **Match + propose** — agent cross-references `items/RG-XXXX/` heroes + `label.json`s and proposes
   per cluster: *matches RG-00NN → add as details* **or** *new item → mint next RG-XXXX*, with a reason.
4. **Confirm** — user accepts / picks a different SKU / skips, per cluster.
5. **File** — `file_cluster.py --sku RG-XXXX --uuids … [--mint] [--role uuid=hero|detail-back|…]`
   (see contract below). Idempotent; clears the photos out of Intake.

## Flow B — Downloads → proper album (agent decides per photo)

1. **Scan** `~/Downloads` for images; HEIC → temp JPEG so the agent can view them.
2. **Route** — agent looks at each and proposes: product shot → **Intake** album (or, if it clearly
   matches a live SKU, that SKU's album directly via Flow A's filing); non-product → leave alone.
3. **Confirm** the routing.
4. **Import** — `import_to_photos.scpt <album> <files…>` imports into Photos + adds to the chosen
   album (creating it under the "Richmond General" folder if needed), returns new UUIDs. Product
   imports land in Intake → Flow A takes over.

## `file_cluster.py` — contract & guarantees

Input: a SKU (or `--mint`), the photo UUIDs, optional per-UUID roles the agent assigns by looking.

1. **Mint if new** — `sku_authority.py allocate` (atomic Square-CAS; hard-fails if Square unreachable
   — never a colliding local fallback). Else use the given existing SKU.
2. **Filesystem** — ensure `items/RG-XXXX/`; write `hero.jpeg` + `detail-*.jpeg` via `sips`.
   **Never clobber** an existing hero (append `detail-N`); keep `label.json` consistent (stub if new).
3. **Album** — ensure `RG-XXXX` album under the "Richmond General" folder; `add` the photos
   (idempotent — Photos dedupes album membership).
4. **Tag** — set keywords to include `rg-sorted` + `RG-XXXX` (AppleScript; preserves existing
   keywords). This is what `find_product_clusters.py --hide-sorted` filters on to drop the photo
   out of the intake queue (no album mutation).
5. **Report** exactly what moved where; safe to re-run.

## Keeping Intake clear (FINAL mechanism — tag + queue-filter, 2026-06-19)

Two structural approaches were tried and **rejected**:
1. **PhotoKit remove** (true per-asset remove-from-album) — a bare `swift script.swift` has no
   Info.plist usage description, so `requestAuthorization` returns `.denied` (status 2) with no prompt.
2. **AppleScript delete+recreate the Intake album** — Photos' album deletion is **asynchronous**
   (sets `trashed`, lingers), so recreating the same name immediately creates **duplicate albums**
   that break all name-based references (`-1728`). Verified the hard way (9 phantom `__rg_*` rows).

What **does** work reliably is keyword **writing** (verified) and **reading at the DB level**. So
"out of Intake" is a **soft delete / queue filter**, not a structural mutation:

- **Tag (per cluster):** `file_cluster.py` writes keywords `rg-sorted` + `RG-XXXX` on each filed
  photo via AppleScript (preserves existing keywords). Reliable, reversible, an audit trail.
- **Queue filter:** `find_product_clusters.py --hide-sorted` (→ `exclude_keyword_condition` in
  `photos_db.py`, a parameterized `NOT IN` on the keyword join) excludes `rg-sorted` photos from the
  intake scan. Once filed, a photo drops out of the sorter's view of the queue — reliably, at the
  read-only DB layer, with **no album mutation at all**.
- **Physical cleanup:** the photos stay visible in the Intake album until the user periodically
  mass-selects the `rg-sorted` ones and removes them by hand in Photos. (Photos offers no reliable
  scripted remove-from-album; this is the accepted tradeoff.)
- **Safety:** a mis-tag only hides a photo from the queue view (it stays in the library + its SKU
  album, fully searchable) — never data loss.

## Components

- **Reused (exist):** `find_product_clusters.py`, `extract_photos.py`, `archive_to_album.scpt`,
  `photos_db.py`, `sku_authority.py` (in `rg-full-auto/scripts/`).
- **New (in `photos-library/scripts/`):**
  - `file_cluster.py` — canonical filing (mint? + items/ export + album add + `rg-sorted` tag).
  - `find_product_clusters.py --hide-sorted` + `exclude_keyword_condition` (photos_db.py) — the
    queue-filter that hides sorted photos (replaces the rejected `clear_intake.scpt` rebuild).
  - `import_to_photos.scpt` — Downloads → Photos album.
  - `extract_photos.py` gains `--uuids` (render one specific cluster for the agent's eyes).
- **`SKILL.md`** — agent-loop playbook for both flows; expand triggers ("sort intake", "file into
  SKU", "downloads → album", "clear the intake album").

## Safety / error handling

- **Read-only Photos DB** (`mode=ro&immutable=1`) for all queries — never disturbs iCloud sync (v1.3).
- **Offloaded originals** reported with download guidance; never silently dropped before filing.
- **Irreversible actions** (mint, import, file, Intake-remove) run only after per-cluster confirmation.
- **Idempotent** — re-runs don't double-import (album dedupes) or clobber existing `items/` photos.
- **Minting** is atomic and hard-fails offline (no cross-machine collision).

## Testing

- **Auth spike first** — confirm `intake_remove.swift` can remove an asset from a throwaway album.
- **`--plan` dry-run** on `file_cluster.py` — print what *would* move, no mutations.
- **Unit:** path / no-clobber / role-mapping logic against a temp `items/` dir.
- **End-to-end** on ONE safe cluster from the real 24-photo Intake album before the full pass.

## Deployment

Source in the workspace skills repo (`richmondgeneral/skills`, on `main`); after editing, mirror to
the plugin cache (`rsync -a --exclude=__pycache__`) per the dual-copy rule. Commit per-repo, stage
explicit paths (never `git add -A`), re-verify branch + `main` immediately before any commit/push.

## Out of scope / follow-ups

- Migrating `rg-full-auto` Phase 1–2 and `rg-item-update`'s add-image path to call `file_cluster.py`
  (adopt the canonical path so they inherit folder+album correctness + Intake-clear). Later.
- Auto-semantic detail naming beyond what the agent assigns by looking (e.g. ML back/mark detection).
