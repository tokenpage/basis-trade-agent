import json
import os

from eth_defi.gmx.config import GMXConfig
from eth_defi.gmx.data import GMXMarketData
from web3 import Web3

from basis_trade_agent.gmx_client import GMX_MARKET_SYMBOL_OVERRIDES

PROBE_WALLET_ADDRESS = "0x0000000000000000000000000000000000000001"
PROBE_TARGET_ASSET_SYMBOL = "WBTC"


def main() -> None:
    rpcUrl = os.environ.get("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc")
    web3 = Web3(Web3.HTTPProvider(rpcUrl))
    config = GMXConfig(web3)
    marketData = GMXMarketData(config)
    marketSymbol = GMX_MARKET_SYMBOL_OVERRIDES.get(PROBE_TARGET_ASSET_SYMBOL, PROBE_TARGET_ASSET_SYMBOL)
    availableMarkets = marketData.get_available_markets()
    print(f"=== get_available_markets (market_symbol == {marketSymbol}) ===")
    for marketKey, marketInfo in availableMarkets.items():
        if marketInfo.get("market_symbol") == marketSymbol:
            print(marketKey, json.dumps(marketInfo, indent=2, default=str))
    fundingApr = marketData.get_funding_apr()
    print(f"=== get_funding_apr short/long for {marketSymbol} ===")
    print("long:", fundingApr.get("long", {}).get(marketSymbol))
    print("short:", fundingApr.get("short", {}).get(marketSymbol))
    borrowApr = marketData.get_borrow_apr()
    print(f"=== get_borrow_apr short/long for {marketSymbol} ===")
    print("long:", borrowApr.get("long", {}).get(marketSymbol))
    print("short:", borrowApr.get("short", {}).get(marketSymbol))
    positions = marketData.get_user_positions(PROBE_WALLET_ADDRESS)
    print("=== get_user_positions (probe address, expect empty) ===")
    print(json.dumps(positions, indent=2, default=str))


if __name__ == "__main__":
    main()
