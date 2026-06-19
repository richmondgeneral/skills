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
