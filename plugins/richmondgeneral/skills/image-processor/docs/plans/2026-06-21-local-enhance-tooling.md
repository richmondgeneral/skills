# Local Image-Enhance Tooling (torch/Metal) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a non-generative, faithful local enhancement stage to image-processor — `upres.py` (Real-ESRGAN) and `sharpen.py` (unsharp / NAFNet deblur) — runnable on Apple-Silicon MPS, provisioned once by the code agent and invokable by Cowork over the osascript bridge.

**Architecture:** A dedicated standalone uv venv `~/.cache/rg-enhance` (Python 3.12, torch+torchvision MPS + `spandrel` + PIL/numpy) holds the ML stack, isolated from the plugin's 3.14 env exactly like `~/.cache/rg-matte`. The scripts live in `image-processor/scripts/` and mirror `matte.py` conventions (item-dir mode, `--source`, `label.json` update, actionable stderr if deps missing). Pure logic (scale selection, safe-output paths, `image_pipeline[]` append, unsharp mask) is torch-free and unit-tested in the plugin 3.14 pytest env; torch/`spandrel` are imported lazily only on the inference path so the scripts import cleanly without the heavy stack.

**Tech Stack:** uv, Python 3.12, PyTorch (MPS), `spandrel` (model loader — replaces `realesrgan`/`basicsr`), Pillow, numpy, tesseract (faithfulness OCR check, already a hero_qa dep).

**Source of truth:** `ops/docs/SPEC-local-enhance-tooling.md` (§0 handoff, §2 env, §3 scripts, §4 acceptance, §5 invoke, §6 productize, §7 tiers).

---

## Key decision: `spandrel`, not `realesrgan`+`basicsr`

