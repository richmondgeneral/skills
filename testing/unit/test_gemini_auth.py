"""
Tests for Gemini API-key handling: the key must travel in the x-goog-api-key
HEADER (not the URL query string), and any response.text we surface to the
user must have key-shaped substrings redacted in case Google's error body
echoes the rejected credential.

Covers three independent call sites that share the same fix:
  - image-processor/lib/models/nano_banana.py
  - image-processor/lib/models/gemini25.py
  - square-image-upload/scripts/rotate_item_images.py
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


_REPO = Path(__file__).resolve().parent.parent.parent / "plugins" / "richmondgeneral" / "skills"
# Provider modules use `from base import ...` as their absolute-import fallback
# (the `from .base import ...` relative form fails when we load by file path
# rather than as a package).
_MODELS_DIR = _REPO / "image-processor" / "lib" / "models"
if str(_MODELS_DIR) not in sys.path:
    sys.path.insert(0, str(_MODELS_DIR))


def _load_module(rel_path: str, name: str):
    """Load a module by absolute path so collisions with same-named scripts
    elsewhere in sys.path don't matter."""
    spec = importlib.util.spec_from_file_location(name, _REPO / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


base = _load_module("image-processor/lib/models/base.py", "_base_mod")


# ============================================================================
# redact_api_key — pure function
# ============================================================================

def test_redact_strips_google_api_key():
    """A real-shaped Google key gets replaced with the redaction marker."""
    fake = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456"  # AIza + 35 chars
    msg = f"Bad credentials: key={fake} was rejected."
    assert fake not in base.redact_api_key(msg)
    assert "<redacted-api-key>" in base.redact_api_key(msg)


def test_redact_multiple_keys_in_one_message():
    fake1 = "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"[:39]
    fake2 = "AIzaSyBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"[:39]
    msg = f"primary={fake1} fallback={fake2}"
    out = base.redact_api_key(msg)
    assert fake1 not in out
    assert fake2 not in out
    assert out.count("<redacted-api-key>") == 2


def test_redact_leaves_non_key_strings_alone():
    msg = "AIza_short and AlphaBetaGamma123 — neither matches."
    assert base.redact_api_key(msg) == msg


def test_redact_handles_empty_and_none_safe():
    assert base.redact_api_key("") == ""
    assert base.redact_api_key(None) is None


# ============================================================================
# nano_banana / gemini25: key goes in header, not URL
# ============================================================================

@pytest.fixture
def fake_post():
    """Patch requests.post to capture the call args and return a 401 with
    the rejected key echoed back in the body — the realistic leak vector."""
    with patch("requests.post") as p:
        p.return_value.status_code = 401
        p.return_value.text = ('{"error":{"message":"API key '
                               'AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456 '
                               'expired"}}')
        yield p


def _instantiate_and_call_detect_subject(provider_module, fake_post):
    """Both providers expose _detect_subject(image_path); construct with a
    fake key and a dummy image, expect Exception, return the (exc, post_call_args)."""
    cls = (getattr(provider_module, "NanaBananaModel", None)
           or getattr(provider_module, "Gemini25FlashModel"))
    m = cls(api_key="AIzaSyTEST" + "X" * 30)
    # _detect_subject opens the file via `open(path, 'rb')`, so a real (small)
    # file is needed.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff\xd9")  # minimal JPEG marker bytes
        img_path = f.name
    try:
        with pytest.raises(Exception) as exc_info:
            m._detect_subject(img_path)
    finally:
        Path(img_path).unlink(missing_ok=True)
    return exc_info.value, fake_post.call_args


def test_nano_banana_sends_key_in_header_not_url(fake_post):
    nb = _load_module("image-processor/lib/models/nano_banana.py", "_nb_mod")
    _, call_args = _instantiate_and_call_detect_subject(nb, fake_post)
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
    headers = call_args.kwargs.get("headers", {})
    assert "key=" not in url, f"key still in URL: {url}"
    assert "AIza" not in url, f"key fragment in URL: {url}"
    assert headers.get("x-goog-api-key", "").startswith("AIza")


def test_gemini25_sends_key_in_header_not_url(fake_post):
    g25 = _load_module("image-processor/lib/models/gemini25.py", "_g25_mod")
    _, call_args = _instantiate_and_call_detect_subject(g25, fake_post)
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
    headers = call_args.kwargs.get("headers", {})
    assert "key=" not in url
    assert "AIza" not in url
    assert headers.get("x-goog-api-key", "").startswith("AIza")


def test_nano_banana_redacts_key_from_401_exception_message(fake_post):
    nb = _load_module("image-processor/lib/models/nano_banana.py", "_nb_mod2")
    exc, _ = _instantiate_and_call_detect_subject(nb, fake_post)
    msg = str(exc)
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456" not in msg, (
        f"leaked key in exception: {msg}")
    assert "<redacted-api-key>" in msg


def test_gemini25_redacts_key_from_401_exception_message(fake_post):
    g25 = _load_module("image-processor/lib/models/gemini25.py", "_g25_mod2")
    exc, _ = _instantiate_and_call_detect_subject(g25, fake_post)
    msg = str(exc)
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456" not in msg
    assert "<redacted-api-key>" in msg


# ============================================================================
# rotate_item_images: same patterns, separate skill, separate redactor
# ============================================================================

def test_rotate_item_images_sends_key_in_header(fake_post, tmp_path):
    import rotate_item_images as rim
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")

    with pytest.raises(RuntimeError):
        rim._gemini_call(img.read_bytes(), "image/jpeg",
                         "AIzaSyTEST" + "X" * 30)

    call_args = fake_post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
    headers = call_args.kwargs.get("headers", {})
    assert "key=" not in url, f"key still in URL: {url}"
    assert headers.get("x-goog-api-key", "").startswith("AIza")


def test_rotate_item_images_redacts_key_from_error_message(fake_post, tmp_path):
    import rotate_item_images as rim
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")

    with pytest.raises(RuntimeError) as exc_info:
        rim._gemini_call(img.read_bytes(), "image/jpeg",
                         "AIzaSyTEST" + "X" * 30)

    msg = str(exc_info.value)
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456" not in msg
    assert "<redacted-api-key>" in msg
