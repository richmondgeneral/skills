# Intake Photo Sorter + Downloads Router — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use @superpowers:test-driven-development for each code task.

**Goal:** Extend the `photos-library` skill so the agent can sort the "Richmond General Intake" album into per-SKU Photos albums **and** `items/RG-XXXX/` folders, keep Intake self-clearing, and route `~/Downloads` photos into the right album — all via one canonical filing path.

**Architecture:** Agent is the brain (clusters, looks at photos, proposes SKU assignments); deterministic scripts are the hands. A single `file_cluster.py` is the only thing that moves item photos (mint? → export to `items/` → add to SKU album → tag + PhotoKit-remove from Intake). The Photos DB is read-only; all mutations go through tested scripts and run only after per-cluster confirmation.

**Tech Stack:** Python 3 (`uv` only), AppleScript (`osascript`), Swift 6.3 (PhotoKit), `sips`. Reuses `find_product_clusters.py`, `extract_photos.py`, `archive_to_album.scpt`, `photos_db.py`, and `rg-full-auto/scripts/sku_authority.py`.

**Paths:**
- Skill source: `/Users/scottybe/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/photos-library/`
- Scripts dir: `…/photos-library/scripts/`
- Tests dir (create): `…/photos-library/tests/`
- Plugin cache mirror: `~/.claude/plugins/cache/richmondgeneral/richmondgeneral/1.1.0/skills/photos-library/`
- Design doc: `…/photos-library/docs/plans/2026-06-19-intake-photo-sorter-design.md`

**Execution note:** `skills` is a shared git checkout with concurrent writers and is on `main`. Recommend a throwaway worktree off the `skills` repo (`git worktree add`) per CLAUDE.md, or at minimum branch first. Stage explicit paths — never `git add -A`. Commit to the `skills` repo only.

---

### Task 0: ✅ CONCLUDED — spike result + revised clear mechanism

**Spike outcome (2026-06-19): PhotoKit is DENIED — do NOT build `intake_remove.swift`.** A bare
`swift script.swift` has no Info.plist usage string, so `PHPhotoLibrary.requestAuthorization` returns
`.denied` (status 2) with no prompt. Verified working instead: AppleScript Automation for Photos +
keyword **write** (set/clear keywords persists). **Revised mechanism:** filing tags `rg-sorted` +
`RG-XXXX` (Task 3), and a new **`clear_intake.scpt`** finalize (Task 4b) deletes & recreates the
"Richmond General Intake" album re-adding only the still-unsorted photos. Photos never leave the
library or their SKU albums. The Swift code below is **superseded — skip it.**

> Superseded reference (PhotoKit approach, not used):

**Files:**
- Create: `scripts/intake_remove.swift`

**Step 1: Write the Swift helper**

```swift
// intake_remove.swift — remove assets from a Photos user album via PhotoKit.
// Usage: swift intake_remove.swift "<Album Name>" <uuid1> [<uuid2> ...]
// Exit codes: 0 ok · 2 usage · 3 not-authorized · 4 album-not-found · 5 change-failed
import Photos
import Foundation

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write("usage: intake_remove.swift <album> <uuid...>\n".data(using: .utf8)!)
    exit(2)
}
let albumName = args[1]
let uuids = Set(args[2...].map { $0.uppercased() })

// Authorization (may show a one-time TCC prompt).
let authSem = DispatchSemaphore(value: 0)
var auth: PHAuthorizationStatus = .notDetermined
PHPhotoLibrary.requestAuthorization(for: .readWrite) { auth = $0; authSem.signal() }
authSem.wait()
guard auth == .authorized else {
    FileHandle.standardError.write("not authorized: \(auth.rawValue)\n".data(using: .utf8)!)
    exit(3)
}

// Locate the user album by title.
let opts = PHFetchOptions()
opts.predicate = NSPredicate(format: "title == %@", albumName)
let colls = PHAssetCollection.fetchAssetCollections(with: .album, subtype: .any, options: opts)
guard let album = colls.firstObject else {
    FileHandle.standardError.write("album not found: \(albumName)\n".data(using: .utf8)!)
    exit(4)
}

// Match assets in the album by bare-UUID prefix of localIdentifier ("UUID/L0/001").
var toRemove: [PHAsset] = []
PHAsset.fetchAssets(in: album, options: nil).enumerateObjects { asset, _, _ in
    let bare = String(asset.localIdentifier.prefix(36)).uppercased()
    if uuids.contains(bare) { toRemove.append(asset) }
}

let chSem = DispatchSemaphore(value: 0)
var chErr: Error?
PHPhotoLibrary.shared().performChanges {
    PHAssetCollectionChangeRequest(for: album)?.removeAssets(toRemove as NSArray)
} completionHandler: { _, err in chErr = err; chSem.signal() }
chSem.wait()
if let e = chErr {
    FileHandle.standardError.write("change failed: \(e)\n".data(using: .utf8)!)
    exit(5)
}
print("removed:\(toRemove.count),album:\(albumName)")
```

