#!/usr/bin/env python3
"""Intake scratch cleanup — stop Live Photo .mov bloat + sweep done-item scratch.

Two root causes of the ~1G/session intake bloat (2026-06-19 audit):
  A) iCloud-offloaded originals get materialized by a manual "export unmodified
     originals" step, which emits each Live Photo's .mov sidecar alongside the
     still. Listings only ever need the still. ``prune_live_photo_sidecars`` drops
     those .mov files — and ONLY those that have a still twin, so a real
     standalone video is never touched.
  B) Nothing sweeps intake scratch after an item is done, so ``rg-pending/<sku>``
     (and legacy ``ops/_intake_*``) pile up forever. ``sweep_intake_scratch``
     removes an item's scratch, but only once it's in a terminal state — never
     while photo follow-ups might still need the stills.
"""
import argparse
import json
import os
import shutil
import sys

# Still-image extensions that mark a sibling .mov as a Live Photo sidecar
# (lower-case; matching is case-insensitive).
STILL_EXTS = (".jpeg", ".jpg", ".heic", ".png", ".tiff", ".dng")

# Item states at which intake scratch is safe to delete. "Listed" is deliberately
# excluded: an item can be Listed with photo follow-ups still open (e.g. backstamp
# shots), so its stills in scratch may still be needed.
TERMINAL_STATES = ("Sold", "Archived")


def prune_live_photo_sidecars(directory, dry_run=False):
    """Delete Live Photo .mov sidecars (a .mov with a same-stem still twin).

    Returns the list of removed (or, with ``dry_run``, would-be-removed) paths. A
    .mov with NO still twin is a real video and is never touched. Missing dir → []
    (no error). Pure filesystem logic.
    """
    if not os.path.isdir(directory):
        return []
    names = os.listdir(directory)
    still_stems = {
        os.path.splitext(n)[0].lower()
        for n in names
        if os.path.splitext(n)[1].lower() in STILL_EXTS
    }
    removed = []
    for n in names:
        stem, ext = os.path.splitext(n)
        if ext.lower() == ".mov" and stem.lower() in still_stems:
            path = os.path.join(directory, n)
            if not dry_run:
                os.remove(path)
            removed.append(path)
    return removed


def _staging_dir(items_dir, sku):
    """Default intake staging dir — mirrors intake_to_item.resolve_staging_dir:
    a sibling of items/ at ``<items_dir>/../rg-pending/<sku>``."""
    return os.path.normpath(os.path.join(items_dir, "..", "rg-pending", sku))


def _read_state(items_dir, sku):
    """Return the item's ``state`` from items/<sku>/label.json, or None if absent/unreadable."""
    label = os.path.join(items_dir, sku, "label.json")
    try:
        with open(label) as fh:
            return json.load(fh).get("state")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def sweep_intake_scratch(sku, items_dir, staging_root=None, extra=None,
                         allow_states=TERMINAL_STATES, dry_run=True):
    """Remove an item's intake scratch once it's in a terminal state.

    Targets: the staging dir (``<staging_root or items_dir/..>/rg-pending/<sku>``,
    mirroring resolve_staging_dir) plus any ``extra`` legacy scratch dirs. Acts only
    when the item's label.json ``state`` is in ``allow_states``; otherwise reports it
    skipped and deletes nothing. ``dry_run`` (default True) reports targets without
    deleting. Returns a summary dict.
    """
    if staging_root is not None:
        staging = os.path.normpath(os.path.join(staging_root, sku))
    else:
        staging = _staging_dir(items_dir, sku)
    candidates = [staging] + [os.path.normpath(p) for p in (extra or [])]
    targets = [p for p in candidates if os.path.isdir(p)]

    state = _read_state(items_dir, sku)
    summary = {"sku": sku, "state": state, "eligible": False,
               "targets": targets, "removed": [], "reason": ""}

    if state is None:
        summary["reason"] = f"no readable label.json state for {sku} — refusing to sweep"
        return summary
    if state not in allow_states:
        summary["reason"] = (f"state {state!r} not terminal "
                             f"({', '.join(allow_states)}) — scratch may still be needed")
        return summary

    summary["eligible"] = True
    if dry_run:
        summary["reason"] = f"dry-run: would remove {len(targets)} scratch dir(s)"
        return summary

    for p in targets:
        shutil.rmtree(p)
        summary["removed"].append(p)
    summary["reason"] = f"removed {len(summary['removed'])} scratch dir(s) for {sku} ({state})"
    return summary


def main(argv=None):
    """Thin CLI glue over the two tested functions. Default is dry-run; pass --apply to delete."""
    p = argparse.ArgumentParser(description="Intake scratch cleanup (Live Photo sidecars + done-item sweep)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("prune-sidecars", help="Drop Live Photo .mov files that have a still twin")
    pp.add_argument("directory")
    pp.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")

    sw = sub.add_parser("sweep", help="Remove a terminal-state item's intake scratch")
    sw.add_argument("--sku", required=True)
    sw.add_argument("--items-dir", required=True)
    sw.add_argument("--extra", nargs="*", default=[], help="Extra legacy scratch dirs (e.g. ops/_intake_*)")
    sw.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")

    args = p.parse_args(argv)
    if args.cmd == "prune-sidecars":
        removed = prune_live_photo_sidecars(args.directory, dry_run=not args.apply)
        verb = "removed" if args.apply else "would remove"
        print(f"{verb} {len(removed)} Live Photo sidecar(s)")
        for r in removed:
            print(f"  {r}")
        return 0
    res = sweep_intake_scratch(args.sku, args.items_dir, extra=args.extra, dry_run=not args.apply)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
