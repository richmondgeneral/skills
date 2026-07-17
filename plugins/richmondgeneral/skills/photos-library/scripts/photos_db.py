#!/usr/bin/env python3
"""Shared Photos.sqlite helpers — schema-robust album / keyword filtering.

The CoreData many-to-many join tables and their columns embed entity numbers
(e.g. ``Z_33ASSETS`` with ``Z_33ALBUMS``/``Z_3ASSETS``; ``Z_1KEYWORDS`` with
``Z_1ASSETATTRIBUTES``/``Z_52KEYWORDS``). Those numbers differ across macOS /
Photos versions, so we DISCOVER the table + column names at runtime from
``sqlite_master`` rather than hardcoding them.

Each ``*_condition`` returns ``(sql_fragment, params)`` to splice into a query
whose ``ZASSET`` alias is ``a``. If the join table can't be found (unexpected
schema), the fragment is ``0=1`` so the query simply yields nothing rather than
erroring.
"""


def _columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]


def discover_album_join(conn):
    """(join_table, album_col, asset_col) for the album<->asset M2M, or None."""
    rows = conn.execute(
        r"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Z\_%ASSETS' ESCAPE '\'"
    ).fetchall()
    for (name,) in rows:
        cols = [c for c in _columns(conn, name) if not c.startswith("Z_FOK")]
        album_col = next((c for c in cols if c.endswith("ALBUMS")), None)
        asset_col = next((c for c in cols if c.endswith("ASSETS") and not c.endswith("ALBUMS")), None)
        if album_col and asset_col:
            return name, album_col, asset_col
    return None


def discover_keyword_join(conn):
    """(join_table, attr_col, keyword_col) for the keyword<->asset M2M, or None."""
    rows = conn.execute(
        r"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Z\_%KEYWORDS' ESCAPE '\'"
    ).fetchall()
    for (name,) in rows:
        cols = [c for c in _columns(conn, name) if not c.startswith("Z_FOK")]
        attr_col = next((c for c in cols if c.endswith("ASSETATTRIBUTES")), None)
        kw_col = next((c for c in cols if c.endswith("KEYWORDS")), None)
        if attr_col and kw_col:
            return name, attr_col, kw_col
    return None


def _leaf(name):
    """Album leaf name — accept "Folder/Album" and match the trailing component."""
    return name.rsplit("/", 1)[-1].strip()


def album_condition(conn, album_name):
    """(fragment, params) selecting ZASSET rows (alias ``a``) in the named album.

    Matches the album's leaf name case-insensitively (ZKIND=2 user albums).
    """
    info = discover_album_join(conn)
    if not info:
        return "0=1", []
    jtable, album_col, asset_col = info
    frag = (
        f"a.Z_PK IN (SELECT j.{asset_col} FROM {jtable} j "
        f"JOIN ZGENERICALBUM alb ON alb.Z_PK = j.{album_col} "
        f"WHERE alb.ZKIND = 2 AND lower(alb.ZTITLE) = lower(?))"
    )
    return frag, [_leaf(album_name)]


def keyword_condition(conn, keyword):
    """(fragment, params) selecting ZASSET rows (alias ``a``) tagged ``keyword``."""
    info = discover_keyword_join(conn)
    if not info:
        return "0=1", []
    jtable, attr_col, kw_col = info
    frag = (
        f"a.ZADDITIONALATTRIBUTES IN (SELECT j.{attr_col} FROM {jtable} j "
        f"JOIN ZKEYWORD kw ON kw.Z_PK = j.{kw_col} "
        f"WHERE lower(kw.ZTITLE) = lower(?))"
    )
    return frag, [keyword.strip()]


def exclude_keyword_condition(conn, keyword):
    """(fragment, params) excluding ZASSET rows (alias ``a``) tagged ``keyword``."""
    info = discover_keyword_join(conn)
    if not info:
        return "1=1", [] # if we can't find the keyword table, don't exclude anything
    jtable, attr_col, kw_col = info
    frag = (
        f"a.ZADDITIONALATTRIBUTES NOT IN (SELECT j.{attr_col} FROM {jtable} j "
        f"JOIN ZKEYWORD kw ON kw.Z_PK = j.{kw_col} "
        f"WHERE lower(kw.ZTITLE) = lower(?))"
    )
    return frag, [keyword.strip()]


