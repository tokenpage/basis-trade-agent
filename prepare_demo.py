import argparse
from pathlib import Path

from eth_defi.gmx.config import GMXConfig

from basis_trade_agent.config import load_config, update_config_file
from basis_trade_agent.gmx_client import GmxClient, get_wallet_holdings, resolve_market_and_tokens
from basis_trade_agent.wallet import load_wallet_context

DEMO_CONFIG_UPDATES = {
    "minNetYieldAprPercent": 0.01,
    "hysteresisBandAprPercent": 0.02,
    "netRateSmoothingWindowHours": 0.02,
    "minimumHoldHours": 0,
    "riskTolerance": "conservative",
    "pollIntervalSeconds": 15,
    "slippagePercent": 1.0,
    "minEthReserve": 0.005,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare config.yaml and wallet state for the live two-terminal demo runbook.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--starting-capital-usdc", type=float, default=5.0)
    args = parser.parse_args()

    walletContext = load_wallet_context()
    readConfig = GMXConfig(walletContext.web3)
    currentConfig = load_config(args.config)
    marketTokens = resolve_market_and_tokens(readConfig, currentConfig.targetAssetSymbol)
    gmxClient = GmxClient(readConfig=readConfig, writeConfig=readConfig)
    position = gmxClient.get_short_position(marketTokens, walletContext.account.address)
    if position is not None:
        raise RuntimeError(
            f"Wallet {walletContext.account.address} already has an open {marketTokens.marketSymbol} short (~${position.sizeUsd:.2f}). Close it before recording the demo."
        )

    updatedConfig = update_config_file(
        args.config,
        {**DEMO_CONFIG_UPDATES, "startingCapitalUsdc": args.starting_capital_usdc},
    )
    holdings = get_wallet_holdings(walletContext, marketTokens)
    print(f"Prepared {args.config} for the live demo.")
    print()
    print("Wallet state:")
    for key, value in holdings.items():
        print(f"  {key}: {value}")
    print()
    print("Updated config values:")
    print(f"  startingCapitalUsdc: {updatedConfig.startingCapitalUsdc}")
    print(f"  minNetYieldAprPercent: {updatedConfig.minNetYieldAprPercent}")
    print(f"  hysteresisBandAprPercent: {updatedConfig.hysteresisBandAprPercent}")
    print(f"  enterNetYieldAprPercent: {updatedConfig.enterNetYieldAprPercent}")
    print(f"  exitNetYieldAprPercent: {updatedConfig.exitNetYieldAprPercent}")
    print(f"  netRateSmoothingWindowHours: {updatedConfig.netRateSmoothingWindowHours}")
    print(f"  pollIntervalSeconds: {updatedConfig.pollIntervalSeconds}")
    print(f"  riskTolerance: {updatedConfig.riskTolerance}")
    print()
    print("Demo runbook:")
    print("  Terminal 1: py agent.py")
    print("    - Ask: what are my current holdings?")
    print(f"    - Ask: set starting capital to ${updatedConfig.startingCapitalUsdc}")
    print(f"    - Ask: set my minimum net yield to {updatedConfig.minNetYieldAprPercent}%")
    print(f"    - Ask: set my hysteresis band to {updatedConfig.hysteresisBandAprPercent}%")
    print(f"    - Ask: set my smoothing window to {updatedConfig.netRateSmoothingWindowHours} hours")
    print(f"    - Ask: set my poll interval to {updatedConfig.pollIntervalSeconds} seconds")
    print("  Terminal 2: py main.py --config config.yaml")
    print("    - Watch the loop log 'reloaded config from disk' after the agent changes config.yaml")
    print("    - Then watch it move from action=none to action=enter and submit real GMX txs")


if __name__ == "__main__":
    main()
