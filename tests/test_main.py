import importlib
import logging
from typing import Any

import pytest

from basis_trade_agent.config import AgentConfig

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


def make_config(**overrides: Any) -> AgentConfig:
    return AgentConfig.model_validate({**BASE_CONFIG_FIELDS, **overrides})


def test_merge_runtime_config_updates_mutable_fields_and_recomputes_thresholds() -> None:
    main_module = importlib.reload(importlib.import_module("main"))
    startupConfig = make_config()
    latestConfig = make_config(
        startingCapitalUsdc=250.0,
        minNetYieldAprPercent=4.5,
        hysteresisBandAprPercent=3.0,
        pollIntervalSeconds=15,
        riskTolerance="aggressive",
    )
    mergedConfig = main_module.merge_runtime_config(startupConfig, latestConfig)
    assert mergedConfig.chain == startupConfig.chain
    assert mergedConfig.targetAssetSymbol == startupConfig.targetAssetSymbol
    assert mergedConfig.startingCapitalUsdc == 250.0
    assert mergedConfig.pollIntervalSeconds == 15
    assert mergedConfig.riskTolerance == "aggressive"
    assert mergedConfig.enterNetYieldAprPercent == pytest.approx(6.0)
    assert mergedConfig.exitNetYieldAprPercent == pytest.approx(3.0)


def test_merge_runtime_config_ignores_immutable_fields_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    main_module = importlib.reload(importlib.import_module("main"))
    startupConfig = make_config(chain="arbitrum", targetAssetSymbol="WBTC")
    latestConfig = make_config(chain="arbitrum_sepolia", targetAssetSymbol="ETH", pollIntervalSeconds=30)
    with caplog.at_level(logging.WARNING):
        mergedConfig = main_module.merge_runtime_config(startupConfig, latestConfig)
    assert mergedConfig.chain == "arbitrum"
    assert mergedConfig.targetAssetSymbol == "WBTC"
    assert mergedConfig.pollIntervalSeconds == 30
    assert "ignoring runtime config changes to immutable fields" in caplog.text
    assert "chain" in caplog.text
    assert "targetAssetSymbol" in caplog.text