**Step 2: Non-destructive auth probe**

Run: `swift scripts/intake_remove.swift "__rg_nonexistent__" 00000000-0000-0000-0000-000000000000`
- **Exit 4** ("album not found") = authorized ✅ — auth works, proceed.
- **Exit 3** ("not authorized") = grant Photos access to the controlling app (System Settings → Privacy & Security → Photos), re-run; if it cannot be granted, STOP and switch to the smart-album fallback in the design doc.
- A one-time TCC prompt on first run is expected — approve it.

**Step 3: Destructive smoke test (manual, throwaway album)**

In Photos.app: make an album `__rg_spike__`, drag any one photo in. Get its UUID:
`python3 -c "import sqlite3,photos_db; …"` (or reuse `query_photos.py --album __rg_spike__`).
Run the helper with that UUID. Expected stdout `removed:1,album:__rg_spike__`; verify the photo left the album but still exists in the library. Delete `__rg_spike__` afterward.

**Step 4: Commit**

```bash
git add scripts/intake_remove.swift
git commit -m "feat(photos-library): PhotoKit remove-from-album helper (intake_remove.swift)"
```

---

### Task 1: Shared originals-path helper + `--uuids` extraction

Lets the agent render one specific cluster (by UUID) to look at, and gives `file_cluster.py` a DRY way to resolve a UUID to its on-disk original.

**Files:**
- Modify: `scripts/photos_db.py` (add `original_relpath`)
- Modify: `scripts/extract_photos.py` (add `--uuids`)
- Test: `tests/test_photos_db.py`

**Step 1: Write the failing test**

```python
# tests/test_photos_db.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import photos_db

def test_original_relpath_uses_first_char_and_ext():
    rel = photos_db.original_relpath("ABC12345-0000-0000-0000-000000000000", "public.jpeg")
    assert rel == "originals/A/ABC12345-0000-0000-0000-000000000000.jpeg"

def test_original_relpath_heic_and_png():
    assert photos_db.original_relpath("b0000000-x", "public.heic").endswith(".heic")
    assert photos_db.original_relpath("b0000000-x", "public.png").endswith(".png")
```

**Step 2: Run to verify it fails**

Run: `cd …/photos-library && python3 -m pytest tests/test_photos_db.py -v`
Expected: FAIL (`AttributeError: module 'photos_db' has no attribute 'original_relpath'`).

**Step 3: Implement `original_relpath`**

```python
# photos_db.py
_UTI_EXT = {"public.jpeg": "jpeg", "public.heic": "heic", "public.png": "png",
            "public.tiff": "tiff", "com.compuserve.gif": "gif"}

def original_relpath(uuid, uti):
    """Path of an original inside a .photoslibrary, e.g. originals/A/<uuid>.jpeg.
    Mirrors the layout used by extract_photos.py / intake_to_item.py."""
    ext = _UTI_EXT.get((uti or "").lower(), "jpeg")
    return f"originals/{uuid[0].upper()}/{uuid}.{ext}"
```

