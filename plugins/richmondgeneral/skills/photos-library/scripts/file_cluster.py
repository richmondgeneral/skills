#!/usr/bin/env python3
"""Canonical filing for the intake photo sorter.

Given a SKU (or ``--mint``) and a cluster of Photos ``ZUUID``s, file those photos
into an item's "SKU lib": export originals into ``items/RG-XXXX/`` (hero + details,
never clobbering an existing hero), add them to the per-SKU Photos album under the
"Richmond General" folder, and tag them ``rg-sorted``/``RG-XXXX`` so the separate
``clear_intake.scpt`` finalize can rebuild the Intake album with only unsorted photos.

This module is the ONE thing that moves item photos between Photos albums and the
filesystem, so the two surfaces cannot drift. The pure logic below (SKU resolution,
no-clobber filename planning, label stubbing) is unit-tested; the Photos/sips side
effects live in the integration section and are skipped by ``--plan``.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys

import photos_db
from photos_db import wipe_gps_jpeg

RG_RE = re.compile(r"^RG-\d{4}$")
UUID_RE = re.compile(r"^[0-9A-Fa-f-]{8,}$")  # ZUUIDs are hex + hyphens — safe to embed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_SCPT = os.path.join(SCRIPT_DIR, "archive_to_album.scpt")
SKU_AUTHORITY = os.path.join(SCRIPT_DIR, "..", "..", "rg-full-auto", "scripts", "sku_authority.py")
LIBRARY = os.path.expanduser("~/Pictures/Photos Library.photoslibrary")
DB_PATH = os.path.join(LIBRARY, "database", "Photos.sqlite")
DEFAULT_ITEMS_DIR = os.path.expanduser("~/workspace/richmondgeneral/items")
INTAKE_ALBUM = "Richmond General Intake"


def resolve_sku(sku, mint, allocate):
    """Return the SKU to file under: mint a fresh one, or validate an explicit RG-XXXX."""
    if mint:
        return allocate()
    if not sku or not RG_RE.match(sku):
        raise ValueError(f"bad SKU {sku!r}; expected RG-XXXX or --mint")
    return sku


def _stem_taken(existing, stem):
    return any(n.rsplit(".", 1)[0] == stem for n in existing)


def plan_filenames(existing, photos):
    """Map each photo to a non-clobbering output name in items/RG-XXXX/.

    ``hero`` is used only if no hero.* already exists (otherwise demoted to a detail);
    ``detail-<slug>`` collisions get -2/-3; unroled photos take the next free
    detail-N.jpeg.
    """
    names = set(existing)
    out = []

    def next_detail_n():
        i = 1
        while _stem_taken(names, f"detail-{i}"):
            i += 1
        return f"detail-{i}"

    for p in photos:
        role = p.get("role")
        if role == "hero" and not _stem_taken(names, "hero"):
            stem = "hero"
        elif role and role.startswith("detail-"):
            stem = role
            if _stem_taken(names, stem):
                k = 2
                while _stem_taken(names, f"{role}-{k}"):
                    k += 1
                stem = f"{role}-{k}"
        else:
            stem = next_detail_n()
        name = f"{stem}.jpeg"
        names.add(name)
        out.append({"uuid": p["uuid"], "out": name})
    return out


_STUB = {"sku": "", "product_name": "", "attributes": "", "price": "", "condition": "",
         "condition_notes": "", "measurements_in": {}, "buyer_questions": [], "oversize": False}


def ensure_label(item_dir, sku):
    """Write a stub label.json if absent. Never clobbers an existing one. Returns True if written."""
    path = os.path.join(item_dir, "label.json")
    if os.path.exists(path):
        return False
    data = dict(_STUB)
    data["sku"] = sku
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return True


MANIFEST_NAME = ".filed.json"


def load_manifest(item_dir):
    """uuid -> exported filename map for this item (resume/idempotency memory)."""
    path = os.path.join(item_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_manifest(item_dir, manifest):
    with open(os.path.join(item_dir, MANIFEST_NAME), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def split_filed(manifest, photos):
    """Partition photos into (already_filed, todo) using the manifest — a re-run after
    a bridge timeout must NOT re-export under fresh detail-N names."""
    already, todo = [], []
    for p in photos:
        (already if p["uuid"] in manifest else todo).append(p)
    return already, todo


def find_existing_sku(items_dir, uuids):
    """Scan every item's .filed.json for these uuids. Returns {sku: [matched uuids]}.

    This is the duplicate-mint guard: a --mint run that died mid-flight (e.g. the
    RG-0060 void, 2026-07-15 — first run minted + exported, crashed at the album step,
    the retry minted RG-0061 for the same cluster) already left a manifest behind.
    A retry must ADOPT that SKU, not mint a fresh one."""
    hits = {}
    want = set(uuids)
    if not os.path.isdir(items_dir):
        return hits
    for name in sorted(os.listdir(items_dir)):
        if not RG_RE.match(name):
            continue
        # never adopt a VOIDED record (e.g. RG-0060) — its live successor is the target
        label_path = os.path.join(items_dir, name, "label.json")
        try:
            with open(label_path) as f:
                if str(json.load(f).get("state", "")).lower().startswith("void"):
                    continue
        except (OSError, json.JSONDecodeError):
            pass
        manifest = load_manifest(os.path.join(items_dir, name))
        matched = sorted(want & set(manifest))
        if matched:
            hits[name] = matched
    return hits


def parse_tag_result(raw):
    """Parse per-uuid AppleScript status lines ('<uuid>:ok' / '<uuid>:fail <msg>')."""
    ok, failed = [], {}
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        u, _, status = line.partition(":")
        if status == "ok":
            ok.append(u)
        else:
            failed[u] = status[5:].strip() if status.startswith("fail") else status
    return ok, failed


# --- integration (live Photos / filesystem side effects) ------------------------

def _run(cmd, stage):
    """subprocess.run(check) that FAILS LOUD: on error, emit a JSON record with the
    stage + captured stderr to stdout (bridge-visible) before exiting."""
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(json.dumps({"error": stage, "returncode": e.returncode,
                          "cmd": [str(c) for c in cmd][:4],
                          "stderr": (e.stderr or "").strip()[-2000:]}, indent=2))
        sys.exit(1)

def _allocate():
    """Mint the next RG-XXXX via the atomic Square-CAS allocator (hard-fails offline)."""
    out = subprocess.run([sys.executable, SKU_AUTHORITY, "allocate"],
                         check=True, capture_output=True, text=True)
    sku = out.stdout.strip().splitlines()[-1].strip()
    # sku_authority may emit either a bare RG-XXXX or {"sku": "RG-XXXX"}
    if sku.startswith("{"):
        try:
            sku = json.loads(sku).get("sku", sku)
        except json.JSONDecodeError:
            pass
    if not RG_RE.match(sku):
        raise RuntimeError(f"sku_authority returned unexpected output: {sku!r}")
    return sku


def resolve_originals(uuids):
    """Read-only: map each ZUUID to its on-disk original path + favorite flag.

    Returns (originals, offloaded): originals is a list (input order) of
    {uuid, uti, favorite, path, on_disk}; offloaded lists uuids whose original is
    not on disk (iCloud). Unknown uuids are reported via offloaded too.
    """
    placeholders = ",".join("?" for _ in uuids)
    query = (f"SELECT a.ZUUID, a.ZUNIFORMTYPEIDENTIFIER, a.ZFAVORITE "
             f"FROM ZASSET a WHERE a.ZUUID IN ({placeholders})")
    rows = {}
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro&immutable=1", uri=True) as conn:
        for zuuid, uti, fav in conn.execute(query, uuids):
            rows[zuuid] = (uti, fav)
    originals, offloaded = [], []
    for u in uuids:
        if u not in rows:
            offloaded.append(u)
            continue
        uti, fav = rows[u]
        path = os.path.join(LIBRARY, photos_db.original_relpath(u, uti))
        on_disk = os.path.exists(path)
        if not on_disk:
            offloaded.append(u)
        originals.append({"uuid": u, "uti": uti, "favorite": bool(fav),
                          "path": path, "on_disk": on_disk})
    return originals, offloaded


def assign_roles(originals, roles):
    """Per-photo role list. Honors explicit --role; otherwise the favorite (else first
    on-disk) photo becomes the hero, the rest stay unroled (-> detail-N)."""
    photos = [{"uuid": o["uuid"], "role": roles.get(o["uuid"])} for o in originals]
    if not any(p["role"] == "hero" for p in photos):
        cand = next((p for o, p in zip(originals, photos)
                     if p["role"] is None and o["favorite"] and o["on_disk"]), None)
        if cand is None:
            cand = next((p for o, p in zip(originals, photos)
                         if p["role"] is None and o["on_disk"]), None)
        if cand is None and photos:
            cand = photos[0]
        if cand is not None:
            cand["role"] = "hero"
    return photos


def sips_convert(src, dst, quality=88, max_edge=2000):
    """Export capped at max_edge px (long side): the items/ copies are PUBLIC
    derivatives (raw archive = the Photos library), and uncapped 48MP exports made
    item dirs 30–88MB — slow pages + oversized Square uploads (2026-07-15 audit)."""
    _run(["sips", "-Z", str(max_edge), "-s", "format", "jpeg",
          "-s", "formatOptions", str(quality), src, "--out", dst],
         stage=f"sips export -> {os.path.basename(dst)}")
    wipe_gps_jpeg(dst)  # public items/ repo: location EXIF must never land there


def export_to_item(plan, by_uuid, item_dir):
    """sips each planned on-disk original into items/RG-XXXX/<out>. Returns written names."""
    os.makedirs(item_dir, exist_ok=True)
    written = []
    todo = [e for e in plan if by_uuid[e["uuid"]]["on_disk"]]
    for i, entry in enumerate(todo, 1):
        o = by_uuid[entry["uuid"]]
        dst = os.path.join(item_dir, entry["out"])
        sips_convert(o["path"], dst)
        written.append(entry["out"])
        # per-photo progress to stderr: a bridge timeout leaves evidence of how far we got
        print(f"[export {i}/{len(todo)}] {entry['uuid'][:8]} -> {entry['out']}",
              file=sys.stderr, flush=True)
    return written


def _osascript(script):
    return subprocess.run(["osascript", "-e", script], check=True,
                          capture_output=True, text=True).stdout.strip()


def add_to_album(sku, uuids):
    """Add the photos to the per-SKU album — BEST-EFFORT, never fatal.

    The album-add AppleScript is known-flaky over the Cowork bridge (errors mid-run,
    2026-06-21 SOP). Filing correctness lives in the export + rg-sorted tag, not the
    album, so a failure here returns a warning instead of killing the run (which used
    to abort BEFORE tagging and leave exported items stuck in the queue).
    """
    try:
        out = subprocess.run(["osascript", ARCHIVE_SCPT, sku, *uuids],
                             check=True, capture_output=True, text=True, timeout=120)
        return {"ok": True, "result": out.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "warning": f"album add failed (non-fatal): {(e.stderr or '').strip()[-500:]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "warning": "album add timed out after 120s (non-fatal)"}


def tag_keywords(keywords, uuids):
    """Union the given keywords into each photo's keywords (preserves existing).

    Returns (ok_uuids, failed {uuid: reason}) — the old version swallowed per-photo
    errors in a bare `try` and reported "tagged" no matter what, which is how photos
    silently stayed in the intake queue.
    """
    kw_list = "{" + ", ".join(f'"{k}"' for k in keywords) + "}"
    uuid_list = "{" + ", ".join(f'"{u}"' for u in uuids) + "}"
    script = f'''
tell application "Photos"
    set addKw to {kw_list}
    set out to {{}}
    repeat with u in {uuid_list}
        try
            -- direct id lookup (media item ids are ZUUID & "/L0/001") — the old
            -- `whose id starts with` was a per-photo whole-library scan (~1.1s each)
            try
                set mi to media item id ((contents of u) & "/L0/001")
            on error
                set mi to (first media item whose id starts with (contents of u))
            end try
            set kw to keywords of mi
            if kw is missing value then set kw to {{}}
            repeat with k in addKw
                if kw does not contain (k as string) then set end of kw to (k as string)
            end repeat
            set keywords of mi to kw
            set end of out to (contents of u) & ":ok"
        on error errMsg
            set end of out to (contents of u) & ":fail " & errMsg
        end try
    end repeat
    set AppleScript's text item delimiters to linefeed
    return out as string
end tell'''
    return parse_tag_result(_osascript(script))


def tag_sorted(sku, uuids, retries=1):
    """Union rg-sorted + <sku> into each photo's keywords, with per-uuid verification
    and one retry of any failures. Returns {"ok": [...], "failed": {uuid: reason}}."""
    ok, failed = tag_keywords(["rg-sorted", sku], uuids)
    for _ in range(retries):
        if not failed:
            break
        retry_ok, failed = tag_keywords(["rg-sorted", sku], list(failed))
        ok.extend(retry_ok)
    return {"ok": ok, "failed": failed}


def main():
    p = argparse.ArgumentParser(description="File a cluster of intake photos into a SKU's lib.")
    p.add_argument("--sku", help="existing RG-XXXX to file under")
    p.add_argument("--mint", action="store_true", help="mint the next RG-XXXX (Square-CAS)")
    p.add_argument("--uuids", required=True, help="comma-separated ZUUIDs (the cluster)")
    p.add_argument("--role", action="append", default=[],
                   help="uuid=role (hero|detail-<slug>); repeatable")
    p.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR)
    p.add_argument("--plan", action="store_true", help="dry-run: print intent, mutate nothing")
    p.add_argument("--json", action="store_true", help="with --plan: emit the plan as JSON")
    p.add_argument("--tag-only", action="store_true",
                   help="just tag rg-sorted + SKU (no export/album) — for photos of an already-handled item")
    p.add_argument("--no-album", action="store_true",
                   help="skip the per-SKU album add entirely (it is best-effort anyway)")
    args = p.parse_args()

    uuids = [u.strip() for u in args.uuids.split(",") if u.strip()]
    if not uuids:
        p.error("--uuids was empty")
    for u in uuids:
        if not UUID_RE.match(u):
            p.error(f"bad uuid {u!r}")

    if args.tag_only:
        if not args.sku or not RG_RE.match(args.sku):
            p.error("--tag-only requires --sku RG-XXXX")
        result = tag_sorted(args.sku, uuids)
        print(json.dumps({"mode": "tag-only", "sku": args.sku,
                          "tagged": len(result["ok"]), "failed": result["failed"]}, indent=2))
        sys.exit(3 if result["failed"] else 0)

    roles = {}
    for r in args.role:
        k, _, v = r.partition("=")
        if not v:
            p.error(f"bad --role {r!r}; expected uuid=role")
        roles[k.strip()] = v.strip()

    originals, offloaded = resolve_originals(uuids)
    if not originals:
        p.error("no matching assets for the given uuids")
    by_uuid = {o["uuid"]: o for o in originals}
    on_disk = [o for o in originals if o["on_disk"]]
    photos = assign_roles(on_disk, roles)  # only photos we can actually write get filed

    def existing_files(sku):
        d = os.path.join(args.items_dir, sku) if sku else None
        return set(os.listdir(d)) if d and os.path.isdir(d) else set()

    if args.plan:
        plan = plan_filenames(existing_files(args.sku), photos)
        sku_label = args.sku or ("RG-NEXT (would mint)" if args.mint else "(no SKU!)")
        if args.json:
            print(json.dumps({"plan": True, "sku": sku_label,
                              "exports": [{"uuid": e["uuid"], "out": e["out"]} for e in plan],
                              "album_add": len(on_disk), "offloaded": offloaded}, indent=2))
            return
        print(f"PLAN — sku: {sku_label}")
        for entry in plan:
            print(f"  {entry['uuid'][:8]}  ->  items/{args.sku or 'RG-XXXX'}/{entry['out']}")
        print(f"  album add: {len(on_disk)} photo(s) -> '{args.sku or 'RG-XXXX'}' under 'Richmond General'")
        print(f"  tag rg-sorted + sku (find_product_clusters --hide-sorted then drops it from the queue)")
        if offloaded:
            print(f"  ⚠︎ OFFLOADED (download first, not filed): {', '.join(u[:8] for u in offloaded)}")
        return

    # Duplicate-mint guard: if any of these uuids were already filed somewhere,
    # adopt that SKU (resume) instead of minting/filing a second record.
    hits = find_existing_sku(args.items_dir, uuids)
    if len(hits) > 1:
        print(json.dumps({"error": "uuids span multiple existing SKUs — resolve manually "
                          "(void the later record per the Void-SKU flow)",
                          "matches": hits}, indent=2))
        sys.exit(4)
    if hits:
        (found_sku, matched), = hits.items()
        if args.mint:
            print(f"[resume] {len(matched)} of these photo(s) already filed under {found_sku} "
                  f"— ADOPTING it, no new mint", file=sys.stderr, flush=True)
            args.sku, args.mint = found_sku, False
        elif args.sku and args.sku != found_sku:
            print(json.dumps({"error": f"these uuids were already filed under {found_sku}, "
                              f"not {args.sku} — filing under two SKUs creates a duplicate "
                              "(Void-SKU flow if one is wrong)",
                              "matches": hits}, indent=2))
            sys.exit(4)

    sku = resolve_sku(args.sku, args.mint, _allocate)
    item_dir = os.path.join(args.items_dir, sku)

    # RESUME: skip uuids this item already exported (manifest) — a re-run after a
    # bridge timeout must not duplicate photos under fresh detail-N names.
    manifest = load_manifest(item_dir)
    already, todo = split_filed(manifest, photos)
    if already:
        print(f"[resume] {len(already)} photo(s) already exported for {sku}; skipping",
              file=sys.stderr, flush=True)

    # re-plan against the resolved sku's existing files (mint created a new dir name)
    plan = plan_filenames(existing_files(sku), todo)
    written = export_to_item(plan, by_uuid, item_dir)
    for entry in plan:
        if by_uuid[entry["uuid"]]["on_disk"]:
            manifest[entry["uuid"]] = entry["out"]
    os.makedirs(item_dir, exist_ok=True)
    save_manifest(item_dir, manifest)
    ensure_label(item_dir, sku)

    # TAG FIRST (queue-clearing is the critical side effect), album LAST + best-effort:
    # the old order aborted on the flaky album step BEFORE tagging, stranding exported
    # items in the intake queue (2026-07-15 intake postmortem).
    on_disk_uuids = [o["uuid"] for o in originals if o["on_disk"]]
    tag = tag_sorted(sku, on_disk_uuids)
    album = {"ok": None, "result": "skipped (--no-album)"} if args.no_album \
        else add_to_album(sku, on_disk_uuids)

    print(json.dumps({"sku": sku, "written": written,
                      "resumed_already_exported": len(already),
                      "tagged": len(tag["ok"]), "tag_failed": tag["failed"],
                      "album": album, "offloaded": offloaded}, indent=2))
    sys.exit(3 if tag["failed"] else 0)


if __name__ == "__main__":
    main()
