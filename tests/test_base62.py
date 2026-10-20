import pytest

from shortlink.base62 import decode, encode


@pytest.mark.parametrize("value", [1, 9, 61, 62, 3843, 2**31, 2**63 - 1])
def test_round_trip(value):
    assert decode(encode(value)) == value


@pytest.mark.parametrize("code", ["", "0", "01", "-", "abc!", "zzzzzzzzzzzz"])
def test_invalid_code(code):
    with pytest.raises(ValueError):
        decode(code)


def test_zero_is_not_a_link_id():
    with pytest.raises(ValueError):
        encode(0)
