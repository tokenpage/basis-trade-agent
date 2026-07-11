from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from basis_trade_agent.config import AgentConfig
from basis_trade_agent.decision import Action, DecisionState, decide_action
from basis_trade_agent.gmx_client import ShortPosition

BASE_CONFIG_FIELDS: dict[str, Any] = {
    "chain": "arbitrum",
    "targetAssetSymbol": "WBTC",
    "startingCapitalUsdc": 1000.0,
    "minNetYieldAprPercent": 5.0,
    "hysteresisBandAprPercent": 4.0,
    "netRateSmoothingWindowHours": 24,
    "minimumHoldHours": 24,
    "riskTolerance": "conservative",
    "pollIntervalSeconds": 300,
    "slippagePercent": 0.5,
    "liquidationBufferPercent": 15.0,
    "orderFillTimeoutSeconds": 120,
    "minEthReserve": 0.01,
}

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


@pytest.fixture
def make_config():
    def _make(**overrides: Any) -> AgentConfig:
        return AgentConfig(**{**BASE_CONFIG_FIELDS, **overrides})

    return _make


def make_position(markPrice: float = 60000.0, liquidationPrice: float = 50000.0) -> ShortPosition:
    return ShortPosition(
        sizeUsd=1000.0, sizeUsdRaw=1000 * 10**30, collateralAmountRaw=500_000_000, markPrice=markPrice, liquidationPrice=liquidationPrice
    )


def test_no_position_enters_when_smoothed_rate_above_enter_threshold(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=None)
    action = decide_action(state, config, None, 8.0, NOW)
    assert action == Action.ENTER


def test_no_position_stays_none_when_smoothed_rate_below_enter_threshold(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=None)
    action = decide_action(state, config, None, 6.0, NOW)
    assert action == Action.NONE


def test_open_position_in_dead_zone_between_exit_and_enter_stays_none(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=NOW - timedelta(hours=100))
    position = make_position()
    action = decide_action(state, config, position, 5.0, NOW)
    assert action == Action.NONE


def test_open_position_below_exit_but_held_too_short_stays_none(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=NOW - timedelta(hours=1))
    position = make_position()
    action = decide_action(state, config, position, 2.0, NOW)
    assert action == Action.NONE


def test_open_position_below_exit_and_held_long_enough_closes(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=NOW - timedelta(hours=48))
    position = make_position()
    action = decide_action(state, config, position, 2.0, NOW)
    assert action == Action.CLOSE


def test_open_position_at_exit_threshold_and_held_long_enough_closes(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=NOW - timedelta(hours=48))
    position = make_position()
    action = decide_action(state, config, position, config.exitNetYieldAprPercent, NOW)
    assert action == Action.CLOSE


def test_unsafe_margin_emergency_closes_immediately_after_opening(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=NOW)
    position = make_position(markPrice=60000.0, liquidationPrice=57000.0)
    action = decide_action(state, config, position, 100.0, NOW)
    assert action == Action.EMERGENCY_CLOSE


def test_unsafe_margin_emergency_closes_regardless_of_rate_and_held_hours(make_config) -> None:
    config = make_config()
    state = DecisionState(positionOpenedAt=NOW - timedelta(hours=200))
    position = make_position(markPrice=60000.0, liquidationPrice=57000.0)
    action = decide_action(state, config, position, -50.0, NOW)
    assert action == Action.EMERGENCY_CLOSE
