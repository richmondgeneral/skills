# Item-Model Core + Read-Only `rg-reconcile` — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shared, importable **item-model core** (the cross-channel data model + a pure diff engine) and a **read-only `rg-reconcile`** tool that walks `items/RG-XXXX/` pages, observes each channel the item is on, and reports drift — productizing the 2026-06-18 manual sweep.

**Architecture:** Page (`label.json` + `status.json`) is the spine and holds the *reference* price + lifecycle. Channels (Square, Whatnot) are observed read-only and normalized to a common `ChannelObservation`. A pure function `diff_item(page, observations)` applies the field-authority rules from the design doc — **sold-state is a global CRITICAL invariant; per-channel price divergence is a WARNING unless recorded as intended**. `rg-reconcile` orchestrates: walk pages → run readers → diff → report JSON to `ops/reports/` + console. No writes in this slice (zero production risk).

**Tech Stack:** Python 3.11+ via `uv`; `squareup` SDK (already a dep); `pytest` (dev extra). Shared-lib + `conftest.py` sys.path convention (mirrors `image-processor/lib`).

**Reference design:** `skills/docs/plans/2026-06-18-richmondgeneral-monorepo-design.md` §3–§4.

**Working directory for all commands:** `/Users/scottybe/workspace/richmondgeneral/skills`
**Test runner (confirmed):** `uv run --project plugins/richmondgeneral --extra dev pytest <path> -q`

**Module locations:**
- Core lib: `plugins/richmondgeneral/skills/item-model-core/lib/item_model/`
- Reconcile CLI: `plugins/richmondgeneral/skills/rg-reconcile/scripts/`
- Tests: `testing/unit/`

---

## Task 1: Fix the stale test harness (prerequisite — unblocks the whole suite)

The marketplace migration moved skills under `plugins/richmondgeneral/skills/`, but `testing/conftest.py` still resolves paths from the repo root, so every test that imports a skill module fails at collection.

**Files:**
- Modify: `testing/conftest.py`

**Step 1: Confirm it's broken**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_state.py -q`
Expected: `ModuleNotFoundError: No module named 'item_state'` (collection error).

**Step 2: Repoint the base path**

In `testing/conftest.py`, change the base that `SKILL_DIRS` resolve against to the plugin-nested skills dir, and append the new core lib path:

```python
SKILLS_ROOT = Path(__file__).parent.parent
PLUGIN_SKILLS = SKILLS_ROOT / "plugins" / "richmondgeneral" / "skills"

SKILL_DIRS = [
    "imessage-core/scripts",
    "imessage-archiver/scripts",
    "image-processor/lib",
    "image-processor/scripts",
    "square-image-upload/scripts",
    "square-image-upload-cowork/scripts",
    "square-cache/scripts",
    "square-crm/scripts",
    "rg-full-auto/scripts",
    "product-labeler/scripts",
    "photos-library/scripts",
    "alpaca-market-data/scripts",
    "item-model-core/lib",        # added by this plan
]

for skill_dir in SKILL_DIRS:
    path = PLUGIN_SKILLS / skill_dir          # was: SKILLS_ROOT / skill_dir
    if path.exists():
        sys.path.insert(0, str(path))
```

**Step 3: Verify the existing suite imports again**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_state.py -q`
Expected: `29 passed`.

**Step 4: Commit**

```bash
git add testing/conftest.py
git commit -m "fix(testing): repoint conftest sys.path at plugin-nested skill dirs"
```

> Note: `alpaca-market-data` stays for now; it's removed when trading relocates to AlphaTrade (separate task).

---

## Task 2: Scaffold `item_model` package + core models

**Files:**
- Create: `plugins/richmondgeneral/skills/item-model-core/lib/item_model/__init__.py`
- Create: `plugins/richmondgeneral/skills/item-model-core/lib/item_model/models.py`
- Test: `testing/unit/test_item_model_models.py`

**Step 1: Write the failing test**

```python
# testing/unit/test_item_model_models.py
from item_model.models import (
    Channel, Severity, PageRecord, ChannelObservation, DriftFinding,
)

