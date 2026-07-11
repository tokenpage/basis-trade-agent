import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from basis_trade_agent.execution import ensure_approvals, execute_sequence
from basis_trade_agent.gmx_client import UnsignedOrder


class MockApprovalGmxClient:
    def __init__(self, approvalsByToken: dict[str, dict[str, Any] | None]) -> None:
        self.approvalsByToken = approvalsByToken
        self.approvalCalls: list[tuple[str, str, int]] = []

    def build_approval_transaction_if_needed(self, tokenAddress: str, ownerAddress: str, requiredAmountRaw: int) -> dict[str, Any] | None:
        self.approvalCalls.append((tokenAddress, ownerAddress, requiredAmountRaw))
        return self.approvalsByToken[tokenAddress]


@pytest.fixture
def wallet_context() -> SimpleNamespace:
    receiptCalls: list[str] = []

    def wait_for_transaction_receipt(txHash: str) -> None:
        receiptCalls.append(txHash)

    return SimpleNamespace(
        account=SimpleNamespace(address="0xWALLET"),
        web3=SimpleNamespace(eth=SimpleNamespace(chain_id=42161, wait_for_transaction_receipt=wait_for_transaction_receipt)),
        receiptCalls=receiptCalls,
    )


def test_ensure_approvals_records_submitted_and_confirmed_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wallet_context: SimpleNamespace
) -> None:
    activityPath = tmp_path / ".agent_activity.json"
    gmxClient = MockApprovalGmxClient({"0xTOKEN": {"to": "0xROUTER"}})
    sentTransactions: list[dict[str, Any]] = []

    def mock_sign_and_send(walletContextArg, txParams: dict[str, Any]) -> str:
        assert walletContextArg is wallet_context
        sentTransactions.append(txParams)
        return "0xapproval"

    monkeypatch.setattr("basis_trade_agent.execution.sign_and_send", mock_sign_and_send)
    ensure_approvals(wallet_context, gmxClient, [("0xTOKEN", 123)], activityPath)
    assert gmxClient.approvalCalls == [("0xTOKEN", "0xWALLET", 123)]
    assert sentTransactions == [{"to": "0xROUTER"}]
    assert wallet_context.receiptCalls == ["0xapproval"]
    events = json.loads(activityPath.read_text())["events"]
    assert [event["kind"] for event in events] == ["approval_submitted", "approval_confirmed"]
    assert [event["txHash"] for event in events] == ["0xapproval", "0xapproval"]
    assert [event["txUrl"] for event in events] == ["https://arbiscan.io/tx/0xapproval", "https://arbiscan.io/tx/0xapproval"]
    assert [event["tokenAddress"] for event in events] == ["0xTOKEN", "0xTOKEN"]


def test_execute_sequence_records_submitted_and_confirmed_events_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wallet_context: SimpleNamespace
) -> None:
    activityPath = tmp_path / ".agent_activity.json"
    sentTransactions: list[dict[str, Any]] = []
    waitCalls: list[tuple[str, str, int]] = []
    order = UnsignedOrder(label="open_spot", transaction={"to": "0xROUTER"}, expectedEffect="spot_acquired")

    def mock_sign_and_send(walletContextArg, txParams: dict[str, Any]) -> str:
        assert walletContextArg is wallet_context
        sentTransactions.append(txParams)
        return "0xsubmitted"

    def mock_wait_for_fill(walletContextArg, gmxClientArg, txHash: str, expectedEffect: str, marketTokensArg, timeoutSeconds: int) -> bool:
        assert walletContextArg is wallet_context
        waitCalls.append((txHash, expectedEffect, timeoutSeconds))
        return True

    monkeypatch.setattr("basis_trade_agent.execution.sign_and_send", mock_sign_and_send)
    monkeypatch.setattr("basis_trade_agent.execution.wait_for_fill", mock_wait_for_fill)
    result = execute_sequence(
        wallet_context,
        SimpleNamespace(),
        [order],
        SimpleNamespace(targetAssetAddress="0xWBTC"),
        timeoutSeconds=45,
        activityPath=activityPath,
    )
    assert result is True
    assert sentTransactions == [{"to": "0xROUTER"}]
    assert waitCalls == [("0xsubmitted", "spot_acquired", 45)]
    events = json.loads(activityPath.read_text())["events"]
    assert [event["kind"] for event in events] == ["order_submitted", "order_confirmed"]
    assert [event["label"] for event in events] == ["open_spot", "open_spot"]
    assert [event["expectedEffect"] for event in events] == ["spot_acquired", "spot_acquired"]
    assert [event["txUrl"] for event in events] == ["https://arbiscan.io/tx/0xsubmitted", "https://arbiscan.io/tx/0xsubmitted"]


def test_execute_sequence_records_timeout_and_stops_before_later_legs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wallet_context: SimpleNamespace
) -> None:
    activityPath = tmp_path / ".agent_activity.json"
    sentTransactions: list[dict[str, Any]] = []
    waitCalls: list[tuple[str, str, int]] = []
    orders = [
        UnsignedOrder(label="first_leg", transaction={"to": "0xFIRST"}, expectedEffect="spot_acquired"),
        UnsignedOrder(label="second_leg", transaction={"to": "0xSECOND"}, expectedEffect="position_opened"),
    ]

    def mock_sign_and_send(walletContextArg, txParams: dict[str, Any]) -> str:
        assert walletContextArg is wallet_context
        sentTransactions.append(txParams)
        return "0xtimeout"

    def mock_wait_for_fill(walletContextArg, gmxClientArg, txHash: str, expectedEffect: str, marketTokensArg, timeoutSeconds: int) -> bool:
        assert walletContextArg is wallet_context
        waitCalls.append((txHash, expectedEffect, timeoutSeconds))
        return False

    monkeypatch.setattr("basis_trade_agent.execution.sign_and_send", mock_sign_and_send)
    monkeypatch.setattr("basis_trade_agent.execution.wait_for_fill", mock_wait_for_fill)
    result = execute_sequence(
        wallet_context,
        SimpleNamespace(),
        orders,
        SimpleNamespace(targetAssetAddress="0xWBTC"),
        timeoutSeconds=45,
        activityPath=activityPath,
    )
    assert result is False
    assert sentTransactions == [{"to": "0xFIRST"}]
    assert waitCalls == [("0xtimeout", "spot_acquired", 45)]
    events = json.loads(activityPath.read_text())["events"]
    assert [event["kind"] for event in events] == ["order_submitted", "order_timeout"]
    assert [event["label"] for event in events] == ["first_leg", "first_leg"]
    assert [event["expectedEffect"] for event in events] == ["spot_acquired", "spot_acquired"]
    assert [event["txUrl"] for event in events] == ["https://arbiscan.io/tx/0xtimeout", "https://arbiscan.io/tx/0xtimeout"]
