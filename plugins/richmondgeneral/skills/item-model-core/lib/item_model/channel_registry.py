from __future__ import annotations
import copy
from typing import Dict, List, Optional
from .models import Channel

# Registry channel keys that are SALES channels (github_page is the page itself, not a channel).
REGISTRY_CHANNEL_KEYS: Dict[str, Channel] = {
    "square": Channel.SQUARE,
    "whatnot": Channel.WHATNOT,
    "ebay": Channel.EBAY,
    "marketplace": Channel.MARKETPLACE,
}
LISTED_STATUSES = {"listed", "active", "live"}   # canonical "listed"; aliases accepted
_SOLD_STATES = {"sold", "archived"}


def listed_on_from_registry(channels: dict) -> List[Channel]:
    """Sales channels (excluding github_page) whose status marks them actively listed."""
    out: List[Channel] = []
    for key, ch in REGISTRY_CHANNEL_KEYS.items():
        entry = channels.get(key)
        if isinstance(entry, dict) and str(entry.get("status", "")).strip().lower() in LISTED_STATUSES:
            out.append(ch)
    return out


def sold_from_label(label: dict, status_json: Optional[dict]) -> bool:
    """Unified sold-state: status.json status==sold, OR item state in {Sold,Archived},
    OR any channel status == 'sold'."""
    if status_json and str(status_json.get("status", "")).strip().lower() == "sold":
        return True
    if str(label.get("state", "")).strip().lower() in _SOLD_STATES:
        return True
    for entry in (label.get("channels") or {}).values():
        if isinstance(entry, dict) and str(entry.get("status", "")).strip().lower() == "sold":
            return True
    return False


def set_channel_status(label: dict, channel: str, status: str, **ids) -> dict:
    """Return a copy of `label` with one channel's status (and any platform IDs) set.

    Merges {status, **ids} onto the existing channels.<channel> entry, preserving its
    other keys and leaving all OTHER channels untouched. The channel entry is created if
    absent. Sold is sticky: if the channel's current status is 'sold', the label is
    returned UNCHANGED for that channel — mirrors page_writer's "never downgrade a sold
    channel" rule. The caller's input is not mutated (deep-copied).
    """
    out = copy.deepcopy(label)
    channels = out.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    entry = channels.get(channel)
    if not isinstance(entry, dict):
        entry = {}
    if str(entry.get("status", "")).strip().lower() == "sold":
        return out
    channels[channel] = {**entry, "status": status, **ids}
    out["channels"] = channels
    return out
