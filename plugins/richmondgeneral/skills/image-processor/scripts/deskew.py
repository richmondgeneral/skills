#!/usr/bin/env python3
"""
deskew.py — image-processor `flat-goods` profile + tilt gate (RG-0031 RCA, 2026-06-20).

Two features, ported from the validated prototype
(ops/reports/2026-06-20-RG0031-deskew-prototype/), 23/23 tests passing:

  1. deskew_to_face()  -> the `flat-goods` path: detect the flat item's face
     rectangle, perspective-correct it to straight-on, full-bleed crop. NO cutout.
     Backs standardize.py --deskew/--perspective-correct/--crop-to-face.

  2. residual_tilt_deg() -> the tilt check for analyze_mask_quality(): how far
     from level the dominant object rectangle is. The gate forces `manual` when
     residual_tilt_deg >= 1.5 (the check that would have caught the crooked
     RG-0031 hero — its alpha measured 18.18 deg).

Pure cv2 + numpy (added to the plugin deps 2026-06-20). cv2 is imported LAZILY:
on a machine whose uv env has not been synced, _CV2_OK is False and the public
entry points degrade gracefully — deskew_to_face -> needs_manual, and
residual_tilt_deg -> tilt_deg=None (so the gate's `val is None: continue` simply
skips the tilt rule) — rather than crashing the whole pipeline.
"""
from __future__ import annotations
import math
try:
    import numpy as np
    import cv2
    _CV2_OK = True
