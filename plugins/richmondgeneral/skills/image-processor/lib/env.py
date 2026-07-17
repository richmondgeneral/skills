"""Resolve API keys into os.environ when the launching shell didn't export them.

The osascript/mac-bridge shell is a bare, non-login shell, so the ~/.zshrc that
normally exports GEMINI_API_KEY / NANO_BANANA_API_KEY from the macOS Keychain
never runs — and clean.py over the bridge died with "All models failed". The
model constructors read these via os.getenv(), so this resolves each key in the
documented order (existing env -> macOS Keychain -> workspace .env) and sets
os.environ, making resolution independent of how the script was launched.
"""

import os
import subprocess
from pathlib import Path

# Keys the image-processor models look up via os.getenv().
_KEYS = (
    "GEMINI_API_KEY",
    "NANO_BANANA_API_KEY",
    "GOOGLE_API_KEY",
    "REMOVE_BG_API_KEY",
    "REMOVEBG_API_KEY",
)


def _from_keychain(name):
    """macOS Keychain generic password named `name`, or None."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s", name, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:
        pass
    return None


def _dotenv_candidates():
    """Candidate .env paths: every ancestor of this file, then the known workspace .env."""
    cands = [parent / ".env" for parent in Path(__file__).resolve().parents]
    cands.append(Path.home() / "workspace" / "richmondgeneral" / ".env")
    seen, out = set(), []
    for c in cands:
        if c not in seen and c.is_file():
            seen.add(c)
            out.append(c)
    return out


def _from_dotenv(name, candidates):
    for path in candidates:
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == name:
                    value = value.strip().strip('"').strip("'")
                    if value:
                        return value
        except Exception:
            continue
    return None


def bootstrap_keys():
    """Set os.environ for known API keys that aren't already present.

    Order per key: existing env (untouched) -> Keychain -> workspace .env.
    Safe to call repeatedly; never overwrites a key the shell already exported.
    """
    candidates = None
    for name in _KEYS:
        if os.environ.get(name):
            continue
        value = _from_keychain(name)
        if not value:
            if candidates is None:
                candidates = _dotenv_candidates()
            value = _from_dotenv(name, candidates)
        if value:
            os.environ[name] = value
