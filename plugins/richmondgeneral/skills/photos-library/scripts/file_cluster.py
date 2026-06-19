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


# --- integration (live Photos / filesystem side effects) ------------------------

def _allocate():
    """Mint the next RG-XXXX via the atomic Square-CAS allocator (hard-fails offline)."""
    out = subprocess.run([sys.executable, SKU_AUTHORITY, "allocate"],
                         check=True, capture_output=True, text=True)
    sku = out.stdout.strip().splitlines()[-1].strip()
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


def sips_convert(src, dst, quality=90):
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(quality),
                    src, "--out", dst], check=True, capture_output=True)


def export_to_item(plan, by_uuid, item_dir):
    """sips each planned on-disk original into items/RG-XXXX/<out>. Returns written names."""
    os.makedirs(item_dir, exist_ok=True)
    written = []
    for entry in plan:
        o = by_uuid[entry["uuid"]]
        if not o["on_disk"]:
            continue
        dst = os.path.join(item_dir, entry["out"])
        sips_convert(o["path"], dst)
        written.append(entry["out"])
    return written


def _osascript(script):
    return subprocess.run(["osascript", "-e", script], check=True,
                          capture_output=True, text=True).stdout.strip()


def add_to_album(sku, uuids):
    """Add the photos to the per-SKU album (idempotent) via the existing helper."""
    out = subprocess.run(["osascript", ARCHIVE_SCPT, sku, *uuids],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def tag_sorted(sku, uuids):
    """Union rg-sorted + <sku> into each photo's keywords (preserves existing)."""
    uuid_list = "{" + ", ".join(f'"{u}"' for u in uuids) + "}"
    script = f'''
tell application "Photos"
    set addKw to {{"rg-sorted", "{sku}"}}
    repeat with u in {uuid_list}
        try
            set mi to (first media item whose id starts with (contents of u))
            set kw to keywords of mi
            if kw is missing value then set kw to {{}}
            repeat with k in addKw
                if kw does not contain (k as string) then set end of kw to (k as string)
            end repeat
            set keywords of mi to kw
        end try
    end repeat
    return "tagged"
end tell'''
    return _osascript(script)


def main():
    p = argparse.ArgumentParser(description="File a cluster of intake photos into a SKU's lib.")
    p.add_argument("--sku", help="existing RG-XXXX to file under")
    p.add_argument("--mint", action="store_true", help="mint the next RG-XXXX (Square-CAS)")
    p.add_argument("--uuids", required=True, help="comma-separated ZUUIDs (the cluster)")
    p.add_argument("--role", action="append", default=[],
                   help="uuid=role (hero|detail-<slug>); repeatable")
    p.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR)
    p.add_argument("--plan", action="store_true", help="dry-run: print intent, mutate nothing")
    p.add_argument("--tag-only", action="store_true",
                   help="just tag rg-sorted + SKU (no export/album) — for photos of an already-handled item")
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
                          "tagged": len(uuids), "result": result}, indent=2))
        return

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
        print(f"PLAN — sku: {sku_label}")
        for entry in plan:
            print(f"  {entry['uuid'][:8]}  ->  items/{args.sku or 'RG-XXXX'}/{entry['out']}")
        print(f"  album add: {len(on_disk)} photo(s) -> '{args.sku or 'RG-XXXX'}' under 'Richmond General'")
        print(f"  tag rg-sorted + sku (find_product_clusters --hide-sorted then drops it from the queue)")
        if offloaded:
            print(f"  ⚠︎ OFFLOADED (download first, not filed): {', '.join(u[:8] for u in offloaded)}")
        return

    sku = resolve_sku(args.sku, args.mint, _allocate)
    item_dir = os.path.join(args.items_dir, sku)
    # re-plan against the resolved sku's existing files (mint created a new dir name)
    plan = plan_filenames(existing_files(sku), photos)
    written = export_to_item(plan, by_uuid, item_dir)
    ensure_label(item_dir, sku)
    on_disk_uuids = [o["uuid"] for o in originals if o["on_disk"]]
    album = add_to_album(sku, on_disk_uuids)
    tag = tag_sorted(sku, on_disk_uuids)
    print(json.dumps({"sku": sku, "written": written, "album": album, "tag": tag,
                      "offloaded": offloaded}, indent=2))


if __name__ == "__main__":
    main()