except Exception:  # pragma: no cover - env without opencv/numpy
    np = None  # type: ignore
    cv2 = None  # type: ignore
    _CV2_OK = False


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Return corners ordered TL, TR, BR, BL."""
    pts = pts.reshape(4, 2).astype("float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype="float32")


def _rect_angle_deg(rrect) -> float:
    """Normalize a cv2.minAreaRect angle to a signed 'how far from level' value
    in (-45, 45]. 0 means edges are axis-aligned.

    cv2.minAreaRect's angle is ambiguous up to a 90 deg swap of (w,h), so a
    folded value near +/-45 is the *same* physical orientation as the other
    sign. We therefore always fold into (-45, 45]; downstream code treats the
    magnitude as 'distance from level' which is well defined in [0,45]."""
    (_, _), (w, h), ang = rrect
    a = ang % 90.0
    if a > 45.0:
        a -= 90.0
    return float(a)


# --------------------------------------------------------------------------
# Object (foreground) segmentation — used by BOTH the gate and detection.
# The old code measured the dilated-edge blob, which for a full-bleed photo is
# the whole *frame* (always ~0 deg) and for a noisy photo collapses to a 45 deg
# artifact. We instead segment the actual dominant object and discard the frame.
# --------------------------------------------------------------------------


def _grabcut_small(bgr: np.ndarray, margin: float, iters: int, cap: int):
    """Run GrabCut on a downscaled copy. Returns (small_fg uint8 0/255, (h,w)).

    The central-rect seed treats the image border as background, so a tilted
    flat object on a busy shelf is separated from clutter (unlike the old
    frame-spanning edge mesh, which always read ~0 deg). For a full-bleed object
    the foreground simply fills the frame -> tilt ~0, which is correct.
    """
    h, w = bgr.shape[:2]
    scale = cap / float(max(h, w))
    if scale < 1.0:
        small = cv2.resize(bgr, (max(8, int(w * scale)), max(8, int(h * scale))),
                           interpolation=cv2.INTER_AREA)
    else:
        small = bgr.copy()
    sh, sw = small.shape[:2]
    mask = np.zeros((sh, sw), np.uint8)
    mx, my = max(1, int(sw * margin)), max(1, int(sh * margin))
    rect = (mx, my, sw - 2 * mx, sh - 2 * my)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(small, mask, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return np.zeros((sh, sw), "uint8"), (h, w)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    return fg, (h, w)


def _object_mask(bgr: np.ndarray, margin: float = 0.04, iters: int = 4,
                 cap: int = 600) -> np.ndarray:
    """Binary mask (uint8 0/255) of the dominant foreground object at full res.

    GrabCut foreground (computed on a <=cap downscale), cleaned with OPEN (drop
    speckle) + CLOSE (fill interior detail) AT THE WORKING RESOLUTION for speed,
    reduced to the single largest filled blob, then upsampled to full res.

    Computed fresh every call. (A previous id(bgr)->mask cache was removed:
    id() is reused after an array is GC'd, so in a batch loop a new same-shape
    image silently received a prior image's mask — that made the straight
    RG-0025 read the tilted RG-0023's 41.6° and made --batch non-deterministic.)
    """
    fg, (h, w) = _grabcut_small(bgr, margin, iters, cap)
    sh, sw = fg.shape[:2]
    if fg.max() != 0:
        ko = max(3, (min(sh, sw) // 60) | 1)
        kc = max(5, (min(sh, sw) // 25) | 1)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ko, ko)))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kc, kc)))
        fg = _largest_filled_blob(fg, sh, sw)
    full = cv2.resize(fg, (w, h), interpolation=cv2.INTER_NEAREST)
    return full


def _largest_filled_blob(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    """Keep the largest connected component, fill holes, return uint8 0/255."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype("uint8"), 8)
    if n <= 1:
        return np.zeros((h, w), "uint8")
    # ignore background label 0; pick biggest by area
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    blob = (lab == idx).astype("uint8") * 255
    # fill interior holes via contour redraw
    cnts, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros((h, w), "uint8")
    if cnts:
        cv2.drawContours(out, [max(cnts, key=cv2.contourArea)], -1, 255, cv2.FILLED)
    return out


def _tilt_from_mask(mask: np.ndarray, h: int, w: int, method: str) -> dict:
    """Measure the dominant blob's rectangle tilt + a rectangularity confidence.

    confidence reflects how trustworthy the *tilt* reading is: it requires a
    sizeable, reasonably rectangular blob. Irregular silhouettes (a brooch, a
    scattered dish set) get low rect_fill -> low confidence -> the gate will not
    flag them on tilt alone.
    """
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return {"tilt_deg": 0.0, "confidence": 0.0, "method": "none",
                "area_frac": 0.0, "rect_fill": 0.0}
    c = max(cnts, key=cv2.contourArea)
    c_area = cv2.contourArea(c)
    area_frac = c_area / float(w * h)
    rr = cv2.minAreaRect(c)
    (_, _), (rw, rh), _ = rr
    rect_area = max(rw * rh, 1.0)
    rect_fill = c_area / rect_area              # ~1.0 for a clean rectangle
    tilt = abs(_rect_angle_deg(rr))
    # Confidence in the TILT reading: big blob AND rectangular blob.
    size_term = min(1.0, area_frac / 0.20)
    rect_term = max(0.0, min(1.0, (rect_fill - 0.5) / 0.4))  # 0.5->0, 0.9->1
    confidence = float(round(size_term * rect_term, 3))
    return {"tilt_deg": round(tilt, 3), "confidence": confidence, "method": method,
            "area_frac": round(area_frac, 3), "rect_fill": round(rect_fill, 3)}


def _border_is_busy(bgr: np.ndarray, ring: float = 0.03) -> bool:
    """True if the image border ring is busy (object content reaches the edge),
    i.e. a tight full-bleed crop rather than a studio/cutout on a quiet bg.

    Used as a fast pre-check for the tilt path: a tight full-bleed crop is
    straight-on by construction, but GrabCut on such a crop is unreliable (it
    latches onto an interior design element and reports that element's tilt).
    The border-texture test sidesteps GrabCut entirely for these.
    """
    h, w = bgr.shape[:2]
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    t = max(2, int(min(h, w) * ring))
    rm = np.zeros((h, w), bool)
    rm[:t, :] = rm[-t:, :] = rm[:, :t] = rm[:, -t:] = True
    edges = cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 40, 120)
    edge_density = float((edges[rm] > 0).mean())
    return (float(g[rm].std()) > 30.0) and (edge_density > 0.04)


# --------------------------------------------------------------------------
# Tilt measurement (for the gate)
# --------------------------------------------------------------------------
def residual_tilt_deg(bgr: np.ndarray, alpha: np.ndarray | None = None) -> dict:
    """Estimate how far the dominant object rectangle is from level.

    If `alpha` is given (a cutout / RGBA hero), measure the alpha mask directly
    — this is the authoritative path for transparent-background heroes and is
    what catches a crooked cutout like the bad RG-0031 hero.

    Otherwise we segment the dominant foreground OBJECT (not the image frame)
    and measure its rectangle. Returns {tilt_deg, confidence, method,
    area_frac, rect_fill}; tilt_deg is abs degrees in [0,45].

    NOTE: a low `confidence` means the tilt reading is untrustworthy (irregular
    or tiny object); callers/gates should treat low-confidence as 'do not flag
    on tilt' rather than as a tilt of zero.
    """
    if not _CV2_OK:
        return {"tilt_deg": None, "confidence": 0.0, "method": "cv2_unavailable"}
    h, w = bgr.shape[:2]
    if alpha is not None:
        mask = (alpha > 8).astype("uint8") * 255
        mask = _largest_filled_blob(mask, h, w)
        return _tilt_from_mask(mask, h, w, "alpha")

    # Full-bleed pre-check: a tight crop whose object content reaches the border
    # is straight-on by construction (tilt 0). Short-circuit before GrabCut,
    # which on such a crop unreliably latches onto an interior design element.
    if _border_is_busy(bgr):
        return {"tilt_deg": 0.0, "confidence": 0.95, "method": "full_bleed",
                "area_frac": 1.0, "rect_fill": 1.0}
    mask = _object_mask(bgr)
    return _tilt_from_mask(mask, h, w, "edges")


