from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from basis_trade_agent.config import AgentConfig
from basis_trade_agent.gmx_client import ShortPosition


class Action(str, Enum):
    NONE = "none"
    ENTER = "enter"
    CLOSE = "close"
    EMERGENCY_CLOSE = "emergency_close"


@dataclass
class DecisionState:
    positionOpenedAt: datetime | None = None


def decide_action(
    state: DecisionState,
    config: AgentConfig,
    position: ShortPosition | None,
    smoothedNetRateAprPercent: float,
    now: datetime,
) -> Action:
    if position is not None:
        liquidationBufferPercent = abs(position.liquidationPrice - position.markPrice) / position.markPrice * 100
        if liquidationBufferPercent < config.liquidationBufferPercent:
            return Action.EMERGENCY_CLOSE
        heldHours = (now - state.positionOpenedAt).total_seconds() / 3600
        if heldHours >= config.minimumHoldHours and smoothedNetRateAprPercent <= config.exitNetYieldAprPercent:
            return Action.CLOSE
        return Action.NONE
    if smoothedNetRateAprPercent >= config.enterNetYieldAprPercent:
        return Action.ENTER
    return Action.NONE
