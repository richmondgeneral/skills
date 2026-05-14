#!/usr/bin/env python3
"""
Centralized onboarding queue for rg-full-auto batch processing.

Maintains a single queue file in the ops repo that tracks all items
currently being onboarded, their statuses, and pending questions.

Queue file: <queue_path> (default: ops/inventory/onboarding-queue.json)
This provides a dashboard view across all in-flight items while
per-item .state.json files hold the detailed phase-level state.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_QUEUE_PATH = "/Users/scottybe/workspace/square/ops/inventory/onboarding-queue.json"


@dataclass
class QueueEntry:
    """Summary record for one item in the centralized queue."""
    sku: str
    status: str                          # mirrors ItemStatus.value
    source_image: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    phases_completed: int = 0
    phases_total: int = 10
    pending_questions: int = 0

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


@dataclass
class OnboardingQueue:
    """Mutable queue object. `load_from_disk` is automatic on construction
    if the queue file exists; `save()` writes back."""
    queue_path: str = DEFAULT_QUEUE_PATH
    entries: List[QueueEntry] = field(default_factory=list)

    def __post_init__(self):
        path = Path(self.queue_path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.entries = [QueueEntry(**e) for e in data.get("entries", [])]

    def upsert(self, entry: QueueEntry) -> None:
        """Insert new, or update existing entry with the same SKU."""
        for i, e in enumerate(self.entries):
            if e.sku == entry.sku:
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def remove(self, sku: str) -> None:
        self.entries = [e for e in self.entries if e.sku != sku]

    def find(self, sku: str) -> Optional[QueueEntry]:
        return next((e for e in self.entries if e.sku == sku), None)

    def save(self) -> None:
        """Atomic write — create parent dir, write to temp, rename."""
        path = Path(self.queue_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": [asdict(e) for e in self.entries],
        }
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
