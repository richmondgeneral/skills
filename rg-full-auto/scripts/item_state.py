#!/usr/bin/env python3
"""
Per-item state machine for rg-full-auto batch onboarding.

Tracks each item through the 10-phase pipeline independently.
State persists as .state.json inside each item's folder, enabling:
- Resume after failures
- Async user clarification (park → continue)
- Cross-session persistence

State file: <items_dir>/RG-XXXX/.state.json
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"       # Waiting on user input or external dependency
    SKIPPED = "skipped"       # Intentionally skipped (e.g., no Whatnot listing)


class ItemStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    BLOCKED = "blocked"       # At least one phase needs user input
    COMPLETED = "completed"
    FAILED = "failed"         # Unrecoverable failure
