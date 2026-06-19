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
    listed_on: list[Channel] = field(default_factory=list)
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