# --------------------------------------------------------------------------
# Face-quad detection + deskew (the flat-goods path)
# --------------------------------------------------------------------------
def _quad_dims(corners: np.ndarray) -> tuple[float, float, float]:
    """Return (avg_width, avg_height, aspect=w/h) of an ordered TL,TR,BR,BL quad."""
    wT = np.linalg.norm(corners[1] - corners[0])
    wB = np.linalg.norm(corners[2] - corners[3])
    hL = np.linalg.norm(corners[3] - corners[0])
    hR = np.linalg.norm(corners[2] - corners[1])
    ww = (wT + wB) / 2.0
    hh = (hL + hR) / 2.0
    return ww, hh, (ww / hh if hh else 0.0)


def _fit_quad(contour: np.ndarray) -> np.ndarray:
    """Fit a 4-corner convex quad to a contour.

    Prefer approxPolyDP on the convex hull (hugs the true rectangle, ignoring
    background bleed in the bounding box); fall back to minAreaRect's box.
    """
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    for eps in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08):
        ap = cv2.approxPolyDP(hull, eps * peri, True)
        if len(ap) == 4 and cv2.isContourConvex(ap):
            return _order_corners(ap.astype("float32"))
    box = cv2.boxPoints(cv2.minAreaRect(contour))
    return _order_corners(box.astype("float32"))


def detect_face_quad(bgr: np.ndarray) -> dict:
    """Detect the flat item's face as a 4-corner quad.

    Strategy: GrabCut-segment the dominant object (central-rect seed treats the
    border as background, so shelf clutter is excluded), take its largest filled
    blob, then fit a tight convex quad via hull+approxPolyDP. This replaces the
    old Canny->dilate->largest-contour path, which engulfed surrounding clutter
    and reported an inflated aspect (~0.86 instead of ~0.64 for the RG-0031 book).

    Returns {ok, corners(TL,TR,BR,BL), confidence, area_frac, aspect, rect_fill}.
    `confidence` blends object size, rectangularity (hull-fill) and a plausible
    aspect; low values should route the caller to manual rather than warp.
    """
    if not _CV2_OK:
        return {"ok": False, "corners": None, "confidence": 0.0,
                "area_frac": 0.0, "aspect": 0.0, "rect_fill": 0.0,
                "mar_rect_fill": 0.0}
    h, w = bgr.shape[:2]
    mask = _object_mask(bgr)
    if mask.max() == 0:
        return {"ok": False, "corners": None, "confidence": 0.0,
                "area_frac": 0.0, "aspect": 0.0, "rect_fill": 0.0,
                "mar_rect_fill": 0.0}
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    c_area = cv2.contourArea(c)
    af = c_area / float(w * h)
    if af < 0.10:
        return {"ok": False, "corners": None, "confidence": round(af, 3),
                "area_frac": round(af, 3), "aspect": 0.0, "rect_fill": 0.0,
                "mar_rect_fill": 0.0}
    corners = _fit_quad(c)
    ww, hh, aspect = _quad_dims(corners)
    quad_area = cv2.contourArea(corners.astype("float32"))
    # rect_fill: how well a quad explains the blob (1.0 == the blob IS the quad).
    # NOTE: this is a *fitted-quad* fill — the hull-quad hugs the blob, so it reads
    # ~1.0 even for a non-rectangular silhouette (a brooch fits a quad fine). It is
    # therefore NOT a rectangularity test; use mar_rect_fill (below) for that.
    rect_fill = c_area / max(quad_area, 1.0)
    rect_fill = min(rect_fill, 1.0)
    # mar_rect_fill: blob area / its min-area (rotated) bounding rect. THIS is the
    # rectangularity signal — ~1.0 for a true rectangle (book/box/card/frame),
    # noticeably lower for an irregular outline (brooch ~0.70, scattered set).
    # deskew_to_face uses it as a hard floor so only rectangular faces are warped.
    (_, _), (mw, mh), _ = cv2.minAreaRect(c)
    mar_rect_fill = min(1.0, c_area / max(mw * mh, 1.0))
    plausible = 0.2 <= aspect <= 5.0
    size_term = min(1.0, af / 0.35)
    rect_term = max(0.0, min(1.0, (rect_fill - 0.55) / 0.35))  # 0.55->0, 0.9->1
    confidence = float(round(size_term * rect_term * (1.0 if plausible else 0.3), 3))
    return {"ok": True, "corners": corners, "confidence": confidence,
            "area_frac": round(af, 3), "aspect": round(aspect, 3),
            "rect_fill": round(rect_fill, 3),
            "mar_rect_fill": round(mar_rect_fill, 3)}