The spec lists `realesrgan basicsr` but explicitly allows "a maintained fork … packaged inference wrapper; pin versions, basicsr can be finicky." **`basicsr` (PyPI ≤1.4.2) does `from torchvision.transforms.functional_tensor import rgb_to_grayscale`, a module removed in torchvision ≥0.17** — so vanilla `realesrgan` cannot import against any modern MPS torchvision. Rather than pin an ancient torchvision or sed-patch a dependency, use **`spandrel`** (chaiNNer's maintained model-loader): it loads the *same* RealESRGAN `RRDBNet` `.pth` weights with `ModelLoader().load_from_file(...)`, runs on MPS, has **no basicsr dependency**, and **also loads NAFNet/Restormer deblur weights** — one uniform loader for both `upres.py` and `sharpen.py --deblur`. This is squarely within the spec's latitude and removes the single biggest install risk.

If a reviewer insists on the literal stack, the fallback is `realesrgan` + `basicsr` with `torchvision==0.16.*` pinned — documented here but **not** recommended.

---

## Phasing & gates

- **Phase 1 (env) and Phase 2 (bridge parity) are hard gates.** If MPS doesn't work under a non-interactive `do shell script`, the whole handoff premise fails — stop and report before writing inference code. Provisioning is the long pole and `basicsr`-class breakage is the expected failure mode; verify imports *actually run* before proceeding.
- Pure-logic tasks (3, 5) are TDD'd in the plugin 3.14 env and can proceed in parallel with the env build.
- `sharpen.py` ships the deterministic **unsharp** path first (no weights); **NAFNet `--deblur`** is best-effort and degrades to an actionable message if weights don't download cleanly (YAGNI — the 896px upres batch is the real driver).

---

## Task 1: Provision the `~/.cache/rg-enhance` venv (MPS)

**Files:** none in-repo (provisions an on-disk venv). Record exact commands in the CLAUDE.md note at Task 9.

**Step 1: Create the venv (uv fetches 3.12 itself; default Mac python is 3.14)**

```bash
uv venv ~/.cache/rg-enhance --python 3.12
~/.cache/rg-enhance/bin/python --version    # expect: Python 3.12.x
```

**Step 2: Install torch (MPS) + the loader stack**

```bash
uv pip install --python ~/.cache/rg-enhance torch torchvision pillow numpy spandrel
```
Expected: resolves Apple-Silicon (arm64) wheels for torch/torchvision, spandrel pure-Python. No build-from-source.

**Step 3: Verify the imports actually run (this is where basicsr-class breakage shows)**

```bash
~/.cache/rg-enhance/bin/python - <<'PY'
import torch, torchvision, spandrel, PIL, numpy
from spandrel import ModelLoader
print("torch", torch.__version__, "tv", torchvision.__version__, "spandrel", spandrel.__version__)
PY
```
Expected: prints versions, no ImportError. **If this fails, fix here before continuing.**

**Step 4 (Acceptance Test §4.1): MPS present**

```bash
~/.cache/rg-enhance/bin/python -c "import torch; assert torch.backends.mps.is_available(); print('MPS OK')"
```
Expected: `MPS OK`.

**Step 5: Fetch Real-ESRGAN weights to the fixed cache**

```bash
mkdir -p ~/.cache/rg-enhance/weights
curl -L -o ~/.cache/rg-enhance/weights/RealESRGAN_x4plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
curl -L -o ~/.cache/rg-enhance/weights/RealESRGAN_x2plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth
ls -lh ~/.cache/rg-enhance/weights/
```
Expected: two `.pth` files (~64MB each).

**Step 6: Smoke-load a weight through spandrel on MPS**

```bash
~/.cache/rg-enhance/bin/python - <<'PY'
import torch
from spandrel import ModelLoader
m = ModelLoader().load_from_file("/Users/scottybe/.cache/rg-enhance/weights/RealESRGAN_x4plus.pth")
print("loaded:", type(m.model).__name__, "scale:", m.scale)
m.model.to("mps").eval()
print("on MPS OK")
PY
```
Expected: prints architecture + `scale: 4` + `on MPS OK`. No commit (env is outside git).

---

## Task 2: Acceptance Test §4.2 — non-interactive bridge parity (CRITICAL GATE)

**Files:** none. This proves Cowork can drive the env via `do shell script` (non-login, non-interactive shell).

**Step 1: Run the MPS check through osascript (reproduces the bridge environment)**

```bash
osascript -e 'do shell script "/Users/scottybe/.cache/rg-enhance/bin/python -c \"import torch; assert torch.backends.mps.is_available(); print(42)\""'
```
Expected: `42`. (osascript `do shell script` runs `/bin/sh -c` with a minimal, non-login env — same surface Cowork hits over the bridge.)

**Step 2: If it fails (MPS unavailable / lib not found under do-shell-script):** STOP. Do not write inference scripts. Report: the handoff requires this to pass, and the fix (env vars, library paths) belongs here, not in the scripts. Capture the exact error.

**Step 3:** No commit. Note the result for the CLAUDE.md handoff note.

---

## Task 3: `lib`-level shared helpers (TDD, torch-free)

**Files:**
- Create: `skills/plugins/richmondgeneral/skills/image-processor/scripts/enhance_common.py`
- Test: `skills/plugins/richmondgeneral/skills/image-processor/tests/test_enhance_common.py`

These three pure functions are shared by `upres.py` / `sharpen.py` / `enhance.py` (DRY) and run under the plugin 3.14 env (no torch).

**Step 1: Write the failing tests**

```python
# tests/test_enhance_common.py
import json, sys, os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import enhance_common as ec

def test_pick_scale_needs_2x():
    # 896 -> >=1500 : 2x (1792) is enough
    assert ec.pick_scale(896, 1500) == 2

def test_pick_scale_needs_4x():
    assert ec.pick_scale(896, 3000) == 4   # 2x=1792 < 3000, 4x=3584 ok

def test_pick_scale_already_big():
    assert ec.pick_scale(2000, 1500) == 1  # no upscale needed

def test_safe_out_default_suffix(tmp_path):
    src = tmp_path / "hero.png"; src.write_bytes(b"x")
    out = ec.resolve_out(str(src), None, suffix="upres")
    assert Path(out).name == "hero.upres.png"

def test_safe_out_refuses_source_without_out(tmp_path):
    src = tmp_path / "hero.png"; src.write_bytes(b"x")
    out = ec.resolve_out(str(src), None, suffix="upres")
    assert Path(out) != src   # never silently overwrite source

def test_safe_out_explicit_overwrite_allowed(tmp_path):
    src = tmp_path / "hero.png"; src.write_bytes(b"x")
    out = ec.resolve_out(str(src), "hero.png", suffix="upres", item_dir=str(tmp_path))
    assert Path(out) == src   # explicit --out hero.png is allowed to overwrite

def test_append_pipeline_creates_list(tmp_path):
    lj = tmp_path / "label.json"; lj.write_text(json.dumps({"sku": "RG-9999"}))
    ec.append_pipeline(str(tmp_path), {"tool": "upres.py", "model": "x4plus"})
    d = json.loads(lj.read_text())
    assert isinstance(d["image_pipeline"], list) and d["image_pipeline"][0]["tool"] == "upres.py"

def test_append_pipeline_appends(tmp_path):
    lj = tmp_path / "label.json"
    lj.write_text(json.dumps({"image_pipeline": [{"tool": "a"}]}))
    ec.append_pipeline(str(tmp_path), {"tool": "b"})
    d = json.loads(lj.read_text())
    assert [e["tool"] for e in d["image_pipeline"]] == ["a", "b"]
```

**Step 2: Run, verify fail**

Run: `cd skills/plugins/richmondgeneral && uv run pytest skills/richmondgeneral/skills/image-processor/tests/test_enhance_common.py -v`
(Adjust the path to wherever the plugin's pytest resolves the tests dir — match how `test_hero_qa.py` is run.)
Expected: FAIL (`No module named enhance_common`).

**Step 3: Implement `enhance_common.py`**

```python
#!/usr/bin/env python3
"""Shared, torch-free helpers for the local enhance scripts (upres/sharpen/enhance).

Kept importable WITHOUT torch so the pure logic unit-tests run in the plugin's
3.14 env; the heavy ML imports live in upres.py/sharpen.py behind lazy imports.
"""
from __future__ import annotations
import datetime, glob, json, math, os


def pick_scale(src_w: int, target_w: int) -> int:
    """Smallest Real-ESRGAN model scale (1/2/4) so src_w*scale >= target_w.
    1 means 'already big enough, skip the model'."""
    if src_w >= target_w:
        return 1
    need = target_w / src_w
    return 2 if need <= 2 else 4


def resolve_source(item_dir: str, source: str | None) -> str:
    """--source filename in item dir, else the first hero.{png,jpg,jpeg}."""
    if source:
        return os.path.join(item_dir, source)
    hits = sorted(g for g in glob.glob(os.path.join(item_dir, "hero.*"))
                  if g.lower().endswith((".png", ".jpg", ".jpeg")))
    if not hits:
        raise FileNotFoundError(f"no hero.* in {item_dir}")
    return hits[0]


def resolve_out(src_path: str, out: str | None, *, suffix: str,
                item_dir: str | None = None) -> str:
    """Safe output path. Default = '<stem>.<suffix><ext>' beside the source
    (NEVER the source itself). An explicit --out may overwrite the source."""
    if out:
        return out if os.path.isabs(out) or item_dir is None else os.path.join(item_dir, out)
    stem, ext = os.path.splitext(src_path)
    return f"{stem}.{suffix}{ext or '.png'}"


def append_pipeline(item_dir: str, entry: dict) -> None:
    """Append a reproducibility record to label.json -> image_pipeline[]."""
    lj = os.path.join(item_dir, "label.json")
    if not os.path.isfile(lj):
        return
    entry.setdefault("timestamp",
                     datetime.datetime.now(datetime.timezone.utc).isoformat())
    entry.setdefault("non_generative", True)
    data = json.load(open(lj, encoding="utf-8"))
    data.setdefault("image_pipeline", []).append(entry)
    with open(lj, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
```

**Step 4: Run, verify pass**

Run the same pytest command. Expected: all PASS.

**Step 5: Commit**

```bash
git add skills/plugins/richmondgeneral/skills/image-processor/scripts/enhance_common.py \
        skills/plugins/richmondgeneral/skills/image-processor/tests/test_enhance_common.py
git commit -m "feat(image-processor): torch-free shared helpers for enhance stage"
```

---

## Task 4: `upres.py` — Real-ESRGAN upscaler

**Files:**
- Create: `skills/plugins/richmondgeneral/skills/image-processor/scripts/upres.py`
- Test: extend `tests/test_enhance_common.py` is enough for pure logic; the inference is covered by acceptance tests (Task 6).

**Step 1: Implement `upres.py`** (torch/spandrel imported lazily; mirrors matte.py)

```python
#!/usr/bin/env python3
"""upres.py — faithful local super-resolution (Real-ESRGAN via spandrel, MPS).

NON-GENERATIVE: a fixed convolutional SR model; it sharpens/enlarges existing
pixels and does NOT invent label text or marks. Safe to auto-run on labeled goods.

ENV: needs the rg-enhance venv (torch + spandrel). Run by absolute path:
  ~/.cache/rg-enhance/bin/python upres.py --item-dir items/RG-XXXX --target-w 1500

CLI:
  upres.py --item-dir items/RG-XXXX [--target-w 1500] [--source hero.png] [--out hero.png]
  upres.py <input> <output> [--target-w 1500]    # ad-hoc, no label.json
"""
from __future__ import annotations
import argparse, os, sys, time

WEIGHTS = os.path.expanduser("~/.cache/rg-enhance/weights")
MODEL_FOR_SCALE = {2: "RealESRGAN_x2plus.pth", 4: "RealESRGAN_x4plus.pth"}

try:
    from PIL import Image
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import enhance_common as ec
except ImportError as e:
    sys.stderr.write(f"upres.py: missing base dep ({e}). Run under ~/.cache/rg-enhance/bin/python\n")
    raise SystemExit(3)


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def _upscale(img: "Image.Image", scale: int) -> "Image.Image":
    """Run the Real-ESRGAN model for the given scale on MPS."""
    import torch
    from spandrel import ModelLoader, ImageModelDescriptor
    path = os.path.join(WEIGHTS, MODEL_FOR_SCALE[scale])
    if not os.path.isfile(path):
        sys.stderr.write(f"upres.py: weights missing: {path}\n")
        raise SystemExit(4)
    model = ModelLoader().load_from_file(path)
    assert isinstance(model, ImageModelDescriptor)
    dev = _device()
    model.to(dev).eval()
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(dev)
    with torch.no_grad():
        out = model(t).clamp(0, 1)
    out = (out.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255.0).round().astype(np.uint8)
    return Image.fromarray(out)


def upres_file(src: str, out: str, target_w: int) -> dict:
    img = Image.open(src)
    sw = img.width
    scale = ec.pick_scale(sw, target_w)
    t0 = time.time()
    if scale == 1:
        result = img.convert("RGB")            # already big enough
        used = "none(skip)"
    else:
        result = _upscale(img, scale)
        used = MODEL_FOR_SCALE[scale]
    # If the model overshot or undershot, Lanczos to >= target while keeping aspect.
    if result.width < target_w:
        h = round(result.height * target_w / result.width)
        result = result.resize((target_w, h), Image.LANCZOS)
    result.save(out)
    return {"tool": "upres.py", "model": used, "scale": scale,
            "src": os.path.basename(src), "out": os.path.basename(out),
            "src_w": sw, "out_w": result.width, "device": _device(),
            "wall_s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Faithful Real-ESRGAN upscale (MPS)")
    ap.add_argument("input", nargs="?"); ap.add_argument("output", nargs="?")
    ap.add_argument("--item-dir"); ap.add_argument("--source")
    ap.add_argument("--out"); ap.add_argument("--target-w", type=int, default=1500)
    ap.add_argument("--no-update-label", action="store_true")
    a = ap.parse_args()

    if a.item_dir:
        src = ec.resolve_source(a.item_dir, a.source)
        out = ec.resolve_out(src, a.out, suffix="upres", item_dir=a.item_dir)
    elif a.input and a.output:
        src, out = a.input, a.output
    else:
        ap.error("provide --item-dir, or both input and output")

    rec = upres_file(src, out, a.target_w)
    if a.item_dir and not a.no_update_label:
        ec.append_pipeline(a.item_dir, rec)
    print(f"upres: {rec['src_w']}px -> {rec['out_w']}px via {rec['model']} "
          f"({rec['device']}, {rec['wall_s']}s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 2: Import-only smoke (no torch needed for arg errors)**

Run: `~/.cache/rg-enhance/bin/python skills/plugins/richmondgeneral/skills/image-processor/scripts/upres.py --help`
Expected: usage prints (proves the file parses + imports under the enhance env).

**Step 3: Commit**

```bash
git add skills/plugins/richmondgeneral/skills/image-processor/scripts/upres.py
git commit -m "feat(image-processor): upres.py — Real-ESRGAN faithful upscale (spandrel/MPS)"
```

---

## Task 5: `sharpen.py` — unsharp (default) + NAFNet deblur (`--deblur`)

**Files:**
- Create: `skills/plugins/richmondgeneral/skills/image-processor/scripts/sharpen.py`
- Test: `tests/test_sharpen.py` (unsharp is deterministic + torch-free → TDD)

**Step 1: Write the failing test**

```python
# tests/test_sharpen.py
import sys, os
from PIL import Image
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sharpen

def test_unsharp_changes_and_is_deterministic(tmp_path):
    src = tmp_path / "g.png"
    arr = (np.random.RandomState(0).rand(64, 64, 3) * 255).astype("uint8")
    Image.fromarray(arr).save(src)
    o1 = tmp_path / "o1.png"; o2 = tmp_path / "o2.png"
    sharpen.sharpen_file(str(src), str(o1), amount=0.6, deblur=False)
    sharpen.sharpen_file(str(src), str(o2), amount=0.6, deblur=False)
    a0 = np.asarray(Image.open(src).convert("RGB"))
    a1 = np.asarray(Image.open(o1).convert("RGB"))
    a2 = np.asarray(Image.open(o2).convert("RGB"))
    assert not np.array_equal(a0, a1)          # it did something
    assert np.array_equal(a1, a2)              # deterministic
```

**Step 2: Run, verify fail** — `No module named sharpen`.

**Step 3: Implement `sharpen.py`**

```python
#!/usr/bin/env python3
"""sharpen.py — deterministic unsharp mask (default) or NAFNet deblur (--deblur).

Default path is pure PIL (no torch) — deterministic, faithful, safe to auto-run.
--deblur loads a NAFNet/Restormer deblur model via spandrel (needs rg-enhance).

CLI:
  sharpen.py --item-dir items/RG-XXXX [--amount 0.6] [--source hero.png] [--out hero.png]
  sharpen.py --item-dir items/RG-XXXX --deblur          # genuinely blurry shots
  sharpen.py <input> <output> [--amount 0.6] [--deblur]
"""
from __future__ import annotations
import argparse, os, sys, time
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enhance_common as ec

DEBLUR_WEIGHTS = os.path.expanduser("~/.cache/rg-enhance/weights/NAFNet-deblur.pth")


def _unsharp(img: "Image.Image", amount: float) -> "Image.Image":
    # amount 0..2 -> percent 0..200; deterministic PIL UnsharpMask
    return img.convert("RGB").filter(
        ImageFilter.UnsharpMask(radius=2, percent=int(amount * 100), threshold=2))


def _deblur(img: "Image.Image") -> "Image.Image":
    import torch, numpy as np
    from spandrel import ModelLoader, ImageModelDescriptor
    if not os.path.isfile(DEBLUR_WEIGHTS):
        sys.stderr.write(
            f"sharpen.py: --deblur needs weights at {DEBLUR_WEIGHTS} (not installed). "
            "Use the default unsharp path, or fetch NAFNet/Restormer deblur weights.\n")
        raise SystemExit(4)
    model = ModelLoader().load_from_file(DEBLUR_WEIGHTS)
    assert isinstance(model, ImageModelDescriptor)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(dev).eval()
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(dev)
    with torch.no_grad():
        out = model(t).clamp(0, 1)
    out = (out.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255.0).round().astype("uint8")
    return Image.fromarray(out)


def sharpen_file(src: str, out: str, amount: float, deblur: bool) -> dict:
    img = Image.open(src)
    t0 = time.time()
    result = _deblur(img) if deblur else _unsharp(img, amount)
    result.save(out)
    return {"tool": "sharpen.py", "model": "NAFNet-deblur" if deblur else "unsharp",
            "amount": None if deblur else amount,
            "src": os.path.basename(src), "out": os.path.basename(out),
            "wall_s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Unsharp (default) or NAFNet deblur")
    ap.add_argument("input", nargs="?"); ap.add_argument("output", nargs="?")
    ap.add_argument("--item-dir"); ap.add_argument("--source"); ap.add_argument("--out")
    ap.add_argument("--amount", type=float, default=0.6)
    ap.add_argument("--deblur", action="store_true")
    ap.add_argument("--no-update-label", action="store_true")
    a = ap.parse_args()
    if a.item_dir:
        src = ec.resolve_source(a.item_dir, a.source)
        out = ec.resolve_out(src, a.out, suffix="sharp", item_dir=a.item_dir)
    elif a.input and a.output:
        src, out = a.input, a.output
    else:
        ap.error("provide --item-dir, or both input and output")
    rec = sharpen_file(src, out, a.amount, a.deblur)
    if a.item_dir and not a.no_update_label:
        ec.append_pipeline(a.item_dir, rec)
    print(f"sharpen: {rec['model']} -> {out} ({rec['wall_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 4: Run, verify pass** — the unsharp test runs in the plugin 3.14 env (PIL present, no torch needed).

**Step 5: Commit**

```bash
git add skills/plugins/richmondgeneral/skills/image-processor/scripts/sharpen.py \
        skills/plugins/richmondgeneral/skills/image-processor/tests/test_sharpen.py
git commit -m "feat(image-processor): sharpen.py — unsharp default + NAFNet --deblur"
```

**Step 6 (best-effort): NAFNet/Restormer deblur weights.** Try a clean HF-hosted mirror of NAFNet-deblur (or Restormer motion-deblur) into `~/.cache/rg-enhance/weights/NAFNet-deblur.pth`; smoke-load via spandrel. If no clean non-GDrive source, leave `--deblur` degrading with the actionable message and note "deblur pending weights" in the CLAUDE.md note. Do not block the plan on this.

---

## Task 6: Acceptance Tests §4.3–§4.5 (faithfulness, idempotence, speed)

**Files:** none new; runs the built scripts on real items. Use a scratch copy so the source hero is never mutated.

**Step 1 (§4.3 faithfulness — known text):** upscale RG-0025 (ATARI 1050) and RG-0045 (RX8030) and confirm the label text is preserved, only sharper.

```bash
~/.cache/rg-enhance/bin/python skills/plugins/richmondgeneral/skills/image-processor/scripts/upres.py \
  items/RG-0025/hero.png /tmp/rg0025.upres.png --target-w 1500
# OCR token check (tesseract is already installed for hero_qa):
tesseract items/RG-0025/hero.png stdout 2>/dev/null | tr 'a-z' 'A-Z' | grep -oE 'ATARI|1050' | sort -u
tesseract /tmp/rg0025.upres.png stdout 2>/dev/null | tr 'a-z' 'A-Z' | grep -oE 'ATARI|1050' | sort -u
```
Expected: the upscaled output recognizes the **same** key tokens (no invented characters). Repeat for RG-0045 / `RX8030`. Also eyeball both for fabricated marks. Record result.

**Step 2 (§4.4 idempotence / safe output):** confirm default never overwrites source.

```bash
ls -l items/RG-0025/hero.png            # note mtime/size
~/.cache/rg-enhance/bin/python .../upres.py --item-dir items/RG-0025 --target-w 1500
ls items/RG-0025/hero.upres.png          # default suffixed output created
ls -l items/RG-0025/hero.png            # UNCHANGED
git -C items checkout -- RG-0025/label.json   # revert the pipeline write made during the test
rm -f items/RG-0025/hero.upres.png
```
Expected: `hero.upres.png` exists; `hero.png` untouched; revert leaves the tree clean.

**Step 3 (§4.5 speed):** capture per-image wall time (printed by the script) for a typical 896px→1500px run. Record the number — it sets Cowork's inline-vs-background threshold (spec §0.3, ~30s).

**Step 4:** No code commit (verification only). Carry the numbers into Task 9's CLAUDE.md note.

---

## Task 7: `enhance.py` convenience wrapper (optional, spec §3)

**Files:** Create `skills/plugins/richmondgeneral/skills/image-processor/scripts/enhance.py`

One pass: matte (optional) → upres → sharpen, with `--skip-matte` / `--skip-upres` / `--skip-sharpen`. matte runs in the *matte* venv, upres/sharpen in the *enhance* venv — so `enhance.py` shells out to each by absolute interpreter path rather than importing them (clean cross-venv boundary, same pattern as the spec's file-boundary rule).

```python
#!/usr/bin/env python3
"""enhance.py — one-pass faithful chain: [matte] -> upres -> sharpen.
Each stage runs in its own venv via subprocess (clean cross-version boundary)."""
from __future__ import annotations
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATTE_PY = os.path.expanduser("~/.cache/rg-matte/bin/python")
ENHANCE_PY = os.path.expanduser("~/.cache/rg-enhance/bin/python")


def run(py, script, *args):
    cmd = [py, os.path.join(HERE, script), *args]
    print("+", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item-dir", required=True)
    ap.add_argument("--target-w", type=int, default=1500)
    ap.add_argument("--skip-matte", action="store_true")
    ap.add_argument("--skip-upres", action="store_true")
    ap.add_argument("--skip-sharpen", action="store_true")
    ap.add_argument("--deblur", action="store_true")
    a = ap.parse_args()
    if not a.skip_upres:
        run(ENHANCE_PY, "upres.py", "--item-dir", a.item_dir, "--target-w", str(a.target_w), "--out", "hero.png")
    if not a.skip_sharpen:
        run(ENHANCE_PY, "sharpen.py", "--item-dir", a.item_dir, *(["--deblur"] if a.deblur else []), "--out", "hero.png")
    if not a.skip_matte:
        run(MATTE_PY, "matte.py", "--item-dir", a.item_dir)
    print("enhance: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Commit:
```bash
git add skills/plugins/richmondgeneral/skills/image-processor/scripts/enhance.py
git commit -m "feat(image-processor): enhance.py — one-pass matte->upres->sharpen wrapper"
```

---

## Task 8: Full test suite green

**Step 1:** Run the plugin test suite the same way the repo does (match `test_hero_qa.py`'s invocation).

Run: `cd skills/plugins/richmondgeneral && uv run pytest skills/.../image-processor/tests/ -q`
Expected: all green (existing + `test_enhance_common.py` + `test_sharpen.py`). Per superpowers:verification-before-completion, paste the actual summary line before claiming pass.

---

## Task 9: Productize (spec §6) — dual-copy, docs, SOP

Follow the concurrent-writer rules in the root CLAUDE.md: **explicit paths, never `git add -A`**; for co-edited files (CLAUDE.md, SKILL.md) use the **throwaway-worktree** pattern; `git log origin/main..main` before any push; never `--force`.

**Step 1: Dual-copy scripts → plugin cache** (Cowork's code-mode runs the cache copy)
```bash
rsync -a --exclude=__pycache__ \
  skills/plugins/richmondgeneral/skills/image-processor/scripts/ \
  ~/.claude/plugins/cache/richmondgeneral/*/skills/image-processor/scripts/
# verify upres.py/sharpen.py/enhance.py/enhance_common.py landed in cache
```

**Step 2: SKILL.md** — bump version, add the three scripts + the env line (`~/.cache/rg-enhance`, py3.12 torch/MPS, spandrel) and the generative-guard reminder. Mirror the existing changelog style.

**Step 3: Root `CLAUDE.md` operating-rule note** (newest-on-top) — record: env path + exact provision commands, the 3.12/3.14 split rationale, spandrel-not-basicsr decision, bridge-parity result, per-image wall time, and the faithful-only / generative-judge-gated tier. Land via throwaway worktree off `origin/main`.

**Step 4: Listing SOP** — add a `--upres`/`--sharpen` mention to `ops/docs/RG-listing-SOP.md` photo section.

**Step 5: TASKS.md** — check off / update items 2–3 (the local-tooling eval) with the decisions made (spandrel, Real-ESRGAN, unsharp-first, deblur status, BEN2 still open).

**Step 6: Commit per repo, explicit paths.** `skills/` (scripts+tests+SKILL.md+plan), `ops/` (SOP), root (CLAUDE.md+TASKS.md) — separate commits. `git log origin/main..main` then push only on clean fast-forward.

---

## Done = all of:
- `~/.cache/rg-enhance` builds; MPS true **and** passes non-interactive `do shell script` parity (§4.1–4.2).
- `upres.py` + `sharpen.py` (+ `enhance.py`) work; faithfulness/idempotence/speed verified on RG-0025 & RG-0045 (§4.3–4.5).
- All pytest green; scripts dual-copied to cache; SKILL.md/CLAUDE.md/SOP/TASKS updated; committed per-repo and pushed clean.
- Out of scope (separate todos): BEN2-vs-BiRefNet A/B; SUPIR/genai showcase path; catalog-wide backfill run.
