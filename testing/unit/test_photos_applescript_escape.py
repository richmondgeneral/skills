"""
Tests for _as_applescript_quoted in image-processor/lib/photos.py — verifies
strings going into AppleScript double-quoted literals are escaped so a `"`
or `\\` in user input (filename, UUID, dest path) can't terminate the
literal and inject AppleScript code.

We import lib/photos.py by absolute path because there's a name collision
with scripts/photos.py (both auto-added to sys.path by conftest), and the
scripts version wins resolution order. importlib.util sidesteps the
collision.
"""
import importlib.util
from pathlib import Path

_LIB_PHOTOS = (Path(__file__).resolve().parent.parent.parent
               / "image-processor" / "lib" / "photos.py")
_spec = importlib.util.spec_from_file_location("_lib_photos", _LIB_PHOTOS)
_lib_photos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lib_photos)

q = _lib_photos._as_applescript_quoted


def test_plain_string_passes_through_unchanged():
    assert q("IMG_1234.jpg") == "IMG_1234.jpg"


def test_double_quote_is_escaped():
    """A `"` in the middle of a value must become `\\"` so it doesn't
    terminate the surrounding AppleScript string literal."""
    assert q('foo"bar') == 'foo\\"bar'


def test_backslash_is_escaped_before_quote_handling():
    """`\\` must escape first, otherwise our own `\\"` escape gets re-escaped."""
    assert q("foo\\bar") == "foo\\\\bar"


def test_backslash_quote_pair_escaped_correctly():
    """The dangerous input `foo\\"bar` (literal backslash + quote) must become
    `foo\\\\\\"bar` — backslash doubled, quote escaped — so when AppleScript
    parses the literal it sees a backslash followed by a quote character, not
    an escaped quote that terminates early."""
    assert q('foo\\"bar') == 'foo\\\\\\"bar'


def test_classic_injection_payload_neutralized():
    """The reviewer-supplied attack: uuid containing `"; do shell script ...`.
    After escaping, every `"` in the input is preceded by a `\\`, so the
    entire payload becomes a single inert AppleScript string value — no
    syntactic break-out."""
    payload = 'x"; do shell script "rm -rf ~"; --'
    escaped = q(payload)
    # Every `"` in the escaped output must be preceded by a `\`.
    for i, ch in enumerate(escaped):
        if ch == '"':
            assert i > 0 and escaped[i - 1] == "\\", (
                f"unescaped quote at index {i} in {escaped!r}")
    # And: the count of `"` is preserved (we didn't drop any).
    assert escaped.count('"') == payload.count('"')


def test_empty_string_passes_through():
    assert q("") == ""


def test_newlines_preserved_as_value():
    """Newlines are kept verbatim — they're safe inside an AppleScript string
    literal (they don't terminate it the way `"` does)."""
    assert q("foo\nbar") == "foo\nbar"