**Step 4: Run to verify it passes** — `python3 -m pytest tests/test_photos_db.py -v` → PASS.

**Step 5: Add `--uuids` to `extract_photos.py`**

Add an argument and a fetch branch that selects assets `WHERE a.ZUUID IN (…)` (parameterized), names each output `<uuid[:8]>.jpeg`, and reuses the existing `sips` conversion + offloaded-reporting. Accept a comma-separated list. Keep `--album`/`--keyword`/`--days` working unchanged.

**Step 6: Manual verify** — `python3 scripts/extract_photos.py --uuids <uuid1>,<uuid2> -o /tmp/rgsee --resize 1024x1024` produces JPEGs; offloaded ones are reported.

**Step 7: Commit**

```bash
git add scripts/photos_db.py scripts/extract_photos.py tests/test_photos_db.py
git commit -m "feat(photos-library): original_relpath helper + extract_photos --uuids"
```

---

### Task 2: `file_cluster.py` pure logic (TDD)

The testable core: SKU resolution, no-clobber filename planning, and label.json stubbing. No Photos side effects yet.

**Files:**
- Create: `scripts/file_cluster.py`
- Test: `tests/test_file_cluster.py`

**Step 1: Write failing tests**

```python
# tests/test_file_cluster.py
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import file_cluster as fc

def test_resolve_sku_explicit_ok():
    assert fc.resolve_sku("RG-0031", mint=False, allocate=None) == "RG-0031"

def test_resolve_sku_rejects_bad_format():
    import pytest
    with pytest.raises(ValueError):
        fc.resolve_sku("0031", mint=False, allocate=None)

def test_resolve_sku_mint_calls_allocator():
    assert fc.resolve_sku(None, mint=True, allocate=lambda: "RG-0099") == "RG-0099"

def test_plan_filenames_hero_when_absent():
    out = fc.plan_filenames(existing=set(), photos=[{"uuid": "u1", "role": "hero"}])
    assert out == [{"uuid": "u1", "out": "hero.jpeg"}]

def test_plan_filenames_hero_demoted_when_present():
    out = fc.plan_filenames(existing={"hero.png"}, photos=[{"uuid": "u1", "role": "hero"}])
    assert out == [{"uuid": "u1", "out": "detail-1.jpeg"}]

def test_plan_filenames_named_detail_and_collision():
    out = fc.plan_filenames(existing={"detail-back.jpeg"},
                            photos=[{"uuid": "u1", "role": "detail-back"},
                                    {"uuid": "u2", "role": None}])
    assert out[0]["out"] == "detail-back-2.jpeg"
    assert out[1]["out"] == "detail-1.jpeg"

def test_stub_label_written_only_when_absent(tmp_path):
    d = tmp_path / "RG-0031"; d.mkdir()
    fc.ensure_label(str(d), "RG-0031")
    data = json.loads((d / "label.json").read_text()); assert data["sku"] == "RG-0031"
    (d / "label.json").write_text('{"sku":"RG-0031","price":"42"}')
    fc.ensure_label(str(d), "RG-0031")  # must not clobber
    assert json.loads((d / "label.json").read_text())["price"] == "42"
```

**Step 2: Run to verify they fail** — `python3 -m pytest tests/test_file_cluster.py -v` → FAIL (module/functions missing).

**Step 3: Implement the pure functions**