def test_channel_and_severity_enums():
    assert Channel.SQUARE.value == "square"
    assert Channel.WHATNOT.value == "whatnot"
    assert Severity.CRITICAL.value == "critical"

def test_page_record_defaults():
    p = PageRecord(sku="RG-0009", reference_price=95.0)
    assert p.sold is False
    assert p.intended_channel_prices == {}

def test_channel_observation_and_finding():
    obs = ChannelObservation(channel=Channel.SQUARE, present=True, price=45.0, sold=False)
    assert obs.present and obs.price == 45.0
    f = DriftFinding(sku="RG-0009", field="price", channel=Channel.SQUARE,
                     severity=Severity.WARNING, expected=95.0, actual=45.0, message="x")
    assert f.severity is Severity.WARNING
    assert f.to_dict()["channel"] == "square"
```

**Step 2: Run to verify it fails**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'item_model'`.

**Step 3: Implement**

```python
# .../item-model-core/lib/item_model/__init__.py
"""Shared cross-channel item model + diff engine for Richmond General."""
```

```python
# .../item-model-core/lib/item_model/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Channel(str, Enum):
    SQUARE = "square"
    WHATNOT = "whatnot"
    EBAY = "ebay"
    MARKETPLACE = "marketplace"


class Severity(str, Enum):
    CRITICAL = "critical"   # sold-state conflict — can double-sell a unique item
    WARNING = "warning"     # unintended price divergence
    INFO = "info"           # snapshot / presence note


@dataclass
class PageRecord:
    """The spine: what items/RG-XXXX/ asserts about an item."""
    sku: str
    reference_price: float
    sold: bool = False
    # explicit list of channels the item is listed on; empty => derive from observations
    listed_on: list[Channel] = field(default_factory=list)
    # channel -> intentionally-different price (suppresses WARNING when matched)
    intended_channel_prices: Dict[Channel, float] = field(default_factory=dict)


@dataclass
class ChannelObservation:
    """Read-only normalized state of an item on one channel."""
    channel: Channel
    present: bool
    price: Optional[float] = None
    sold: Optional[bool] = None   # True if channel marks it sold/unavailable


@dataclass
class DriftFinding:
    sku: str
    field: str            # "price" | "sold_state" | "presence"
    channel: Channel
    severity: Severity
    expected: Any
    actual: Any
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.sku,
            "field": self.field,
            "channel": self.channel.value,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
        }
```

**Step 4: Run to verify it passes**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_models.py -q`
Expected: `3 passed`.

**Step 5: Commit**

```bash
git add plugins/richmondgeneral/skills/item-model-core/lib/item_model/ testing/unit/test_item_model_models.py
git commit -m "feat(item-model): core models (Channel, PageRecord, ChannelObservation, DriftFinding)"
```

---

## Task 3: Page reader (`label.json` + `status.json` → `PageRecord`)

**Files:**
- Create: `.../item-model-core/lib/item_model/page_reader.py`
- Test: `testing/unit/test_item_model_page_reader.py`

**Step 1: Write the failing test**

```python
# testing/unit/test_item_model_page_reader.py
import json
from item_model.page_reader import read_page_record
from item_model.models import Channel

def _write_item(items_dir, sku, label, status=None):
    d = items_dir / sku
    d.mkdir(parents=True)
    (d / "label.json").write_text(json.dumps(label), encoding="utf-8")
    if status is not None:
        (d / "status.json").write_text(json.dumps(status), encoding="utf-8")
    return d

def test_reads_reference_price_and_defaults(tmp_path):
    _write_item(tmp_path, "RG-0009", {"sku": "RG-0009", "price": "95.00"})
    rec = read_page_record(tmp_path / "RG-0009")
    assert rec.sku == "RG-0009"
    assert rec.reference_price == 95.0
    assert rec.sold is False

def test_status_json_marks_sold(tmp_path):
    _write_item(tmp_path, "RG-0003",
                {"sku": "RG-0003", "price": "25.00"},
                {"status": "sold"})
    rec = read_page_record(tmp_path / "RG-0003")
    assert rec.sold is True

