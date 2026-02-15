from query_helper import QueryHelper


def test_sanitize_escapes_single_quotes():
    raw = "abc'def"
    assert QueryHelper._sanitize(raw) == "abc\\'def"


def test_items_by_category_escapes_injected_value():
    category_id = "cat' || quit() || 'x"
    query = QueryHelper.items_by_category(category_id)

    assert "cat\\' || quit() || \\'x" in query
    assert "mongosh square_cache --eval" in query


def test_search_by_name_escapes_single_quote_pattern():
    pattern = "O'Neil"
    query = QueryHelper.search_by_name(pattern)

    assert "O\\'Neil" in query
    assert "$regex" in query