```python
# file_cluster.py  (pure-logic section)
import json, os, re

RG_RE = re.compile(r"^RG-\d{4}$")

def resolve_sku(sku, mint, allocate):
    if mint:
        return allocate()                       # 'RG-XXXX' from sku_authority
    if not sku or not RG_RE.match(sku):
        raise ValueError(f"bad SKU {sku!r}; expected RG-XXXX or --mint")
    return sku

def _stem_taken(existing, stem):
    return any(n.rsplit(".", 1)[0] == stem for n in existing)

def plan_filenames(existing, photos):
    """Map each photo to a non-clobbering output name in items/RG-XXXX/.
    hero only if no hero.* exists (else demoted to a detail); detail-<slug> de-duped
    with -2/-3; unroled photos get the next free detail-N.jpeg."""
    names = set(existing); out = []
    def next_detail_n():
        i = 1
        while _stem_taken(names, f"detail-{i}"): i += 1
        return f"detail-{i}"
    for p in photos:
        role = p.get("role")
        if role == "hero" and not _stem_taken(names, "hero"):
            stem = "hero"
        elif role and role.startswith("detail-"):
            stem = role
            if _stem_taken(names, stem):
                k = 2
                while _stem_taken(names, f"{role}-{k}"): k += 1
                stem = f"{role}-{k}"
        else:
            stem = next_detail_n()
        name = f"{stem}.jpeg"; names.add(name)
        out.append({"uuid": p["uuid"], "out": name})
    return out

_STUB = {"sku": "", "product_name": "", "attributes": "", "price": "", "condition": "",
         "condition_notes": "", "measurements_in": {}, "buyer_questions": [], "oversize": False}

def ensure_label(item_dir, sku):
    path = os.path.join(item_dir, "label.json")
    if os.path.exists(path):
        return False
    data = dict(_STUB); data["sku"] = sku
    with open(path, "w") as f: json.dump(data, f, indent=2)
    return True
```

**Step 4: Run to verify they pass** — `python3 -m pytest tests/test_file_cluster.py -v` → PASS.

**Step 5: Commit**

```bash
git add scripts/file_cluster.py tests/test_file_cluster.py
git commit -m "feat(photos-library): file_cluster pure logic (sku/filename/label, TDD)"
```

---

### Task 3: `file_cluster.py` integration wiring + `--plan`

Adds the side-effecting orchestration around the tested core. Side effects are isolated so `--plan` can print intent without mutating anything.

**Files:**
- Modify: `scripts/file_cluster.py`

**Step 1: Add the allocator, originals resolver, exporter, album add, and Intake clear**

- `_allocate()` → shells `uv run python …/rg-full-auto/scripts/sku_authority.py allocate` (relative path from this script), returns the printed `RG-XXXX`. Fail loudly if non-zero (Square unreachable = hard fail, by design).
- `_resolve_originals(uuids)` → open Photos DB **read-only** (`mode=ro&immutable=1`), select `ZUUID, ZUNIFORMTYPEIDENTIFIER, ZFAVORITE` for the UUIDs, build on-disk paths via `photos_db.original_relpath`; collect **offloaded** (missing on disk) separately. Favorite (or agent `hero` role) ranks the hero candidate.
- `_export(mapping, originals, item_dir)` → `sips` each original → `items/RG-XXXX/<out>` at quality 90 (reuse the `sips_convert` pattern from `intake_to_item.py`).
- `_add_to_album(sku, uuids)` → `osascript archive_to_album.scpt <sku> <uuids…>` (existing, idempotent).
- `_tag(sku, uuids)` → `osascript` that, for each matched media item, **reads current keywords and writes back the union** with `rg-sorted` + `<sku>` (preserve existing; AppleScript keyword write verified working). NO removal here — Intake removal is the separate `clear_intake.scpt` finalize (Task 4b). Reference the Intake album via its parent folder ("Richmond General"), the way `archive_to_album.scpt` does.

**Step 2: Wire `main()` with `--plan`**

Args: `--sku`, `--mint`, `--uuids` (comma list), `--role uuid=rolename` (repeatable), `--items-dir` (default `~/workspace/richmondgeneral/items`), `--plan`. Order: resolve SKU (mint may run even in plan? **No** — in `--plan`, print "would mint" and use `RG-NEXT` placeholder; never call `allocate`) → resolve originals (read-only; safe in plan) → `plan_filenames` → if `--plan`, print the table (uuid → out, album, "remove from Intake", offloaded warnings) and exit 0. Otherwise execute export → ensure_label → album add → clear Intake → print a JSON summary.

**Step 3: Dry-run on a real cluster (no mutations)**

