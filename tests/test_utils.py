import pytest
from datetime import timedelta
from utils.timedelta_parser import parse_timedelta

@pytest.mark.parametrize("input_str, expected_delta", [
    ("30m", timedelta(minutes=30)),
    ("2h", timedelta(hours=2)),
    ("7d", timedelta(days=7)),
    ("1d", timedelta(days=1)),
    ("10m", timedelta(minutes=10)),
    ("30s", None),
    ("1 week", None),
    ("10", None),
    ("", None),
])
def test_parse_timedelta(input_str, expected_delta):
    assert parse_timedelta(input_str) == expected_delta
