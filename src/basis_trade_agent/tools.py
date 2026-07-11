from typing import Literal

import yaml

from basis_trade_agent.activity import get_activity_path, read_activity
from basis_trade_agent.chat_tool import AgentRuntimeState, ChatTool, ChatToolInput
from basis_trade_agent.config import load_config, update_config_file
from basis_trade_agent.gmx_client import get_wallet_holdings


class GetConfigInput(ChatToolInput):
    pass


class GetConfigTool(ChatTool):
    def __init__(self) -> None:
        super().__init__(name="get_config", description="Returns the current agent trading configuration as YAML.", paramsSchema=GetConfigInput)

    def execute_inner(self, runtimeState: AgentRuntimeState, params: GetConfigInput) -> str:  # noqa: ARG002
        config = load_config(runtimeState.configPath)
        return yaml.dump(config.model_dump(), default_flow_style=False, sort_keys=False)


class UpdateConfigInput(ChatToolInput):
    startingCapitalUsdc: float | None = None
    minNetYieldAprPercent: float | None = None
    hysteresisBandAprPercent: float | None = None
    netRateSmoothingWindowHours: float | None = None
    minimumHoldHours: float | None = None
    riskTolerance: Literal["conservative", "aggressive"] | None = None
    pollIntervalSeconds: int | None = None
    slippagePercent: float | None = None
    liquidationBufferPercent: float | None = None
    orderFillTimeoutSeconds: int | None = None
    minEthReserve: float | None = None


class UpdateConfigTool(ChatTool):
    def __init__(self) -> None:
        super().__init__(
            name="update_config",
            description="Updates one or more trading parameters in the config file. Only pass the fields the user wants changed; leave the rest null. Cannot change chain or targetAssetSymbol.",
            paramsSchema=UpdateConfigInput,
        )

    def execute_inner(self, runtimeState: AgentRuntimeState, params: UpdateConfigInput) -> str:
        updates = {key: value for key, value in params.model_dump().items() if value is not None}
        if not updates:
            return "No fields were provided to update."
        newConfig = update_config_file(runtimeState.configPath, updates)
        return f"Updated config: {updates}. New enterNetYieldAprPercent={newConfig.enterNetYieldAprPercent:.2f}%, exitNetYieldAprPercent={newConfig.exitNetYieldAprPercent:.2f}%"


class GetWalletHoldingsInput(ChatToolInput):
    pass


class GetWalletHoldingsTool(ChatTool):
    def __init__(self) -> None:
        super().__init__(name="get_wallet_holdings", description="Returns the agent wallet's current ETH, USDC, and target-asset balances.", paramsSchema=GetWalletHoldingsInput)

    def execute_inner(self, runtimeState: AgentRuntimeState, params: GetWalletHoldingsInput) -> str:  # noqa: ARG002
        holdings = get_wallet_holdings(runtimeState.walletContext, runtimeState.marketTokens)
        return yaml.dump(holdings, default_flow_style=False, sort_keys=False)


class GetCurrentPositionInput(ChatToolInput):
    pass


class GetCurrentPositionTool(ChatTool):
    def __init__(self) -> None:
        super().__init__(name="get_current_position", description="Returns details of the agent's currently open GMX short position, or reports that no position is open.", paramsSchema=GetCurrentPositionInput)

    def execute_inner(self, runtimeState: AgentRuntimeState, params: GetCurrentPositionInput) -> str:  # noqa: ARG002
        position = runtimeState.gmxClient.get_short_position(runtimeState.marketTokens, runtimeState.walletContext.account.address)
        if position is None:
            return "No position is currently open."
        liquidationBufferPercent = abs(position.liquidationPrice - position.markPrice) / position.markPrice * 100
        positionData = {
            "sizeUsd": position.sizeUsd,
            "markPrice": position.markPrice,
            "liquidationPrice": position.liquidationPrice,
            "liquidationBufferPercent": liquidationBufferPercent,
        }
        return yaml.dump(positionData, default_flow_style=False, sort_keys=False)


class GetRecentActivityInput(ChatToolInput):
    pass


class GetRecentActivityTool(ChatTool):
    def __init__(self) -> None:
        super().__init__(
            name="get_recent_activity",
            description="Returns the last few approval/order events the live main.py loop recorded, including explorer links for submitted and confirmed transactions.",
            paramsSchema=GetRecentActivityInput,
        )

    def execute_inner(self, runtimeState: AgentRuntimeState, params: GetRecentActivityInput) -> str:  # noqa: ARG002
        activity = read_activity(get_activity_path(runtimeState.configPath))
        events = activity.get("events", [])
        if not events:
            return "No recorded activity yet."
        return yaml.dump(events[-8:], default_flow_style=False, sort_keys=False)