def test_optional_listed_on_and_intended_prices(tmp_path):
    _write_item(tmp_path, "RG-0016", {
        "sku": "RG-0016", "price": "7.00",
        "listed_on": ["square", "whatnot"],
        "intended_channel_prices": {"whatnot": 6.0},
    })
    rec = read_page_record(tmp_path / "RG-0016")
    assert Channel.WHATNOT in rec.listed_on
    assert rec.intended_channel_prices[Channel.WHATNOT] == 6.0
```

**Step 2: Run to verify it fails**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_page_reader.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'item_model.page_reader'`.

**Step 3: Implement**

```python
# .../item-model-core/lib/item_model/page_reader.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Union
from .models import PageRecord, Channel


def read_page_record(item_dir: Union[str, Path]) -> PageRecord:
    """Build a PageRecord from items/<SKU>/label.json (+ optional status.json)."""
    item_dir = Path(item_dir)
    label = json.loads((item_dir / "label.json").read_text(encoding="utf-8"))

    sku = label["sku"]
    reference_price = float(label["price"])

    sold = False
    status_file = item_dir / "status.json"
    if status_file.exists():
        status = json.loads(status_file.read_text(encoding="utf-8"))
        sold = str(status.get("status", "")).lower() == "sold"

    listed_on = [Channel(c) for c in label.get("listed_on", [])]
    intended = {
        Channel(k): float(v)
        for k, v in label.get("intended_channel_prices", {}).items()
    }
    return PageRecord(
        sku=sku,
        reference_price=reference_price,
        sold=sold,
        listed_on=listed_on,
        intended_channel_prices=intended,
    )
```

**Step 4: Run to verify it passes**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_page_reader.py -q`
Expected: `3 passed`.

**Step 5: Commit**

```bash
git add plugins/richmondgeneral/skills/item-model-core/lib/item_model/page_reader.py testing/unit/test_item_model_page_reader.py
git commit -m "feat(item-model): page reader (label.json + status.json -> PageRecord)"
```

---

## Task 4: The diff engine (the heart — pure function, fully unit-tested)

**Files:**
- Create: `.../item-model-core/lib/item_model/diff.py`
- Test: `testing/unit/test_item_model_diff.py`

**Step 1: Write the failing tests** (encode the field-authority rules)

```python
# testing/unit/test_item_model_diff.py
from item_model.diff import diff_item
from item_model.models import (
    Channel, Severity, PageRecord, ChannelObservation,
)

def _page(**kw):
    return PageRecord(sku=kw.get("sku", "RG-0001"),
                      reference_price=kw.get("reference_price", 10.0),
                      sold=kw.get("sold", False),
                      listed_on=kw.get("listed_on", []),
                      intended_channel_prices=kw.get("intended_channel_prices", {}))

def test_no_findings_when_aligned():
    page = _page(reference_price=10.0)
    obs = [ChannelObservation(Channel.SQUARE, present=True, price=10.0, sold=False)]
    assert diff_item(page, obs) == []

def test_unintended_price_divergence_is_warning():
    page = _page(reference_price=95.0)
    obs = [ChannelObservation(Channel.SQUARE, present=True, price=45.0, sold=False)]
    findings = diff_item(page, obs)
    assert len(findings) == 1
    assert findings[0].field == "price"
    assert findings[0].severity is Severity.WARNING

def test_intended_override_suppresses_price_warning():
    page = _page(reference_price=7.0, intended_channel_prices={Channel.WHATNOT: 6.0})
    obs = [ChannelObservation(Channel.WHATNOT, present=True, price=6.0, sold=False)]
    assert diff_item(page, obs) == []

def test_sold_page_but_channel_active_is_critical():
    page = _page(sold=True)
    obs = [ChannelObservation(Channel.SQUARE, present=True, price=10.0, sold=False)]
    findings = diff_item(page, obs)
    assert any(f.field == "sold_state" and f.severity is Severity.CRITICAL
               for f in findings)

def test_channel_sold_but_page_active_is_critical():
    page = _page(sold=False)
    obs = [ChannelObservation(Channel.WHATNOT, present=True, price=10.0, sold=True)]
    findings = diff_item(page, obs)
    assert any(f.field == "sold_state" and f.severity is Severity.CRITICAL
               for f in findings)

