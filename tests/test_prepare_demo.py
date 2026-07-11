import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
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


class MockPrepareDemoGmxClient:
    def __init__(self, position) -> None:
        self.position = position
        self.getShortPositionCalls: list[dict[str, Any]] = []

    def get_short_position(self, marketTokens, walletAddress: str):
        self.getShortPositionCalls.append({"marketTokens": marketTokens, "walletAddress": walletAddress})
        return self.position


def make_config(**overrides: Any) -> AgentConfig:
    return AgentConfig.model_validate({**BASE_CONFIG_FIELDS, **overrides})


def test_prepare_demo_updates_config_and_prints_runbook(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prepare_demo = importlib.reload(importlib.import_module("prepare_demo"))
    configPath = tmp_path / "config.yaml"
    walletContext = SimpleNamespace(account=SimpleNamespace(address="0xWALLET"), web3=SimpleNamespace())
    currentConfig = make_config(targetAssetSymbol="WBTC")
    updatedConfig = make_config(
        startingCapitalUsdc=12.5,
        minNetYieldAprPercent=0.01,
        hysteresisBandAprPercent=0.02,
        netRateSmoothingWindowHours=0.02,
        minimumHoldHours=0,
        riskTolerance="conservative",
        pollIntervalSeconds=15,
        slippagePercent=1.0,
        minEthReserve=0.005,
    )
    marketTokens = SimpleNamespace(marketSymbol="BTC")
    gmxClient = MockPrepareDemoGmxClient(position=None)
    gmxConfigCalls: list[object] = []
    loadConfigCalls: list[Path] = []
    resolveCalls: list[tuple[object, str]] = []
    updateCalls: list[tuple[Path, dict[str, float | int | str]]] = []
    holdingsCalls: list[tuple[object, object]] = []
    readConfig = SimpleNamespace(web3=walletContext.web3)
    holdings = {"walletAddress": "0xWALLET", "ethBalance": 0.25, "usdcBalance": 9.5, "WBTCBalance": 0.0}

    def mock_gmx_config(web3) -> object:
        gmxConfigCalls.append(web3)
        return readConfig

    def mock_load_config(path: Path) -> AgentConfig:
        loadConfigCalls.append(path)
        return currentConfig

    def mock_resolve_market_and_tokens(config, targetAssetSymbol: str):
        resolveCalls.append((config, targetAssetSymbol))
        return marketTokens

    def mock_gmx_client(*, readConfig, writeConfig) -> MockPrepareDemoGmxClient:
        assert readConfig is writeConfig is readConfig
        return gmxClient

    def mock_update_config_file(path: Path, updates: dict[str, float | int | str]) -> AgentConfig:
        updateCalls.append((path, updates))
        return updatedConfig

    def mock_get_wallet_holdings(walletContextArg, marketTokensArg):
        holdingsCalls.append((walletContextArg, marketTokensArg))
        return holdings

    monkeypatch.setattr(prepare_demo, "load_wallet_context", lambda: walletContext)
    monkeypatch.setattr(prepare_demo, "GMXConfig", mock_gmx_config)
    monkeypatch.setattr(prepare_demo, "load_config", mock_load_config)
    monkeypatch.setattr(prepare_demo, "resolve_market_and_tokens", mock_resolve_market_and_tokens)
    monkeypatch.setattr(prepare_demo, "GmxClient", mock_gmx_client)
    monkeypatch.setattr(prepare_demo, "update_config_file", mock_update_config_file)
    monkeypatch.setattr(prepare_demo, "get_wallet_holdings", mock_get_wallet_holdings)
    monkeypatch.setattr(sys, "argv", ["prepare_demo.py", "--config", str(configPath), "--starting-capital-usdc", "12.5"])

    prepare_demo.main()

    assert gmxConfigCalls == [walletContext.web3]
    assert loadConfigCalls == [configPath]
    assert resolveCalls == [(readConfig, currentConfig.targetAssetSymbol)]
    assert gmxClient.getShortPositionCalls == [{"marketTokens": marketTokens, "walletAddress": walletContext.account.address}]
    assert updateCalls == [(configPath, {**prepare_demo.DEMO_CONFIG_UPDATES, "startingCapitalUsdc": 12.5})]
    assert holdingsCalls == [(walletContext, marketTokens)]
    output = capsys.readouterr().out
    assert f"Prepared {configPath} for the live demo." in output
    assert "Wallet state:" in output
    assert "Updated config values:" in output
    assert "  startingCapitalUsdc: 12.5" in output
    assert "  enterNetYieldAprPercent: 0.02" in output
    assert "  exitNetYieldAprPercent: 0.0" in output
    assert "Demo runbook:" in output
    assert "Terminal 1: py agent.py" in output
    assert "Terminal 2: py main.py --config config.yaml" in output
    assert "Watch the loop log 'reloaded config from disk'" in output
    assert "set starting capital to $12.5" in output


def test_prepare_demo_refuses_open_position_without_rewriting_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepare_demo = importlib.reload(importlib.import_module("prepare_demo"))
    configPath = tmp_path / "config.yaml"
    walletContext = SimpleNamespace(account=SimpleNamespace(address="0xWALLET"), web3=SimpleNamespace())
    currentConfig = make_config(targetAssetSymbol="WBTC")
    marketTokens = SimpleNamespace(marketSymbol="BTC")
    gmxClient = MockPrepareDemoGmxClient(position=SimpleNamespace(sizeUsd=321.09))
    updateCalls: list[tuple[Path, dict[str, float | int | str]]] = []
    readConfig = SimpleNamespace(web3=walletContext.web3)

    monkeypatch.setattr(prepare_demo, "load_wallet_context", lambda: walletContext)
    monkeypatch.setattr(prepare_demo, "GMXConfig", lambda web3: readConfig)
    monkeypatch.setattr(prepare_demo, "load_config", lambda path: currentConfig)
    monkeypatch.setattr(prepare_demo, "resolve_market_and_tokens", lambda config, symbol: marketTokens)
    monkeypatch.setattr(prepare_demo, "GmxClient", lambda *, readConfig, writeConfig: gmxClient)
    monkeypatch.setattr(prepare_demo, "update_config_file", lambda path, updates: updateCalls.append((path, updates)))
    monkeypatch.setattr(prepare_demo, "get_wallet_holdings", lambda walletContextArg, marketTokensArg: pytest.fail("holdings should not be queried when a position is already open"))
    monkeypatch.setattr(sys, "argv", ["prepare_demo.py", "--config", str(configPath)])

    with pytest.raises(RuntimeError, match=r"already has an open BTC short \(~\$321\.09\)"):
        prepare_demo.main()

    assert gmxClient.getShortPositionCalls == [{"marketTokens": marketTokens, "walletAddress": walletContext.account.address}]
    assert updateCalls == []
