from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.cutoff import is_before_cutoff

WAW = ZoneInfo("Europe/Warsaw")


def waw(*args) -> datetime:
    return datetime(*args, tzinfo=WAW)


def test_summer_order_before_cutoff_is_accepted():
    assert is_before_cutoff(date(2027, 7, 15), waw(2027, 7, 14, 13, 59)) is True


def test_summer_order_at_cutoff_is_rejected():
    assert is_before_cutoff(date(2027, 7, 15), waw(2027, 7, 14, 14, 0)) is False


def test_summer_order_after_cutoff_is_rejected():
    assert is_before_cutoff(date(2027, 7, 15), waw(2027, 7, 14, 16, 30)) is False


def test_order_two_days_ahead_is_accepted():
    assert is_before_cutoff(date(2027, 7, 16), waw(2027, 7, 14, 18, 0)) is True


def test_winter_order_before_cutoff_is_accepted():
    assert is_before_cutoff(date(2027, 1, 15), waw(2027, 1, 14, 13, 30)) is True


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        is_before_cutoff(date(2027, 7, 15), datetime(2027, 7, 14, 12, 0))
