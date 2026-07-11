from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from basis_trade_agent.gmx_client import GmxClient, MarketTokens
from basis_trade_agent.wallet import WalletContext


@dataclass
class AgentRuntimeState:
    walletContext: WalletContext
    gmxClient: GmxClient
    marketTokens: MarketTokens
    configPath: Path


class ChatToolInput(BaseModel):
    pass


class ChatTool(BaseModel):
    name: str
    description: str
    paramsSchema: type[ChatToolInput]

    def execute_inner(self, runtimeState: AgentRuntimeState, params: ChatToolInput) -> str:
        raise NotImplementedError("Subclasses must implement execute_inner")

    def execute(self, runtimeState: AgentRuntimeState, params: ChatToolInput) -> str:
        try:
            return self.execute_inner(runtimeState=runtimeState, params=params)
        except Exception as exception:
            return f"Error during {self.name}: {exception}"
