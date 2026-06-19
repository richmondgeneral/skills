from __future__ import annotations

from typing import Optional, Union

OVERSIZE_THRESHOLD_IN = 24.0  # any single box dimension strictly greater => oversize


def _dims(box) -> list[float]:
    if box is None:
        return []
    vals = box.values() if isinstance(box, dict) else box
    out = []
    for v in vals:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def compute_oversize(box: Optional[Union[dict, list]]) -> bool:
    """True if any box dimension (inches) is strictly greater than 24."""
    return any(d > OVERSIZE_THRESHOLD_IN for d in _dims(box))