Run: `python3 scripts/file_cluster.py --mint --uuids <real_uuids> --plan`
Expected: prints planned filenames, "would mint RG-NEXT", album + Intake-clear intent, any offloaded photos. Verify NOTHING changed in Photos or `items/`.

**Step 4: Commit**

```bash
git add scripts/file_cluster.py
git commit -m "feat(photos-library): file_cluster integration wiring + --plan dry-run"
```

---

### Task 4: `import_to_photos.scpt` (Downloads → album)

**Files:**
- Create: `scripts/import_to_photos.scpt`

**Step 1: Write the AppleScript**

```applescript
-- import_to_photos.scpt — import files into Photos and add to an album under
-- the "Richmond General" folder. Usage:
--   osascript import_to_photos.scpt "<Album Name>" <file1> [<file2> ...]
-- Prints: imported:<n>,album:<name>
on run argv
    if (count of argv) < 2 then error "usage: import_to_photos.scpt <album> <file...>"
    set albumName to item 1 of argv
    set filePaths to items 2 thru -1 of argv
    set rootName to "Richmond General"
    set posixFiles to {}
    repeat with p in filePaths
        set end of posixFiles to (POSIX file (contents of p))
    end repeat
    tell application "Photos"
        if not (exists folder named rootName) then make new folder named rootName
        set rootFolder to item 1 of (every folder whose name is rootName)
        if not (exists album named albumName of rootFolder) then
            make new album named albumName at rootFolder
        end if
        set targetAlbum to item 1 of (every album of rootFolder whose name is albumName)
        import posixFiles into targetAlbum skip check duplicates false
        return "imported:" & (count of posixFiles) & ",album:" & albumName
    end tell
end run
```

**Step 2: Manual test** — drop one test image in `~/Downloads`, run
`osascript scripts/import_to_photos.scpt "Richmond General Intake" ~/Downloads/<test>.jpg`.
Expected `imported:1,album:Richmond General Intake`; verify it appears in Intake.

**Step 3: Commit**

```bash
git add scripts/import_to_photos.scpt
git commit -m "feat(photos-library): import_to_photos.scpt (Downloads -> album)"
```

---

### Task 4b: ❌ SUPERSEDED — `clear_intake.scpt` rebuild abandoned

**Outcome (2026-06-19): the album rebuild was abandoned.** Photos' album deletion is async →
delete+recreate-same-name creates duplicate albums that break references (`-1728`). Replaced by a
**soft delete / queue filter**: `file_cluster.py` tags `rg-sorted`, and
`find_product_clusters.py --hide-sorted` (→ `exclude_keyword_condition` in `photos_db.py`) excludes
sorted photos from the intake scan — reliable, no album mutation. `clear_intake.scpt` was deleted.
The original rebuild spec below is **superseded — skip it.**

> Superseded reference (rebuild approach, not used):

Replaces the superseded PhotoKit helper. AppleScript-only; the finalize step that actually clears Intake.

**Files:**
- Create: `scripts/clear_intake.scpt`

**Step 1: Write the AppleScript**

```applescript
-- clear_intake.scpt — rebuild "Richmond General Intake" with only photos NOT tagged rg-sorted.
-- Photos stay in the library + their SKU albums; only Intake membership changes.
-- Usage: osascript clear_intake.scpt
-- Prints: total:<n>,cleared:<n>,kept:<n>
on run argv
    set folderName to "Richmond General"
    set intakeName to "Richmond General Intake"
    set sortedTag to "rg-sorted"
    tell application "Photos"
        set f to item 1 of (every folder whose name is folderName)
        if not (exists album named intakeName of f) then return "total:0,cleared:0,kept:0"
        set alb to item 1 of (every album of f whose name is intakeName)
        set allItems to (get media items of alb)
        set total to (count of allItems)
        set keepItems to {}
        repeat with mi in allItems
            set kw to keywords of mi
            set isSorted to false
            if kw is not missing value then
                repeat with k in kw
                    if (k as string) is sortedTag then set isSorted to true
                end repeat
            end if
            if not isSorted then set end of keepItems to (contents of mi)
        end repeat
        set kept to (count of keepItems)
        delete alb
        set newAlb to (make new album named intakeName at f)
        if kept > 0 then add keepItems to newAlb
        return "total:" & total & ",cleared:" & (total - kept) & ",kept:" & kept
    end tell
end run
```

