import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from basis_trade_agent.chat_tool import AgentRuntimeState, ChatTool, ChatToolInput
from basis_trade_agent.gmx_client import ShortPosition
from basis_trade_agent.tools import GetConfigTool, GetCurrentPositionTool, GetWalletHoldingsTool, UpdateConfigTool

EXAMPLE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.example.yaml"


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    destination = tmp_path / "config.yaml"
    shutil.copy(EXAMPLE_CONFIG_PATH, destination)
    return destination


def make_runtime_state(configPath: Path, gmxClient: SimpleNamespace | None = None) -> AgentRuntimeState:
    return AgentRuntimeState(
        walletContext=SimpleNamespace(account=SimpleNamespace(address="0xWALLET")),
        gmxClient=gmxClient or SimpleNamespace(),
        marketTokens=SimpleNamespace(usdcAddress="0xUSDC", targetAssetAddress="0xWBTC"),
        configPath=configPath,
    )


def make_position() -> ShortPosition:
    return ShortPosition(sizeUsd=1000.0, sizeUsdRaw=int(1000 * 10**30), collateralAmountRaw=500_000_000, markPrice=60000.0, liquidationPrice=50000.0)


def test_get_config_tool_returns_current_config_as_yaml(config_path: Path) -> None:
    tool = GetConfigTool()
    result = tool.execute(runtimeState=make_runtime_state(config_path), params=tool.paramsSchema())
    parsed = yaml.safe_load(result)
    assert parsed["chain"] == "arbitrum"
    assert parsed["minNetYieldAprPercent"] == 5.0


def test_update_config_tool_applies_changes_and_reports_new_thresholds(config_path: Path) -> None:
    tool = UpdateConfigTool()
    params = tool.paramsSchema(minNetYieldAprPercent=10.0, hysteresisBandAprPercent=6.0)
    result = tool.execute(runtimeState=make_runtime_state(config_path), params=params)
    assert "Updated config" in result
    assert "enterNetYieldAprPercent=13.00%" in result
    assert "exitNetYieldAprPercent=7.00%" in result
    rewrittenConfig = yaml.safe_load(config_path.read_text())
    assert rewrittenConfig["minNetYieldAprPercent"] == 10.0
    assert rewrittenConfig["hysteresisBandAprPercent"] == 6.0


def test_update_config_tool_with_no_fields_returns_message_without_writing(config_path: Path) -> None:
    originalText = config_path.read_text()
    tool = UpdateConfigTool()
    result = tool.execute(runtimeState=make_runtime_state(config_path), params=tool.paramsSchema())
    assert result == "No fields were provided to update."
    assert config_path.read_text() == originalText


def test_get_wallet_holdings_tool_returns_holdings_from_gmx_client(config_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fakeHoldings = {"walletAddress": "0xWALLET", "ethBalance": 1.5, "usdcBalance": 100.0, "WBTCBalance": 0.01}
    monkeypatch.setattr("basis_trade_agent.tools.get_wallet_holdings", lambda walletContext, marketTokens: fakeHoldings)
    tool = GetWalletHoldingsTool()
    result = tool.execute(runtimeState=make_runtime_state(config_path), params=tool.paramsSchema())
    parsed = yaml.safe_load(result)
    assert parsed["ethBalance"] == 1.5
    assert parsed["usdcBalance"] == 100.0


def test_get_current_position_tool_reports_open_position(config_path: Path) -> None:
    position = make_position()
    gmxClient = SimpleNamespace(get_short_position=lambda marketTokens, walletAddress: position)
    tool = GetCurrentPositionTool()
    result = tool.execute(runtimeState=make_runtime_state(config_path, gmxClient=gmxClient), params=tool.paramsSchema())
    parsed = yaml.safe_load(result)
    assert parsed["sizeUsd"] == 1000.0
    assert parsed["markPrice"] == 60000.0
    assert parsed["liquidationBufferPercent"] == pytest.approx(abs(50000.0 - 60000.0) / 60000.0 * 100)


def test_get_current_position_tool_reports_no_open_position(config_path: Path) -> None:
    gmxClient = SimpleNamespace(get_short_position=lambda marketTokens, walletAddress: None)
    tool = GetCurrentPositionTool()
    result = tool.execute(runtimeState=make_runtime_state(config_path, gmxClient=gmxClient), params=tool.paramsSchema())
    assert result == "No position is currently open."


class MockRaisingToolInput(ChatToolInput):
    pass


class MockRaisingTool(ChatTool):
    def __init__(self) -> None:
        super().__init__(name="mock_raising_tool", description="Always raises for testing the error boundary.", paramsSchema=MockRaisingToolInput)

    def execute_inner(self, runtimeState: AgentRuntimeState, params: MockRaisingToolInput) -> str:
        raise RuntimeError("boom")


def test_chat_tool_execute_converts_raised_exception_to_error_string(config_path: Path) -> None:
    tool = MockRaisingTool()
    result = tool.execute(runtimeState=make_runtime_state(config_path), params=tool.paramsSchema())
    assert "mock_raising_tool" in result
    assert "boom" in result