def test_findings_sorted_critical_first():
    page = _page(reference_price=95.0, sold=True)
    obs = [ChannelObservation(Channel.SQUARE, present=True, price=45.0, sold=False)]
    findings = diff_item(page, obs)
    assert findings[0].severity is Severity.CRITICAL
```

**Step 2: Run to verify it fails**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_diff.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'item_model.diff'`.

**Step 3: Implement**

```python
# .../item-model-core/lib/item_model/diff.py
from __future__ import annotations
from typing import List
from .models import PageRecord, ChannelObservation, DriftFinding, Severity

_SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


def diff_item(page: PageRecord, observations: List[ChannelObservation]) -> List[DriftFinding]:
    """Apply field-authority rules. Returns findings sorted by severity (critical first)."""
    findings: List[DriftFinding] = []

    for obs in observations:
        if not obs.present:
            continue

        # 1) sold-state invariant (GLOBAL, CRITICAL): page and every channel must agree.
        if obs.sold is not None and obs.sold != page.sold:
            findings.append(DriftFinding(
                sku=page.sku, field="sold_state", channel=obs.channel,
                severity=Severity.CRITICAL, expected=page.sold, actual=obs.sold,
                message=(f"sold-state mismatch: page sold={page.sold} but "
                         f"{obs.channel.value} sold={obs.sold} — risk of double-sale"),
            ))

        # 2) price vs reference (WARNING) — skipped on sold items and intended overrides.
        if not page.sold and obs.price is not None:
            intended = page.intended_channel_prices.get(obs.channel)
            target = intended if intended is not None else page.reference_price
            if abs(obs.price - target) > 0.005:
                kind = "intended" if intended is not None else "reference"
                findings.append(DriftFinding(
                    sku=page.sku, field="price", channel=obs.channel,
                    severity=Severity.WARNING, expected=target, actual=obs.price,
                    message=(f"{obs.channel.value} price {obs.price} != {kind} {target}"),
                ))

    findings.sort(key=lambda f: _SEVERITY_ORDER[f.severity])
    return findings
```

**Step 4: Run to verify it passes**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_diff.py -q`
Expected: `6 passed`.

**Step 5: Commit**

```bash
git add plugins/richmondgeneral/skills/item-model-core/lib/item_model/diff.py testing/unit/test_item_model_diff.py
git commit -m "feat(item-model): diff engine (global sold-state invariant + price-vs-reference)"
```

---

## Task 5: Square read adapter (live → `ChannelObservation`, read-only)

Normalizes a live Square catalog item to a `ChannelObservation`. Uses the `squareup` SDK already used by `safe_batch_reprice.py`. Read-only (search + read; no writes).

**Files:**
- Create: `.../item-model-core/lib/item_model/channels/__init__.py` (empty)
- Create: `.../item-model-core/lib/item_model/channels/square_reader.py`
- Test: `testing/unit/test_item_model_square_reader.py`

**Step 1: Write the failing test** (inject a fake client — no network)

```python
# testing/unit/test_item_model_square_reader.py
from item_model.channels.square_reader import observe_square
from item_model.models import Channel

class _FakeVariation:
    def __init__(self, sku, amount):
        self.item_variation_data = type("V", (), {
            "sku": sku,
            "price_money": type("M", (), {"amount": amount})(),
        })()

def test_absent_sku_returns_not_present():
    index = {}  # sku -> (price_cents, sold_out)
    obs = observe_square("RG-9999", index=index)
    assert obs.channel is Channel.SQUARE and obs.present is False

def test_present_sku_maps_price_and_sold():
    index = {"RG-0009": (9500, False)}
    obs = observe_square("RG-0009", index=index)
    assert obs.present is True
    assert obs.price == 95.0
    assert obs.sold is False
```

**Step 2: Run to verify it fails**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_square_reader.py -q`
Expected: FAIL — module not found.

**Step 3: Implement**

Two layers so the diff stays testable without network: a pure `observe_square(sku, index)` mapper, and a `build_square_index(client)` that pulls the live catalog once into `{sku: (price_cents, sold_out)}`.