**Step 2: Smoke test on a throwaway album first**

Make `__rg_clear_test__` under the "Richmond General" folder with 2 photos; tag one `rg-sorted`
(via the Task 3 `_tag` path or a one-off osascript). Temporarily point the script at that album name,
run it, expect `total:2,cleared:1,kept:1`; verify the album now holds only the untagged photo and both
photos still exist in the library. Restore the album name; delete `__rg_clear_test__`.

**Step 3: Commit**

```bash
git add scripts/clear_intake.scpt
git commit -m "feat(photos-library): clear_intake.scpt (rebuild Intake, AppleScript tag+rebuild)"
```

---

### Task 5: SKILL.md agent-loop playbook + triggers

**Files:**
- Modify: `SKILL.md`

**Step 1:** Bump version (→ 1.7), add a changelog entry, and expand the `description` triggers to include "sort intake photos", "file into SKU", "clear the intake album", "photos from downloads into the right album".

**Step 2:** Add two playbook sections the agent follows:

- **"Sort Intake → SKU lib (agent loop)"**: cluster (`find_product_clusters.py --album "Richmond General Intake"`) → extract each cluster (`extract_photos.py --uuids … --resize 1024x1024 -o /tmp/...`) and **Read** the JPEGs → cross-reference `items/RG-XXXX/` + `label.json` → propose existing-vs-new per cluster with a reason → on confirm run `file_cluster.py` (with `--role` assignments from what you saw; `--mint` for new) → report. Always `--plan` first when unsure. Handle offloaded originals (offer to download in Photos first).
- **"Downloads → proper album (agent decides per photo)"**: list `~/Downloads` images → convert HEIC to temp JPEG to view → **Read** and route each (product → Intake or a clearly-matching SKU; non-product → leave) → confirm → `import_to_photos.scpt` per group → product imports flow into the Intake sorter.

**Step 3:** Document the safety rules inline: read-only DB; irreversible steps only after confirmation; minting hard-fails offline; Intake clear = tag + PhotoKit remove (smart-album fallback noted).

**Step 4: Commit**

```bash
git add SKILL.md
git commit -m "docs(photos-library): agent-loop playbook for intake sorter + downloads router"
```

---

### Task 6: Mirror to cache + end-to-end on ONE real cluster

**Step 1: Run the unit suite** — `cd …/photos-library && python3 -m pytest tests/ -v` → all PASS.

**Step 2: Mirror source → plugin cache** (dual-copy rule):

```bash
rsync -a --exclude=__pycache__ \
  /Users/scottybe/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/photos-library/ \
  ~/.claude/plugins/cache/richmondgeneral/richmondgeneral/1.1.0/skills/photos-library/
```

**Step 3: Live end-to-end on the smallest safe cluster** from the real 24-photo Intake album: cluster → look → `file_cluster.py --plan` → execute → verify (a) `items/RG-XXXX/` has the files, (b) the `RG-XXXX` album exists under "Richmond General" with the photos, (c) those photos are **gone from Intake** but still in the library, (d) `label.json` is consistent. Then decide whether to proceed through the rest of the 24.

**Step 4: Final commit** (if any cache-only tweaks) and stop for review before sweeping all clusters.

```bash
git add -- scripts SKILL.md tests docs
git commit -m "chore(photos-library): mirror intake-sorter to cache + e2e verified"
```

---

## Done when
- `pytest tests/` green; `file_cluster.py --plan` accurate.
- One real cluster filed end-to-end with Intake cleared and folder+album in sync.
- Playbook in `SKILL.md`; source mirrored to cache.
- Remaining 23 Intake photos sortable via the agent loop on demand.
