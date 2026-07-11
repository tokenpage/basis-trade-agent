from datetime import datetime, timedelta, timezone

from basis_trade_agent.rates import RateHistory


def test_multiple_appends_within_window_are_all_retained_and_averaged() -> None:
    history = RateHistory(windowHours=24)
    baseTime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history.append(baseTime, 4.0)
    history.append(baseTime + timedelta(hours=1), 6.0)
    history.append(baseTime + timedelta(hours=2), 8.0)
    assert history.smoothed_rate() == 6.0
    assert len(history.samples) == 3


def test_sample_older_than_window_is_pruned_on_next_append() -> None:
    history = RateHistory(windowHours=1)
    baseTime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history.append(baseTime, 100.0)
    history.append(baseTime + timedelta(hours=2), 6.0)
    assert history.smoothed_rate() == 6.0
    assert len(history.samples) == 1


def test_single_append_immediately_returns_that_samples_value() -> None:
    history = RateHistory(windowHours=24)
    history.append(datetime(2026, 1, 1, tzinfo=timezone.utc), 7.5)
    assert history.smoothed_rate() == 7.5
