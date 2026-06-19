"""Instance-config seam: resolve per-instance constants and the Square token
independent of how the process was launched.

The osascript/mac-bridge runs scripts in a bare, non-login shell, so the
~/.zshrc that normally exports SQUARE_ACCESS_TOKEN from the macOS Keychain never
runs. This module resolves the token in the documented order (env -> Keychain ->
workspace .env), mirroring image-processor/lib/env.py but kept self-contained so
item_model has no cross-skill import dependency.

Per-instance constants (Square location/merchant, GitHub Pages base, items dir)
default to Richmond General but can be overridden via env to genericize the
item_model for another Square merchant.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_WORKSPACE_ENV = Path.home() / "workspace" / "richmondgeneral" / ".env"


def _from_keychain(name: str) -> Optional[str]:
    """macOS Keychain generic password named `name`, or None. Never raises."""
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s", name, "-w"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            v = r.stdout.strip()
            return v or None
    except Exception:
        pass
    return None


def _from_dotenv(name: str, path: Path = _WORKSPACE_ENV) -> Optional[str]:
    """Value of `name` from a KEY=VALUE .env file, or None. Never raises."""
    try:
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == name:
                return v.strip().strip('"').strip("'") or None
    except Exception:
        pass
    return None


def resolve_square_token() -> Optional[str]:
    """Square access token, resolved independent of how the process was launched
    (works over the osascript bridge's bare shell). Order: env SQUARE_ACCESS_TOKEN ->
    env SQUARE_TOKEN -> macOS Keychain (SQUARE_ACCESS_TOKEN) -> workspace .env."""
    for env_name in ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN"):
        v = os.environ.get(env_name)
        if v:
            return v
    v = _from_keychain("SQUARE_ACCESS_TOKEN")
    if v:
        return v
    for env_name in ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN"):
        v = _from_dotenv(env_name)
        if v:
            return v
    return None


@dataclass(frozen=True)
class InstanceConfig:
    location_id: str
    merchant_id: str
    pages_base: str
    items_dir: str


def load_instance_config() -> InstanceConfig:
    """Per-instance constants from env with Richmond General defaults (override via env to
    genericize for another Square merchant)."""
    return InstanceConfig(
        location_id=os.environ.get("SQUARE_LOCATION_ID", "B87BAEZ0NWV34"),
        merchant_id=os.environ.get("SQUARE_MERCHANT_ID", "7MM9AFJAD0XHW"),
        pages_base=os.environ.get("RG_PAGES_BASE", "https://richmondgeneral.github.io/items"),
        items_dir=os.environ.get("RG_ITEMS_DIR", str(Path.home() / "workspace" / "richmondgeneral" / "items")),
    )
