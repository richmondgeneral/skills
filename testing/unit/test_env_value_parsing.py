"""
Tests for parse_env_value in refresh_item_image.py and upload_to_square.py.

Both skills carry independent .env parsers because there is no shared
utility module across skills. The same test battery runs against both
to keep them honest.

Reviewer-found bugs the new helper fixes:
  - refresh_item_image's parser didn't strip quotes or inline `#` comments
    at all, so KEY=tok # prod returned 'tok # prod' and failed auth silently.
  - upload_to_square's parser stripped quotes BEFORE inline `#`, so a quoted
    value containing `#` (base64 padding chars etc.) got truncated.
"""
import pytest

import refresh_item_image  # square-image-upload
import upload_to_square    # square-image-upload-cowork


@pytest.fixture(params=[
    refresh_item_image.parse_env_value,
    upload_to_square.parse_env_value,
], ids=["square-image-upload", "square-image-upload-cowork"])
def parse(request):
    return request.param


def test_plain_token_unchanged(parse):
    assert parse("sq0atp-xxxxxxxx") == "sq0atp-xxxxxxxx"


def test_outer_whitespace_stripped(parse):
    assert parse("  sq0atp-xxxxxxxx  ") == "sq0atp-xxxxxxxx"


def test_inline_comment_stripped_unquoted(parse):
    """Reviewer's case: `KEY=tok # prod` must yield `tok`, not `tok # prod`."""
    assert parse("sq0atp-xxxxxxxx # prod token") == "sq0atp-xxxxxxxx"


def test_inline_comment_without_leading_space_also_stripped(parse):
    """Conservative convention: unquoted `#` ALWAYS starts a comment.
    Users who need `#` in the value should quote it."""
    assert parse("sq0atp-xxxxxxxx#prod") == "sq0atp-xxxxxxxx"


def test_double_quoted_value_unwrapped(parse):
    assert parse('"sq0atp-xxxxxxxx"') == "sq0atp-xxxxxxxx"


def test_single_quoted_value_unwrapped(parse):
    assert parse("'sq0atp-xxxxxxxx'") == "sq0atp-xxxxxxxx"


def test_quoted_value_preserves_hash(parse):
    """Reviewer's other case: when the user explicitly quotes a value
    containing `#`, the `#` must NOT be treated as a comment marker."""
    assert parse('"sq0atp-with#hash"') == "sq0atp-with#hash"


def test_quoted_value_preserves_inner_whitespace(parse):
    assert parse('"   spaced   "') == "   spaced   "


def test_mismatched_quotes_not_stripped(parse):
    """If only one side has a quote, don't strip — the value is malformed
    or contains a literal quote, and we shouldn't mangle it further."""
    assert parse('"sq0atp') == '"sq0atp'


def test_empty_value(parse):
    assert parse("") == ""


def test_whitespace_only(parse):
    assert parse("   ") == ""


def test_quoted_value_with_trailing_comment(parse):
    """A `.env` line of `KEY="value" # comment` must yield `value`.

    The naive `val[0] == val[-1]` close-quote detector misses this: the last
    char is `t` (from `comment`), not `"`, so the value falls through to the
    unquoted branch and returns `"value` (leading quote intact). Silent 401
    against Square in production."""
    assert parse('"sq0atp-xxxxxxxx"  # prod') == "sq0atp-xxxxxxxx"
