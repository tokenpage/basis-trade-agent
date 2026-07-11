from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, computed_field


class AgentConfig(BaseModel):
    chain: Literal["arbitrum", "arbitrum_sepolia"]
    targetAssetSymbol: str
    startingCapitalUsdc: float
    minNetYieldAprPercent: float
    hysteresisBandAprPercent: float
    netRateSmoothingWindowHours: float
    minimumHoldHours: float
    riskTolerance: Literal["conservative", "aggressive"]
    pollIntervalSeconds: int
    slippagePercent: float
    liquidationBufferPercent: float
    orderFillTimeoutSeconds: int
    minEthReserve: float

    @computed_field
    @property
    def enterNetYieldAprPercent(self) -> float:
        return self.minNetYieldAprPercent + self.hysteresisBandAprPercent / 2

    @computed_field
    @property
    def exitNetYieldAprPercent(self) -> float:
        return self.minNetYieldAprPercent - self.hysteresisBandAprPercent / 2


def load_config(configPath: Path) -> AgentConfig:
    rawConfig = yaml.safe_load(configPath.read_text())
    return AgentConfig.model_validate(rawConfig)
