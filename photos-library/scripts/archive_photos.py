#!/usr/bin/env python3
"""Archive processed product photos into Photos.app per-item albums.

Moves photos from the camera roll into a structured album hierarchy:
  Richmond General Archive/
    RG-0001/   (album with originals for item 1)
    RG-0002/   (album with originals for item 2)
    ...

Two modes:
  --uuids   : Archive by Photos library UUID (preferred, from cluster discovery)
  --reverse : Reverse-lookup filenames in the item folder back to Photos UUIDs

Usage:
  # Direct UUID mode (when cluster discovery was used in Phase 0):
  python archive_photos.py --item-id RG-0015 --uuids ABC123 DEF456 GHI789

  # Reverse-lookup mode (when photos came from Desktop/Downloads):
  python archive_photos.py --item-id RG-0015 --reverse \
    --item-dir ~/workspace/square/items/RG-0015 --include "IMG_*"

  # Dry run (show what would be archived):
  python archive_photos.py --item-id RG-0015 --uuids ABC123 --dry-run

  # JSON output (for pipeline integration):
  python archive_photos.py --item-id RG-0015 --uuids ABC123 --json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional


# macOS Photos library DB path
PHOTOS_DB = os.path.expanduser(
    "~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite"
)

# AppleScript for album management
ARCHIVE_SCRIPT = os.path.join(os.path.dirname(__file__), "archive_to_album.scpt")

# Cocoa epoch offset (2001-01-01 to Unix epoch)
COCOA_EPOCH_OFFSET = 978307200


def find_uuids_by_filename(
    filenames: List[str], file_mtimes: Optional[dict] = None
) -> tuple[dict, Optional[str]]:
    """Reverse-lookup Photos library UUIDs by original filename.

    Searches the Photos SQLite database for assets whose original filename
    matches any of the provided filenames. If exact filename lookup misses
    (for example local JPG files from HEIC originals), it falls back to
    base-name lookup across extensions (e.g., IMG_0077.jpg -> IMG_0077.HEIC).

    Returns a dict mapping local filename -> uuid and an optional error message.
    """
    if not filenames:
        return {}, None

    if not os.path.exists(PHOTOS_DB):
        return {}, (
            "Photos database not found. Ensure Photos Library exists at "
            f"{PHOTOS_DB}"
        )

    try:
        # immutable=1 (not just mode=ro) so we take no locks and never touch
        # the WAL — avoids disrupting cloudphotod's iCloud sync state.
        conn = sqlite3.connect(f"file:{PHOTOS_DB}?mode=ro&immutable=1", uri=True)
        cursor = conn.cursor()
    except sqlite3.Error as exc:
        return {}, (
            "Unable to open Photos database. Grant Full Disk Access to Terminal/Codex "
            f"and retry. SQLite error: {exc}"
        )

    normalized_filenames = {fname: fname.lower() for fname in filenames}
    normalized_bases = {fname: Path(fname).stem.lower() for fname in filenames}
    exact_names = sorted(set(normalized_filenames.values()))
    base_names = sorted(set(normalized_bases.values()))

    exact_placeholders = ",".join("?" for _ in exact_names)
    base_placeholders = ",".join("?" for _ in base_names)
    base_expr = (
        "lower(CASE "
        "WHEN instr(aa.ZORIGINALFILENAME, '.') > 0 "
        "THEN substr(aa.ZORIGINALFILENAME, 1, instr(aa.ZORIGINALFILENAME, '.') - 1) "
        "ELSE aa.ZORIGINALFILENAME END)"
    )

    query = f"""
    SELECT
        a.ZUUID,
        aa.ZORIGINALFILENAME,
        a.ZDATECREATED,
        datetime(a.ZDATECREATED + {COCOA_EPOCH_OFFSET}, 'unixepoch', 'localtime') as created,
        lower(aa.ZORIGINALFILENAME) as original_lower,
        {base_expr} as base_lower
    FROM ZASSET a
    LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
    WHERE (
        lower(aa.ZORIGINALFILENAME) IN ({exact_placeholders})
        OR {base_expr} IN ({base_placeholders})
    )
      AND aa.ZORIGINALFILENAME IS NOT NULL
      AND a.ZTRASHEDSTATE = 0
      AND a.ZKIND = 0
    ORDER BY a.ZDATECREATED DESC
    """

    try:
        cursor.execute(query, exact_names + base_names)
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        try:
            conn.close()
        except sqlite3.Error:
            pass
        return {}, f"Photos database query failed: {exc}"

    # Build candidates indexed by exact filename and by base filename.
    candidates_by_exact = {}
    candidates_by_base = {}
    for uuid, fname, cocoa_created, created, original_lower, base_lower in rows:
        candidate = {
            "uuid": uuid,
            "filename": fname,
            "cocoa_created": cocoa_created,
            "created": created,
        }

        if original_lower:
            if original_lower not in candidates_by_exact:
                candidates_by_exact[original_lower] = []
            candidates_by_exact[original_lower].append(candidate)

        if base_lower:
            if base_lower not in candidates_by_base:
                candidates_by_base[base_lower] = []
            candidates_by_base[base_lower].append(candidate)

    # Map local filename -> best UUID match.
    # Prefer exact filename match; fallback to base-name match.
    result = {}
    for local_name in filenames:
        exact_key = normalized_filenames[local_name]
        base_key = normalized_bases[local_name]

        if exact_key in candidates_by_exact:
            candidates = candidates_by_exact[exact_key]
            match_scope = "exact"
        elif base_key in candidates_by_base:
            candidates = candidates_by_base[base_key]
            match_scope = "base"
        else:
            continue

        chosen = candidates[0]
        match_method = f"{match_scope}_most_recent"

        if file_mtimes and local_name in file_mtimes:
            target_unix = file_mtimes[local_name]
            chosen = min(
                candidates,
                key=lambda c: abs((c["cocoa_created"] + COCOA_EPOCH_OFFSET) - target_unix),
            )
            match_method = f"{match_scope}_closest_mtime"

        result[local_name] = {
            "uuid": chosen["uuid"],
            "filename": local_name,
            "photos_filename": chosen["filename"],
            "created": chosen["created"],
            "match_method": match_method,
            "candidate_count": len(candidates),
        }

    return result, None


def parse_include_patterns(include: str) -> List[str]:
    """Parse comma-separated glob patterns for filename matching."""
    patterns = [p.strip().lower() for p in include.split(",") if p.strip()]
    if not patterns:
        return ["img_*"]
    return patterns


def get_filenames_from_dir(item_dir: str, include: str = "IMG_*") -> List[str]:
    """Get original photo filenames from an item directory.

    Matching is case-insensitive. `include` supports comma-separated globs.
    """
    item_path = Path(item_dir).expanduser()
    if not item_path.exists():
        return []

    patterns = parse_include_patterns(include)

    filenames = []
    for f in sorted(item_path.iterdir()):
        if f.is_file() and any(fnmatch(f.name.lower(), p) for p in patterns):
            filenames.append(f.name)

    return filenames


def get_file_mtimes(item_dir: str, filenames: List[str]) -> dict:
    """Get mtime for each filename in item directory."""
    item_path = Path(item_dir).expanduser()
    mtimes = {}
    for filename in filenames:
        try:
            mtimes[filename] = (item_path / filename).stat().st_mtime
        except OSError:
            continue
    return mtimes


def run_archive_applescript(item_id: str, uuids: List[str], dry_run: bool = False) -> dict:
    """Run the AppleScript to archive photos into a per-item album.

    Returns dict with archived count, skipped count, and album name.
    """
    if not uuids:
        return {"archived": 0, "skipped": 0, "album": item_id, "error": "No UUIDs provided"}

    if dry_run:
        return {
            "archived": len(uuids),
            "skipped": 0,
            "album": item_id,
            "dry_run": True,
            "uuids": uuids,
        }

    if not os.path.exists(ARCHIVE_SCRIPT):
        return {"archived": 0, "skipped": 0, "album": item_id,
                "error": f"AppleScript not found: {ARCHIVE_SCRIPT}"}

    cmd = ["osascript", ARCHIVE_SCRIPT, item_id] + uuids

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            return {
                "archived": 0,
                "skipped": len(uuids),
                "album": item_id,
                "error": result.stderr.strip(),
            }

        # Parse result: "archived:N,skipped:M,album:RG-XXXX"
        output = result.stdout.strip()
        parsed = {}
        for part in output.split(","):
            key, _, val = part.partition(":")
            parsed[key.strip()] = val.strip()

        return {
            "archived": int(parsed.get("archived", 0)),
            "skipped": int(parsed.get("skipped", 0)),
            "album": parsed.get("album", item_id),
        }

    except subprocess.TimeoutExpired:
        return {"archived": 0, "skipped": len(uuids), "album": item_id,
                "error": "Photos.app timed out (60s)"}
    except Exception as e:
        return {"archived": 0, "skipped": len(uuids), "album": item_id,
                "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Archive product photos into Photos.app per-item albums"
    )
    parser.add_argument("--item-id", required=True, help="Item SKU (e.g., RG-0015)")

    # Source mode
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--uuids", nargs="+", help="Photos library UUIDs to archive")
    source.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse-lookup UUIDs from filenames in item directory",
    )

    # Reverse-lookup options
    parser.add_argument("--item-dir", help="Item directory path (for --reverse mode)")
    parser.add_argument(
        "--include",
        default="IMG_*",
        help=(
            "Filename glob pattern(s), comma-separated; case-insensitive "
            "(default: IMG_*)"
        ),
    )

    # Output options
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    uuids = []

    if args.uuids:
        uuids = args.uuids
    elif args.reverse:
        if not args.item_dir:
            # Default to standard item path
            args.item_dir = os.path.expanduser(
                f"~/workspace/square/items/{args.item_id}"
            )

        filenames = get_filenames_from_dir(args.item_dir, args.include)

        if not filenames:
            result = {
                "archived": 0,
                "skipped": 0,
                "album": args.item_id,
                "error": f"No files matching '{args.include}' in {args.item_dir}",
            }
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"No files matching '{args.include}' in {args.item_dir}")
            sys.exit(1)

        # Reverse lookup filenames -> UUIDs
        file_mtimes = get_file_mtimes(args.item_dir, filenames)
        lookup, lookup_error = find_uuids_by_filename(filenames, file_mtimes=file_mtimes)
        if lookup_error:
            result = {
                "archived": 0,
                "skipped": len(filenames),
                "album": args.item_id,
                "error": lookup_error,
            }
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Error: {lookup_error}")
            sys.exit(1)

        matched = []
        unmatched = []
        for fname in filenames:
            if fname in lookup:
                matched.append(lookup[fname])
                uuids.append(lookup[fname]["uuid"])
            else:
                unmatched.append(fname)

        if not args.json and not args.dry_run:
            if matched:
                print(f"Found {len(matched)} of {len(filenames)} photos in Photos library:")
                for m in matched:
                    photos_name = m.get("photos_filename", m["filename"])
                    print(f"  {m['filename']} -> {m['uuid']} (Photos: {photos_name})")
            if unmatched:
                print(f"Not found in Photos library ({len(unmatched)}):")
                for u in unmatched:
                    print(f"  {u}")

    # Archive
    result = run_archive_applescript(args.item_id, uuids, dry_run=args.dry_run)

    if args.reverse:
        result["lookup"] = {
            "total_files": len(get_filenames_from_dir(
                args.item_dir or os.path.expanduser(f"~/workspace/square/items/{args.item_id}"),
                args.include
            )),
            "matched": len(uuids),
            "unmatched": len(filenames) - len(uuids) if 'filenames' in dir() else 0,
        }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("dry_run"):
            print(f"\n[DRY RUN] Would archive {result['archived']} photos to "
                  f"Richmond General Archive / {result['album']}")
        elif result.get("error"):
            print(f"\nError: {result['error']}")
        else:
            print(f"\nArchived {result['archived']} photos to "
                  f"Richmond General Archive / {result['album']}")
            if result["skipped"] > 0:
                print(f"  ({result['skipped']} UUIDs not found, skipped)")

    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
