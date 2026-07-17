import os, sqlite3, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import psi_db


def test_asset_uuid_little_endian_halves():
    # Live-verified 2026-07-15: psi assets(uuid_0,uuid_1) little-endian halves
    # reconstruct ZASSET.ZUUID EA161386-C707-4F77-B85A-B90BCD4864C9.
    u0 = struct.unpack("<q", bytes.fromhex("EA161386C7074F77"))[0]
    u1 = struct.unpack("<q", bytes.fromhex("B85AB90BCD4864C9"))[0]
    assert u0 == 0x774F07C7861316EA  # signed value as sqlite stores it
    assert psi_db.asset_uuid(u0, u1) == "EA161386-C707-4F77-B85A-B90BCD4864C9"


def _mini_psi(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE groups(category INT2, content_string TEXT, normalized_string TEXT);
        CREATE TABLE ga(groupid INT, assetid INT);
        CREATE TABLE assets(uuid_0 INT, uuid_1 INT, creationDate INT);
        """
    )
    # NB: real psi content_string AND normalized_string carry a trailing NUL.
    conn.execute("INSERT INTO groups(rowid, category, content_string, normalized_string) "
                 "VALUES (685, 1500, 'Receipt' || char(0), 'receipt' || char(0))")
    conn.execute("INSERT INTO groups(rowid, category, content_string, normalized_string) "
                 "VALUES (684, 2800, 'Receipts' || char(0), 'receipts' || char(0))")
    conn.execute("INSERT INTO groups(rowid, category, content_string, normalized_string) "
                 "VALUES (1, 1500, 'Dog' || char(0), 'dog' || char(0))")
    u0 = struct.unpack("<q", bytes.fromhex("EA161386C7074F77"))[0]
    u1 = struct.unpack("<q", bytes.fromhex("B85AB90BCD4864C9"))[0]
    conn.execute("INSERT INTO assets(rowid, uuid_0, uuid_1, creationDate) VALUES (55, ?, ?, 0)", (u0, u1))
    conn.execute("INSERT INTO ga(groupid, assetid) VALUES (685, 55)")
    conn.execute("INSERT INTO ga(groupid, assetid) VALUES (1, 55)")
    conn.commit()
    conn.close()


def test_receipt_uuids_from_mini_psi(tmp_path):
    db = str(tmp_path / "psi.sqlite")
    _mini_psi(db)
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        got = psi_db.receipt_uuids(conn)
    assert got == {"EA161386-C707-4F77-B85A-B90BCD4864C9"}