def album_exists(conn, album_name):
    row = conn.execute(
        "SELECT 1 FROM ZGENERICALBUM WHERE ZKIND = 2 AND lower(ZTITLE) = lower(?) LIMIT 1",
        (_leaf(album_name),),
    ).fetchone()
    return row is not None


def keyword_exists(conn, keyword):
    row = conn.execute(
        "SELECT 1 FROM ZKEYWORD WHERE lower(ZTITLE) = lower(?) LIMIT 1",
        (keyword.strip(),),
    ).fetchone()
    return row is not None


def list_albums(conn, limit=40):
    """User-album (ZKIND=2) titles, for discovery / not-found hints."""
    rows = conn.execute(
        "SELECT ZTITLE FROM ZGENERICALBUM WHERE ZKIND = 2 AND ZTITLE IS NOT NULL "
        "ORDER BY ZTITLE LIMIT ?",
        (limit,),
    ).fetchall()
    return [r[0] for r in rows]


_UTI_EXT = {"public.jpeg": "jpeg", "public.heic": "heic", "public.png": "png",
            "public.tiff": "tiff", "com.compuserve.gif": "gif"}

def original_relpath(uuid, uti):
    """Path of an original inside a .photoslibrary, e.g. originals/A/<uuid>.jpeg.
    Mirrors the layout used by extract_photos.py / intake_to_item.py."""
    ext = _UTI_EXT.get((uti or "").lower(), "jpeg")
    return f"originals/{uuid[0].upper()}/{uuid}.{ext}"


# ---------------------------------------------------------------------------
# GPS EXIF wipe (privacy) — STDLIB ONLY (this script runs over the bare bridge
# shell, no piexif). 2026-07-15: 130 published images carried iPhone GPS
# coordinates because sips exports originals metadata-and-all straight into
# the public items/ repo. The wipe is in place and offset-stable: the GPS IFD's
# entry count, its 12-byte entries, and every pointed-to value block are
# zeroed, so the file length, pixels, orientation tag, and all other EXIF are
# untouched. Detectors that follow the (now zero) entry count see no GPS.
# ---------------------------------------------------------------------------

import os
import sys

_TIFF_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def wipe_gps_jpeg(path):
    """Zero the GPS IFD of a JPEG in place. Returns True if GPS data was wiped,
    False if none found. NEVER raises — filing must not fail on a weird file
    (the items-repo CI gate is the backstop)."""
    try:
        with open(path, "rb") as f:
            data = bytearray(f.read())
        if data[:2] != b"\xff\xd8":
            return False
        # find the Exif APP1 segment
        i = 2
        tiff = None
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                break
            marker, seglen = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
            if marker == 0xE1 and data[i + 4:i + 10] == b"Exif\x00\x00":
                tiff = i + 10  # TIFF header offset; all IFD offsets are relative to this
                break
            if marker in (0xDA, 0xD9):  # image data — no EXIF
                break
            i += 2 + seglen
        if tiff is None:
            return False
        bo = {b"II": "little", b"MM": "big"}.get(bytes(data[tiff:tiff + 2]))
        if bo is None:
            return False
        num = lambda a, n: int.from_bytes(data[a:a + n], bo)
        ifd0 = tiff + num(tiff + 4, 4)
        # scan IFD0 entries for the GPS IFD pointer (tag 0x8825)
        gps = None
        for e in range(num(ifd0, 2)):
            ent = ifd0 + 2 + 12 * e
            if num(ent, 2) == 0x8825:
                gps = tiff + num(ent + 8, 4)
                break
        if gps is None or gps + 2 > len(data):
            return False
        count = num(gps, 2)
        if count == 0 or gps + 2 + 12 * count > len(data):
            return False
        # zero every pointed-to value block, then the entries, then the count
        for e in range(count):
            ent = gps + 2 + 12 * e
            vsize = _TIFF_TYPE_SIZES.get(num(ent + 2, 2), 1) * num(ent + 4, 4)
            if vsize > 4:
                off = tiff + num(ent + 8, 4)
                if off + vsize <= len(data):
                    data[off:off + vsize] = bytes(vsize)
            data[ent:ent + 12] = bytes(12)
        data[gps:gps + 2] = (0).to_bytes(2, bo)
        with open(path, "wb") as f:
            f.write(bytes(data))
        return True
    except Exception as exc:  # pragma: no cover - belt and suspenders
        print(f"[gps-wipe] WARNING {os.path.basename(path)}: {exc}", file=sys.stderr)
        return False
