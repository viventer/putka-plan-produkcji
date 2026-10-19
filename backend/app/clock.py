from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# Orders are accepted until 14:00 Europe/Warsaw on the day before delivery.
WARSAW = ZoneInfo("Europe/Warsaw")
CUTOFF_TIME = time(14, 0)


def get_now() -> datetime:
    return datetime.now(WARSAW)


def cutoff_for(delivery_date: date) -> datetime:
    """Instant at which an order for `delivery_date` stops being accepted."""
    order_day = delivery_date - timedelta(days=1)
    return datetime.combine(order_day, CUTOFF_TIME, tzinfo=WARSAW)


def is_before_cutoff(delivery_date: date, now: datetime) -> bool:
    """Whether `now` is still early enough to order for `delivery_date`.

    `now` must be timezone-aware. Exactly 14:00 Europe/Warsaw is rejected.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now < cutoff_for(delivery_date)
