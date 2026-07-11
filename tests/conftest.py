from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import Field

from basis_trade_agent.chat_tool import AgentRuntimeState, ChatTool, ChatToolInput


class MockOrderResult:
    def __init__(self, transaction: dict[str, Any]) -> None:
        self.transaction = transaction


class MockSwapOrder:
    instances: list["MockSwapOrder"] = []

    def __init__(self, writeConfig, start_token, out_token) -> None:
        self.writeConfig = writeConfig
        self.startToken = start_token
        self.outToken = out_token
        self.createSwapOrderCalls: list[dict[str, Any]] = []
        MockSwapOrder.instances.append(self)

    def create_swap_order(self, **kwargs: Any) -> MockOrderResult:
        self.createSwapOrderCalls.append(kwargs)
        return MockOrderResult(transaction={"kind": "swap", "startToken": self.startToken, "outToken": self.outToken})


class MockIncreaseOrder:
    instances: list["MockIncreaseOrder"] = []

    def __init__(self, writeConfig, market_key, collateral_address, index_token_address, is_long) -> None:
        self.writeConfig = writeConfig
        self.marketKey = market_key
        self.collateralAddress = collateral_address
        self.indexTokenAddress = index_token_address
        self.isLong = is_long
        self.createIncreaseOrderCalls: list[dict[str, Any]] = []
        MockIncreaseOrder.instances.append(self)

    def create_increase_order(self, **kwargs: Any) -> MockOrderResult:
        self.createIncreaseOrderCalls.append(kwargs)
        return MockOrderResult(transaction={"kind": "increase"})


class MockDecreaseOrder:
    instances: list["MockDecreaseOrder"] = []

    def __init__(self, writeConfig, market_key, collateral_address, index_token_address, is_long) -> None:
        self.writeConfig = writeConfig
        self.marketKey = market_key
        self.collateralAddress = collateral_address
        self.indexTokenAddress = index_token_address
        self.isLong = is_long
        self.createDecreaseOrderCalls: list[dict[str, Any]] = []
        MockDecreaseOrder.instances.append(self)

    def create_decrease_order(self, **kwargs: Any) -> MockOrderResult:
        self.createDecreaseOrderCalls.append(kwargs)
        return MockOrderResult(transaction={"kind": "decrease"})


class MockErc20Details:
    def __init__(self, balanceRaw: int) -> None:
        self.balanceRaw = balanceRaw
        self.balanceOfCalls: list[str] = []
        self.contract = SimpleNamespace(functions=SimpleNamespace(balanceOf=self._balance_of))

    def _balance_of(self, address: str) -> SimpleNamespace:
        self.balanceOfCalls.append(address)
        return SimpleNamespace(call=lambda: self.balanceRaw)


@pytest.fixture
def mock_order_classes(monkeypatch: pytest.MonkeyPatch) -> dict[str, type]:
    monkeypatch.setattr(MockSwapOrder, "instances", [])
    monkeypatch.setattr(MockIncreaseOrder, "instances", [])
    monkeypatch.setattr(MockDecreaseOrder, "instances", [])
    monkeypatch.setattr("basis_trade_agent.gmx_client.SwapOrder", MockSwapOrder)
    monkeypatch.setattr("basis_trade_agent.gmx_client.IncreaseOrder", MockIncreaseOrder)
    monkeypatch.setattr("basis_trade_agent.gmx_client.DecreaseOrder", MockDecreaseOrder)
    return {"swap": MockSwapOrder, "increase": MockIncreaseOrder, "decrease": MockDecreaseOrder}


@pytest.fixture
def patch_target_asset_balance(monkeypatch: pytest.MonkeyPatch):
    def _patch(balanceRaw: int) -> MockErc20Details:
        mockDetails = MockErc20Details(balanceRaw=balanceRaw)
        monkeypatch.setattr("basis_trade_agent.gmx_client.fetch_erc20_details", lambda web3, tokenAddress, chain_id: mockDetails)
        return mockDetails

    return _patch


@pytest.fixture
def mock_gmx_config() -> SimpleNamespace:
    return SimpleNamespace(web3=SimpleNamespace(eth=SimpleNamespace(chain_id=42161)), chain="arbitrum")


class MockGeminiLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def get_next_step(self, systemPrompt: str, prompt: str) -> dict[str, Any]:
        self.calls.append({"systemPrompt": systemPrompt, "prompt": prompt})
        if not self.responses:
            raise AssertionError("MockGeminiLLM ran out of scripted responses")
        return self.responses.pop(0)


@pytest.fixture
def mock_gemini_llm():
    def _make(responses: list[dict[str, Any]]) -> MockGeminiLLM:
        return MockGeminiLLM(responses)

    return _make


class MockEchoToolInput(ChatToolInput):
    text: str = ""


class MockEchoTool(ChatTool):
    resultText: str = "echoed"
    executeInnerCalls: list[dict[str, Any]] = Field(default_factory=list)

    def __init__(self, name: str = "mock_echo", resultText: str = "echoed") -> None:
        super().__init__(name=name, description="Mock tool for tests.", paramsSchema=MockEchoToolInput, resultText=resultText, executeInnerCalls=[])

    def execute_inner(self, runtimeState: AgentRuntimeState, params: MockEchoToolInput) -> str:
        self.executeInnerCalls.append(params.model_dump())
        return self.resultText


@pytest.fixture
def mock_echo_tool():
    def _make(name: str = "mock_echo", resultText: str = "echoed") -> MockEchoTool:
        return MockEchoTool(name=name, resultText=resultText)

    return _make