```python
# .../item-model-core/lib/item_model/channels/square_reader.py
from __future__ import annotations
import os
from typing import Dict, Optional, Tuple
from ..models import Channel, ChannelObservation

SquareIndex = Dict[str, Tuple[int, bool]]   # sku -> (price_cents, sold_out)


def observe_square(sku: str, index: SquareIndex) -> ChannelObservation:
    """Pure mapper: SKU + prebuilt index -> ChannelObservation."""
    if sku not in index:
        return ChannelObservation(channel=Channel.SQUARE, present=False)
    price_cents, sold_out = index[sku]
    return ChannelObservation(
        channel=Channel.SQUARE, present=True,
        price=round(price_cents / 100, 2), sold=bool(sold_out),
    )


def build_square_index(client=None, location_id: Optional[str] = None) -> SquareIndex:
    """Pull live catalog once into {sku: (price_cents, sold_out)}. Read-only.

    location_id resolves from arg -> SQUARE_LOCATION_ID env (default the RG location
    is instance config; do NOT hardcode here — see instance-config seam in the design).
    """
    from square.client import Square  # imported lazily so unit tests need no SDK/network
    if client is None:
        token = os.environ.get("SQUARE_ACCESS_TOKEN") or os.environ.get("SQUARE_TOKEN")
        client = Square(token=token)
    location_id = location_id or os.environ.get("SQUARE_LOCATION_ID")

    index: SquareIndex = {}
    cursor = None
    while True:
        resp = client.catalog.search_items(cursor=cursor) if cursor \
            else client.catalog.search_items()
        for item in (resp.items or []):
            for v in (item.item_data.variations or []):
                vd = v.item_variation_data
                sku = getattr(vd, "sku", None)
                if not sku:
                    continue
                price_cents = getattr(getattr(vd, "price_money", None), "amount", None)
                sold_out = False
                for ov in (getattr(vd, "location_overrides", None) or []):
                    if location_id is None or ov.location_id == location_id:
                        sold_out = bool(getattr(ov, "sold_out", False)) or sold_out
                index[sku] = (price_cents or 0, sold_out)
        cursor = getattr(resp, "cursor", None)
        if not cursor:
            break
    return index
```

> The exact SDK method/attribute names (`search_items`, `location_overrides`, `sold_out`) must be confirmed against the installed `squareup` version during execution — verify with a one-off `uv run` REPL call and adjust. The pure `observe_square` is the unit-tested contract; `build_square_index` is the thin live edge (cover in an integration test, not unit).

**Step 4: Run to verify it passes**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_square_reader.py -q`
Expected: `2 passed`.

**Step 5: Commit**

```bash
git add plugins/richmondgeneral/skills/item-model-core/lib/item_model/channels/ testing/unit/test_item_model_square_reader.py
git commit -m "feat(item-model): Square read adapter (pure mapper + live index builder)"
```

---

## Task 6: Whatnot read adapter (CSV → `ChannelObservation`)

Reads `items/rg-inventory/whatnot-import.csv` into `{sku: (price, status)}`, mirroring the existing CSV conventions in `sync_to_whatnot.py`.

**Files:**
- Create: `.../item-model-core/lib/item_model/channels/whatnot_reader.py`
- Test: `testing/unit/test_item_model_whatnot_reader.py`

**Step 1: Write the failing test**

```python
# testing/unit/test_item_model_whatnot_reader.py
from item_model.channels.whatnot_reader import build_whatnot_index, observe_whatnot
from item_model.models import Channel

CSV = (
    "Title,Price,SKU,Status\n"
    "Boogeyman 2 DVD,7,RG-0016,active\n"
    "Phantasm DVD,11,RG-0017,sold\n"
)

def test_index_and_observe(tmp_path):
    p = tmp_path / "whatnot-import.csv"
    p.write_text(CSV, encoding="utf-8")
    index = build_whatnot_index(str(p))

    o16 = observe_whatnot("RG-0016", index)
    assert o16.channel is Channel.WHATNOT and o16.present and o16.price == 7.0 and o16.sold is False

    o17 = observe_whatnot("RG-0017", index)
    assert o17.sold is True

    assert observe_whatnot("RG-9999", index).present is False
