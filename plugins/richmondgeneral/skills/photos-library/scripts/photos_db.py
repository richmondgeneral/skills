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
