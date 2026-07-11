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


def update_config_file(configPath: Path, updates: dict[str, float | int | str]) -> AgentConfig:
    unknownKeys = set(updates) - set(AgentConfig.model_fields)
    if unknownKeys:
        raise ValueError(f"Unknown config field(s): {sorted(unknownKeys)}")
    updatedLines = []
    remainingKeys = set(updates)
    for line in configPath.read_text().splitlines():
        stripped = line.lstrip()
        key = stripped.split(":", 1)[0].strip() if (not stripped.startswith("#") and ":" in stripped) else None
        if key in updates:
            commentIndex = line.find("#")
            comment = line[commentIndex:] if commentIndex != -1 else ""
            newLine = f"{key}: {updates[key]}"
            updatedLines.append(f"{newLine.ljust(commentIndex)}{comment}" if comment and len(newLine) < commentIndex else (f"{newLine}  {comment}" if comment else newLine))
            remainingKeys.discard(key)
        else:
            updatedLines.append(line)
    if remainingKeys:
        raise ValueError(f"Config field(s) not found in {configPath}: {sorted(remainingKeys)}")
    newText = "\n".join(updatedLines) + "\n"
    newConfig = AgentConfig.model_validate(yaml.safe_load(newText))
    configPath.write_text(newText)
    return newConfig