```

**Step 2: Run to verify it fails**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_whatnot_reader.py -q`
Expected: FAIL — module not found.

**Step 3: Implement**

```python
# .../item-model-core/lib/item_model/channels/whatnot_reader.py
from __future__ import annotations
import csv
from pathlib import Path
from typing import Dict, Tuple, Union
from ..models import Channel, ChannelObservation

WhatnotIndex = Dict[str, Tuple[float, bool]]   # sku -> (price, sold)


def build_whatnot_index(csv_path: Union[str, Path]) -> WhatnotIndex:
    index: WhatnotIndex = {}
    path = Path(csv_path)
    if not path.exists():
        return index
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sku = (row.get("SKU") or "").strip()
            if not sku:
                continue
            try:
                price = float((row.get("Price") or "0").strip())
            except ValueError:
                price = 0.0
            sold = (row.get("Status") or "").strip().lower() == "sold"
            index[sku] = (price, sold)
    return index


def observe_whatnot(sku: str, index: WhatnotIndex) -> ChannelObservation:
    if sku not in index:
        return ChannelObservation(channel=Channel.WHATNOT, present=False)
    price, sold = index[sku]
    return ChannelObservation(channel=Channel.WHATNOT, present=True, price=price, sold=sold)
```

**Step 4: Run to verify it passes**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_item_model_whatnot_reader.py -q`
Expected: `1 passed`.

**Step 5: Commit**

```bash
git add plugins/richmondgeneral/skills/item-model-core/lib/item_model/channels/whatnot_reader.py testing/unit/test_item_model_whatnot_reader.py
git commit -m "feat(item-model): Whatnot CSV read adapter"
```

---

## Task 7: `rg-reconcile` CLI (walk pages → observe → diff → report)

Orchestrates the read-only sweep and writes a timestamped JSON report to `ops/reports/` plus a console summary. Orchestration is unit-tested with injected indexes/fakes; the live edge (`build_square_index`) is wired but not unit-tested.

**Files:**
- Create: `plugins/richmondgeneral/skills/rg-reconcile/scripts/reconcile.py`
- Create: `plugins/richmondgeneral/skills/rg-reconcile/SKILL.md` (brief: read-only drift reconcile)
- Test: `testing/unit/test_reconcile_run.py`

**Step 1: Write the failing test** (inject indexes; no network, no real items dir)

```python
# testing/unit/test_reconcile_run.py
import json
from reconcile import run_reconcile

def _item(items_dir, sku, price, status=None, label_extra=None):
    d = items_dir / sku; d.mkdir(parents=True)
    label = {"sku": sku, "price": price}
    if label_extra:
        label.update(label_extra)
    (d / "label.json").write_text(json.dumps(label), encoding="utf-8")
    if status:
        (d / "status.json").write_text(json.dumps({"status": status}), encoding="utf-8")

def test_run_reports_price_drift_and_sold_conflict(tmp_path):
    items_dir = tmp_path / "items"; items_dir.mkdir()
    _item(items_dir, "RG-0009", "95.00")             # square will show 45 -> WARNING
    _item(items_dir, "RG-0003", "25.00", status="sold")  # square active -> CRITICAL

    square_index = {"RG-0009": (4500, False), "RG-0003": (2500, False)}
    whatnot_index = {}

    report = run_reconcile(
        items_dir=str(items_dir),
        square_index=square_index,
        whatnot_index=whatnot_index,
    )
    sev = {(f["sku"], f["field"]): f["severity"] for f in report["findings"]}
    assert sev[("RG-0009", "price")] == "warning"
    assert sev[("RG-0003", "sold_state")] == "critical"
    assert report["summary"]["critical"] == 1
    assert report["summary"]["warning"] == 1
```

**Step 2: Run to verify it fails**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_reconcile_run.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'reconcile'` (add `rg-reconcile/scripts` to `conftest.py` SKILL_DIRS in this step — append `"rg-reconcile/scripts"`).

