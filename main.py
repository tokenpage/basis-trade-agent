import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from eth_defi.gmx.config import GMXConfig
from eth_defi.token import fetch_erc20_details

from basis_trade_agent.config import AgentConfig, load_config
from basis_trade_agent.decision import Action, DecisionState, decide_action
from basis_trade_agent.execution import ensure_approvals, execute_sequence
from basis_trade_agent.gmx_client import MAX_UINT256, GmxClient, resolve_market_and_tokens
from basis_trade_agent.rates import RateHistory
from basis_trade_agent.wallet import load_wallet_context

log = logging.getLogger(__name__)
IMMUTABLE_RUNTIME_CONFIG_FIELDS = ("chain", "targetAssetSymbol")


def run_preflight_checks(walletContext, config: AgentConfig, usdcAddress: str, hasOpenPosition: bool) -> None:
    ethBalanceWei = walletContext.web3.eth.get_balance(walletContext.account.address)
    ethBalance = ethBalanceWei / 10**18
    if ethBalance < config.minEthReserve:
        raise RuntimeError(f"ETH balance {ethBalance:.6f} is below the configured minimum reserve {config.minEthReserve}")
    usdcDetails = fetch_erc20_details(walletContext.web3, usdcAddress, chain_id=walletContext.web3.eth.chain_id)
    usdcBalanceRaw = usdcDetails.contract.functions.balanceOf(walletContext.account.address).call()
    usdcBalance = usdcBalanceRaw / 10**usdcDetails.decimals
    if not hasOpenPosition and usdcBalance < config.startingCapitalUsdc:
        raise RuntimeError(f"USDC balance {usdcBalance:.2f} is below the configured starting capital {config.startingCapitalUsdc}")


def merge_runtime_config(startupConfig: AgentConfig, latestConfig: AgentConfig) -> AgentConfig:
    immutableChanges = {
        fieldName: getattr(latestConfig, fieldName)
        for fieldName in IMMUTABLE_RUNTIME_CONFIG_FIELDS
        if getattr(latestConfig, fieldName) != getattr(startupConfig, fieldName)
    }
    if immutableChanges:
        log.warning(
            f"ignoring runtime config changes to immutable fields {immutableChanges}; restart main.py to apply chain/target asset changes"
        )
    mutableUpdates = {
        fieldName: value
        for fieldName, value in latestConfig.model_dump().items()
        if fieldName not in IMMUTABLE_RUNTIME_CONFIG_FIELDS
    }
    return startupConfig.model_copy(update=mutableUpdates)


def run(configPath: Path) -> None:
    startupConfig = load_config(configPath)
    walletContext = load_wallet_context()
    readConfig = GMXConfig(walletContext.web3)
    writeConfig = GMXConfig(walletContext.web3, user_wallet_address=walletContext.account.address)
    gmxClient = GmxClient(readConfig=readConfig, writeConfig=writeConfig)
    marketTokens = resolve_market_and_tokens(readConfig, startupConfig.targetAssetSymbol)
    initialPosition = gmxClient.get_short_position(marketTokens, walletContext.account.address)
    run_preflight_checks(walletContext, startupConfig, marketTokens.usdcAddress, hasOpenPosition=initialPosition is not None)
    approvalCheckThreshold = MAX_UINT256 // 2
    ensure_approvals(
        walletContext,
        gmxClient,
        [
            (marketTokens.usdcAddress, approvalCheckThreshold),
            (marketTokens.targetAssetAddress, approvalCheckThreshold),
        ],
    )
    activeConfig = startupConfig
    state = DecisionState(positionOpenedAt=datetime.now(timezone.utc) if initialPosition is not None else None)
    rateHistory = RateHistory(windowHours=activeConfig.netRateSmoothingWindowHours)
    log.info(
        f"basis trade agent started: chain={activeConfig.chain} targetAsset={activeConfig.targetAssetSymbol} market={marketTokens.marketKey} riskTolerance={activeConfig.riskTolerance}"
    )
    while True:
        try:
            latestConfig = merge_runtime_config(startupConfig, load_config(configPath))
            if latestConfig.netRateSmoothingWindowHours != activeConfig.netRateSmoothingWindowHours:
                rateHistory = RateHistory(windowHours=latestConfig.netRateSmoothingWindowHours)
                log.info(f"reloaded config: reset rate history for new smoothing window {latestConfig.netRateSmoothingWindowHours}h")
            elif latestConfig != activeConfig:
                log.info("reloaded config from disk")
            activeConfig = latestConfig
            run_cycle(walletContext, activeConfig, gmxClient, marketTokens, state, rateHistory)
        except Exception:
            log.critical("unhandled exception during cycle", exc_info=True)
        time.sleep(activeConfig.pollIntervalSeconds)


def run_cycle(
    walletContext, config: AgentConfig, gmxClient: GmxClient, marketTokens, state: DecisionState, rateHistory: RateHistory
) -> None:
    now = datetime.now(timezone.utc)
    position = gmxClient.get_short_position(marketTokens, walletContext.account.address)
    if position is not None and state.positionOpenedAt is None:
        state.positionOpenedAt = now
    instantaneousNetRate = gmxClient.get_net_rate_apr_percent(marketTokens)
    rateHistory.append(now, instantaneousNetRate)
    smoothedNetRate = rateHistory.smoothed_rate()
    action = decide_action(state, config, position, smoothedNetRate, now)
    log.info(
        f"cycle: position={'open' if position else 'none'} instantaneousApr={instantaneousNetRate:.2f}% smoothedApr={smoothedNetRate:.2f}% action={action.value}"
    )
    if action == Action.ENTER:
        orders = gmxClient.build_open_transactions(marketTokens, config.riskTolerance, config.startingCapitalUsdc, config.slippagePercent)
        if execute_sequence(walletContext, gmxClient, orders, marketTokens, config.orderFillTimeoutSeconds):
            state.positionOpenedAt = now
            log.info("position opened successfully")
    elif action in (Action.CLOSE, Action.EMERGENCY_CLOSE):
        if position is None:
            log.warning(f"{action.value} triggered but no open position was found; skipping this cycle")
            return
        orders = gmxClient.build_close_transactions(
            marketTokens, position, config.riskTolerance, config.slippagePercent, walletContext.account.address
        )
        if execute_sequence(walletContext, gmxClient, orders, marketTokens, config.orderFillTimeoutSeconds):
            state.positionOpenedAt = None
            log.info(f"position closed successfully ({action.value})")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Basis Trade Agent: delta-neutral GMX V2 basis trade on Arbitrum")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