def deskew_to_face(bgr: np.ndarray, min_confidence: float = 0.45,
                   min_rect_fill: float = 0.80) -> dict:
    """flat-goods path: perspective-correct the detected face to straight-on.

    Returns {ok, image, method, angle_in, confidence, needs_manual, reason}.
    If detection confidence < min_confidence -> needs_manual=True (route to queue).

    RECTANGULARITY FLOOR (added 2026-06-20): the flat-goods path is ONLY valid for
    rectangular faces (books / paper / cards / boxed / framed). A perspective warp
    of a non-rectangular silhouette (a brooch, a scattered dish set) is meaningless
    — it forces an irregular blob into a quad. So before warping we require the
    detected face's mar_rect_fill (blob area / its min-area rotated bounding rect)
    >= min_rect_fill. Below that we route to manual with reason="not_rectangular".
    0.80 was chosen empirically: the RG-0022 brooch reads ~0.695 while genuine
    rectangular faces — the RG-0031 book (~0.82), RG-0025 box (~0.82), and the
    synthetic rotations (~0.99) — all sit comfortably above it.
    """
    if not _CV2_OK:
        return {"ok": False, "image": None, "method": "cv2_unavailable",
                "angle_in": None, "confidence": 0.0,
                "needs_manual": True, "reason": "cv2_unavailable"}
    det = detect_face_quad(bgr)
    angle_in = residual_tilt_deg(bgr)["tilt_deg"]
    if not det["ok"] or det["confidence"] < min_confidence:
        return {"ok": False, "image": None, "method": "detect_failed",
                "angle_in": angle_in, "confidence": det["confidence"],
                "needs_manual": True, "reason": "deskew_low_confidence"}
    if det.get("mar_rect_fill", 0.0) < min_rect_fill:
        return {"ok": False, "image": None, "method": "not_rectangular",
                "angle_in": angle_in, "confidence": det["confidence"],
                "needs_manual": True, "reason": "not_rectangular",
                "mar_rect_fill": det.get("mar_rect_fill", 0.0)}
    src = det["corners"]
    wT = np.linalg.norm(src[1] - src[0]); wB = np.linalg.norm(src[2] - src[3])
    hL = np.linalg.norm(src[3] - src[0]); hR = np.linalg.norm(src[2] - src[1])
    ww = int(round((wT + wB) / 2.0)); hh = int(round((hL + hR) / 2.0))
    dst = np.array([[0, 0], [ww - 1, 0], [ww - 1, hh - 1], [0, hh - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(bgr, M, (ww, hh), flags=cv2.INTER_CUBIC)
    return {"ok": True, "image": out, "method": "perspective_warp",
            "angle_in": angle_in, "confidence": det["confidence"],
            "needs_manual": False, "reason": None,
            "out_size": (ww, hh), "aspect": round(ww / hh, 3) if hh else 0}


# --------------------------------------------------------------------------
# CLI (single-image)
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse, json, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--output", "-o")
    ap.add_argument("--measure-only", action="store_true",
                    help="just print residual_tilt_deg of the input")
    a = ap.parse_args()
    img = cv2.imread(a.input)
    if img is None:
        print(json.dumps({"error": f"could not read {a.input}"})); sys.exit(1)
    if a.measure_only:
        print(json.dumps(residual_tilt_deg(img))); sys.exit(0)
    r = deskew_to_face(img)
    meta = {k: v for k, v in r.items() if k != "image"}
    if r["ok"] and a.output:
        cv2.imwrite(a.output, r["image"])
        meta["residual_tilt_after"] = residual_tilt_deg(r["image"])["tilt_deg"]
    print(json.dumps(meta))