**Step 3: Implement**

```python
# plugins/richmondgeneral/skills/rg-reconcile/scripts/reconcile.py
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from typing import Dict, Optional

from item_model.page_reader import read_page_record
from item_model.diff import diff_item
from item_model.models import Channel
from item_model.channels.square_reader import observe_square, build_square_index
from item_model.channels.whatnot_reader import observe_whatnot, build_whatnot_index


def run_reconcile(items_dir: str, square_index: Dict, whatnot_index: Dict) -> dict:
    """Pure orchestration over injected indexes. Returns the report dict."""
    findings = []
    for child in sorted(Path(items_dir).glob("RG-*")):
        if not (child / "label.json").exists():
            continue
        page = read_page_record(child)
        observations = [
            observe_square(page.sku, square_index),
            observe_whatnot(page.sku, whatnot_index),
        ]
        for f in diff_item(page, observations):
            findings.append(f.to_dict())

    summary = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        summary[f["severity"]] = summary.get(f["severity"], 0) + 1
    return {"findings": findings, "summary": summary, "item_count": summary}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only drift reconcile (pages vs channels).")
    ap.add_argument("--items-dir", default=os.environ.get(
        "RG_ITEMS_DIR", str(Path.home() / "workspace" / "richmondgeneral" / "items")))
    ap.add_argument("--whatnot-csv", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    square_index = build_square_index()
    whatnot_csv = args.whatnot_csv or str(
        Path(args.items_dir) / "rg-inventory" / "whatnot-import.csv")
    whatnot_index = build_whatnot_index(whatnot_csv)

    report = run_reconcile(args.items_dir, square_index, whatnot_index)

    out = args.json_out
    if out is None:
        ops_reports = Path(args.items_dir).parent / "ops" / "reports"
        ops_reports.mkdir(parents=True, exist_ok=True)
        out = str(ops_reports / "reconcile-latest.json")  # timestamp via wrapper at call time
    Path(out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    s = report["summary"]
    print(f"Reconcile: {s['critical']} critical, {s['warning']} warning, {s['info']} info")
    for f in report["findings"]:
        print(f"  [{f['severity'].upper():8}] {f['sku']} {f['field']} on {f['channel']}: {f['message']}")
    print(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 4: Run to verify it passes**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/test_reconcile_run.py -q`
Expected: `1 passed`.

**Step 5: Full suite + manual smoke**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/ -q`
Expected: all green (existing 29 + new tests).

Manual (real data, read-only): `cd /Users/scottybe/workspace/richmondgeneral/skills && SQUARE_ACCESS_TOKEN=... SQUARE_LOCATION_ID=B87BAEZ0NWV34 uv run --project plugins/richmondgeneral python plugins/richmondgeneral/skills/rg-reconcile/scripts/reconcile.py --items-dir /Users/scottybe/workspace/richmondgeneral/items`
Expected: a console summary + `ops/reports/reconcile-latest.json`. Today's known drift should now be clean (we healed it), so expect 0 findings — a good real-world assertion.

**Step 6: Commit**

```bash
git add plugins/richmondgeneral/skills/rg-reconcile/ testing/unit/test_reconcile_run.py testing/conftest.py
git commit -m "feat(rg-reconcile): read-only page-vs-channel drift report over the item-model core"
```

---

## Done criteria for this slice
- Test harness fixed; full unit suite green via the confirmed runner.
- `item_model` core importable: models, page reader, diff engine, Square + Whatnot read adapters.
- `rg-reconcile` produces a JSON + console drift report from real data, read-only.
- The 2026-06-18 sweep is now a repeatable command.

## Explicitly deferred to later slices (per design §7)
- **Heal** (`--heal`) + the per-channel write helper (Slice C / write-path).
- **Intake on the core** (`process_batch.py` migration — Slice B).
- eBay/Marketplace adapters (Marketplace = computer-use-only; flag "manual").
- `catalog_state.json` snapshot generation + retiring `catalog_index.jsonl`.
- The `instance-config` seam (replacing the `SQUARE_LOCATION_ID`/path env reads with one config object) — begins genericization.
