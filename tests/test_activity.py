import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from basis_trade_agent.activity import append_activity_event, get_activity_path, get_tx_explorer_url


class MockDateTime:
    queuedTimes: list[datetime] = []

    @classmethod
    def now(cls, tz: timezone) -> datetime:
        assert tz is timezone.utc
        if not cls.queuedTimes:
            raise AssertionError("MockDateTime ran out of queued timestamps")
        return cls.queuedTimes.pop(0)


def test_get_activity_path_places_state_file_next_to_config() -> None:
    configPath = Path("/tmp/agent/config.yaml")
    assert get_activity_path(configPath) == Path("/tmp/agent/.agent_activity.json")


def test_append_activity_event_timestamps_and_truncates_to_last_twenty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    activityPath = tmp_path / ".agent_activity.json"
    queuedTimes = [datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index) for index in range(21)]
    monkeypatch.setattr("basis_trade_agent.activity.datetime", MockDateTime)
    MockDateTime.queuedTimes = list(queuedTimes)
    for index in range(21):
        append_activity_event(activityPath, {"kind": "order_submitted", "sequence": index})
    activity = json.loads(activityPath.read_text())
    events = activity["events"]
    assert len(events) == 20
    assert [event["sequence"] for event in events] == list(range(1, 21))
    assert events[0]["timestamp"] == queuedTimes[1].isoformat()
    assert events[-1]["timestamp"] == queuedTimes[-1].isoformat()


def test_get_tx_explorer_url_returns_arbiscan_transaction_link() -> None:
    assert get_tx_explorer_url(42161, "0xabc") == "https://arbiscan.io/tx/0xabc"
