import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from eth_defi.gmx.config import GMXConfig

from basis_trade_agent.config import load_config
from basis_trade_agent.decision import Action, DecisionState, decide_action
from basis_trade_agent.execution import ensure_approvals, sign_and_send, wait_for_fill
from basis_trade_agent.gmx_client import MAX_UINT256, GmxClient, resolve_market_and_tokens
from basis_trade_agent.rates import RateHistory
from basis_trade_agent.wallet import load_wallet_context
from main import run_preflight_checks

ARBISCAN_TX_URL_TEMPLATE = "https://arbiscan.io/tx/{txHash}"
ARBISCAN_ADDRESS_URL_TEMPLATE = "https://arbiscan.io/address/{address}"


def print_banner(text: str) -> None:
    print()
    print("=" * 78)
    print(text)
    print("=" * 78)


def wait_for_entry_signal(gmxClient: GmxClient, marketTokens, config, state: DecisionState, rateHistory: RateHistory) -> None:
    while True:
        now = datetime.now(timezone.utc)
        instantaneousNetRate = gmxClient.get_net_rate_apr_percent(marketTokens)
        rateHistory.append(now, instantaneousNetRate)
        smoothedNetRate = rateHistory.smoothed_rate()
        action = decide_action(state, config, None, smoothedNetRate, now)
        print(
            f"[{now:%H:%M:%S}] instantaneous net rate={instantaneousNetRate:.4f}%  smoothed={smoothedNetRate:.4f}%  "
            f"enter threshold={config.enterNetYieldAprPercent:.4f}%  action={action.value}"
        )
        if action == Action.ENTER:
            return
        time.sleep(config.pollIntervalSeconds)


def open_position(walletContext, gmxClient: GmxClient, marketTokens, config) -> list[tuple[str, str]]:
    orders = gmxClient.build_open_transactions(marketTokens, config.riskTolerance, config.startingCapitalUsdc, config.slippagePercent)
    txHashes = []
    for order in orders:
        txHash = sign_and_send(walletContext, order.transaction)
        txHashes.append((order.label, txHash))
        print(f"submitted '{order.label}': {ARBISCAN_TX_URL_TEMPLATE.format(txHash=txHash)}")
        filled = wait_for_fill(walletContext, gmxClient, txHash, order.expectedEffect, marketTokens, config.orderFillTimeoutSeconds)
        if not filled:
            print(f"'{order.label}' did not confirm within {config.orderFillTimeoutSeconds}s — check the tx above manually.")
            sys.exit(1)
        print(f"confirmed '{order.label}'")
    return txHashes


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo runner: waits for a real entry signal and opens one real GMX basis trade position, then exits.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()

    config = load_config(args.config)
    walletContext = load_wallet_context()
    readConfig = GMXConfig(walletContext.web3)
    writeConfig = GMXConfig(walletContext.web3, user_wallet_address=walletContext.account.address)
    gmxClient = GmxClient(readConfig=readConfig, writeConfig=writeConfig)
    marketTokens = resolve_market_and_tokens(readConfig, config.targetAssetSymbol)
    walletAddress = walletContext.account.address

    print_banner(f"Basis Trade Agent Demo — wallet {walletAddress}")
    print(f"Chain: {config.chain}  Market: {marketTokens.marketSymbol}  Risk mode: {config.riskTolerance}")
    print(f"Starting capital: ${config.startingCapitalUsdc}  Enter threshold: {config.enterNetYieldAprPercent:.4f}%  Poll interval: {config.pollIntervalSeconds}s")
    print(f"View wallet: {ARBISCAN_ADDRESS_URL_TEMPLATE.format(address=walletAddress)}")

    initialPosition = gmxClient.get_short_position(marketTokens, walletAddress)
    if initialPosition is not None:
        print("A position is already open on this wallet — nothing to demo. Close it first (make main) or use a fresh wallet.")
        sys.exit(1)

    run_preflight_checks(walletContext, config, marketTokens.usdcAddress, hasOpenPosition=False)
    print("Preflight checks passed (ETH reserve + USDC capital confirmed).")

    approvalCheckThreshold = MAX_UINT256 // 2
    ensure_approvals(walletContext, gmxClient, [(marketTokens.usdcAddress, approvalCheckThreshold), (marketTokens.targetAssetAddress, approvalCheckThreshold)])
    print("Token approvals confirmed.")

    state = DecisionState(positionOpenedAt=None)
    rateHistory = RateHistory(windowHours=config.netRateSmoothingWindowHours)

    print_banner("Watching live GMX funding/borrow rates for an entry signal...")
    wait_for_entry_signal(gmxClient, marketTokens, config, state, rateHistory)

    print_banner("ENTRY SIGNAL — opening a real GMX position now")
    txHashes = open_position(walletContext, gmxClient, marketTokens, config)

    position = gmxClient.get_short_position(marketTokens, walletAddress)
    print_banner("POSITION OPENED")
    for label, txHash in txHashes:
        print(f"  {label}: {ARBISCAN_TX_URL_TEMPLATE.format(txHash=txHash)}")
    if position is not None:
        print(f"  Short size: ${position.sizeUsd:.2f}")
        print(f"  Mark price: ${position.markPrice:.2f}")
        print(f"  Liquidation price: ${position.liquidationPrice:.2f}")
    print("Ask agent.py \"what's my current position?\" to see the agent confirm this conversationally.")


if __name__ == "__main__":
    main()
