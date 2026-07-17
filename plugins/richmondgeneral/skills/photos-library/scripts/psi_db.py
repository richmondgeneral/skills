#!/usr/bin/env python3
"""Photos search-index (psi.sqlite) helpers — Apple-ML label lookups.

psi.sqlite lives at ``<library>/database/search/psi.sqlite`` and maps ML labels
("Receipt", "Document", …) to assets. Open it ``mode=ro&immutable=1`` only —
same iCloud-sync safety rule as Photos.sqlite.

Schema notes (live-verified 2026-07-15):
- ``groups.content_string`` AND ``normalized_string`` carry a trailing NUL
  byte. SQLite's rtrim/replace can't strip it (the NUL pattern arg reads as
  empty), so match equality against both the plain and ``||char(0)`` forms.
- ``assets.uuid_0``/``uuid_1`` are the asset UUID as two little-endian signed
  64-bit halves; reconstructed value equals ``ZASSET.ZUUID``.
- Receipt groups: category 1500 (scene label "Receipt") and 2800 ("Receipts").
"""

import struct
import uuid as _uuid
from pathlib import Path

RECEIPT_NORMALIZED = ("receipt", "receipts")
RECEIPT_CATEGORIES = (1500, 2800)


def find_psi_db():
    p = Path.home() / "Pictures/Photos Library.photoslibrary/database/search/psi.sqlite"
    return str(p) if p.exists() else None


def asset_uuid(uuid_0, uuid_1):
    """Reconstruct ZASSET.ZUUID from psi assets(uuid_0, uuid_1) int halves."""
    return str(_uuid.UUID(bytes=struct.pack("<q", uuid_0) + struct.pack("<q", uuid_1))).upper()


def receipt_uuids(conn):
    """Set of ZUUIDs the Photos ML labeled as receipts (union of both groups)."""
    # Real psi values are NUL-terminated ("receipt\x00") — match both forms.
    norms = [*RECEIPT_NORMALIZED, *(n + "\x00" for n in RECEIPT_NORMALIZED)]
    ph_cat = ",".join("?" for _ in RECEIPT_CATEGORIES)
    ph_norm = ",".join("?" for _ in norms)
    rows = conn.execute(
        f"SELECT DISTINCT a.uuid_0, a.uuid_1 FROM groups g "
        f"JOIN ga ON ga.groupid = g.rowid JOIN assets a ON a.rowid = ga.assetid "
        f"WHERE g.category IN ({ph_cat}) AND g.normalized_string IN ({ph_norm})",
        (*RECEIPT_CATEGORIES, *norms),
    ).fetchall()
    return {asset_uuid(u0, u1) for u0, u1 in rows}
