from item_model.measurements import compute_oversize, OVERSIZE_THRESHOLD_IN


def test_threshold_is_24():
    assert OVERSIZE_THRESHOLD_IN == 24.0


def test_no_dims_is_not_oversize():
    assert compute_oversize(None) is False
    assert compute_oversize({}) is False


def test_long_side_over_24_is_oversize():
    assert compute_oversize({"l": 26, "w": 12, "h": 7}) is True   # RG-0009 box


def test_all_within_24_is_not_oversize():
    assert compute_oversize({"l": 18, "w": 11, "h": 7}) is False


def test_exactly_24_is_not_oversize():
    assert compute_oversize({"l": 24, "w": 24, "h": 24}) is False  # strictly greater


def test_accepts_list_form_and_strings():
    assert compute_oversize([26, 12, 7]) is True
    assert compute_oversize({"l": "26", "w": "12", "h": "7"}) is True
