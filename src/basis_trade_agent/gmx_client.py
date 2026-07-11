from dataclasses import dataclass
from typing import Literal

from eth_defi.gmx.config import GMXConfig
from eth_defi.gmx.contracts import NETWORK_TOKENS, get_contract_addresses
from eth_defi.gmx.data import GMXMarketData
from eth_defi.gmx.order.decrease_order import DecreaseOrder
from eth_defi.gmx.order.increase_order import IncreaseOrder
from eth_defi.gmx.order.swap_order import SwapOrder
from eth_defi.token import fetch_erc20_details
from web3.types import TxParams

GMX_SIZE_DELTA_PRECISION = 10**30
GMX_MARKET_SYMBOL_OVERRIDES = {"WBTC": "BTC"}
MAX_UINT256 = 2**256 - 1


@dataclass
class MarketTokens:
    marketKey: str
    marketSymbol: str
    indexTokenAddress: str
    usdcAddress: str
    targetAssetAddress: str
    targetAssetDecimals: int


@dataclass
class ShortPosition:
    sizeUsd: float
    sizeUsdRaw: int
    collateralAmountRaw: int
    markPrice: float
    liquidationPrice: float


@dataclass
class UnsignedOrder:
    label: str
    transaction: TxParams
    expectedEffect: Literal["position_opened", "position_closed", "spot_acquired", "spot_liquidated"]


def resolve_market_and_tokens(config: GMXConfig, targetAssetSymbol: str) -> MarketTokens:
    usdcAddress = NETWORK_TOKENS[config.chain]["USDC"]
    targetAssetAddress = NETWORK_TOKENS[config.chain][targetAssetSymbol]
    marketSymbol = GMX_MARKET_SYMBOL_OVERRIDES.get(targetAssetSymbol, targetAssetSymbol)
    availableMarkets = GMXMarketData(config).get_available_markets()
    matchingMarketKeys = [
        marketKey
        for marketKey, marketInfo in availableMarkets.items()
        if marketInfo.get("market_symbol") == marketSymbol and marketInfo.get("short_token_address") == usdcAddress
    ]
    if not matchingMarketKeys:
        raise ValueError(f"No GMX {config.chain} market found for symbol {marketSymbol} with a USDC short leg")
    marketKey = matchingMarketKeys[0]
    marketInfo = availableMarkets[marketKey]
    targetAssetDecimals = fetch_erc20_details(config.web3, targetAssetAddress, chain_id=config.web3.eth.chain_id).decimals
    return MarketTokens(
        marketKey=marketKey,
        marketSymbol=marketSymbol,
        indexTokenAddress=marketInfo["index_token_address"],
        usdcAddress=usdcAddress,
        targetAssetAddress=targetAssetAddress,
        targetAssetDecimals=targetAssetDecimals,
    )


class GmxClient:
    def __init__(self, readConfig: GMXConfig, writeConfig: GMXConfig) -> None:
        self.readConfig = readConfig
        self.writeConfig = writeConfig

    def get_net_rate_apr_percent(self, marketTokens: MarketTokens) -> float:
        marketData = GMXMarketData(self.readConfig)
        fundingApr = marketData.get_funding_apr()["short"][marketTokens.marketSymbol]
        borrowApr = marketData.get_borrow_apr()["short"][marketTokens.marketSymbol]
        return (fundingApr - borrowApr) * 100

    def get_short_position(self, marketTokens: MarketTokens, walletAddress: str) -> ShortPosition | None:
        marketData = GMXMarketData(self.readConfig)
        positions = marketData.get_user_positions(walletAddress)
        position = positions.get(f"{marketTokens.marketSymbol}_short")
        if position is None:
            return None
        if "liquidation_price" not in position:
            raise ValueError(
                f"GMX position data for {marketTokens.marketSymbol}_short is missing liquidation_price (REST API v2 tier unavailable)"
            )
        return ShortPosition(
            sizeUsd=position["position_size"],
            sizeUsdRaw=position["position_size_usd_raw"],
            collateralAmountRaw=position["initial_collateral_amount"],
            markPrice=position["mark_price"],
            liquidationPrice=position["liquidation_price"],
        )

    def build_approval_transaction_if_needed(self, tokenAddress: str, ownerAddress: str, requiredAmountRaw: int) -> TxParams | None:
        contractAddresses = get_contract_addresses(self.writeConfig.chain)
        tokenDetails = fetch_erc20_details(self.writeConfig.web3, tokenAddress, chain_id=self.writeConfig.web3.eth.chain_id)
        currentAllowance = tokenDetails.contract.functions.allowance(ownerAddress, contractAddresses.syntheticsrouter).call()
        if currentAllowance >= requiredAmountRaw:
            return None
        return tokenDetails.contract.functions.approve(contractAddresses.syntheticsrouter, MAX_UINT256).build_transaction(
            {"from": ownerAddress}
        )

    def build_open_transactions(
        self,
        marketTokens: MarketTokens,
        riskTolerance: Literal["conservative", "aggressive"],
        startingCapitalUsdc: float,
        slippagePercent: float,
    ) -> list[UnsignedOrder]:
        fullCapitalUsdcRaw = int(startingCapitalUsdc * 10**6)
        if riskTolerance == "conservative":
            halfCapitalUsdcRaw = fullCapitalUsdcRaw // 2
            halfCapitalUsd = startingCapitalUsdc / 2
            swapResult = SwapOrder(
                self.writeConfig, start_token=marketTokens.usdcAddress, out_token=marketTokens.targetAssetAddress
            ).create_swap_order(
                amount_in=halfCapitalUsdcRaw,
                slippage_percent=slippagePercent / 100,
            )
            increaseResult = IncreaseOrder(
                self.writeConfig,
                market_key=marketTokens.marketKey,
                collateral_address=marketTokens.usdcAddress,
                index_token_address=marketTokens.indexTokenAddress,
                is_long=False,
            ).create_increase_order(
                size_delta=int(halfCapitalUsd * GMX_SIZE_DELTA_PRECISION),
                initial_collateral_delta_amount=halfCapitalUsdcRaw,
                slippage_percent=slippagePercent / 100,
                swap_path=[],
            )
            return [
                UnsignedOrder(label="spot_buy_target_asset", transaction=swapResult.transaction, expectedEffect="spot_acquired"),
                UnsignedOrder(label="open_short", transaction=increaseResult.transaction, expectedEffect="position_opened"),
            ]
        increaseResult = IncreaseOrder(
            self.writeConfig,
            market_key=marketTokens.marketKey,
            collateral_address=marketTokens.usdcAddress,
            index_token_address=marketTokens.indexTokenAddress,
            is_long=False,
        ).create_increase_order(
            size_delta=int(startingCapitalUsdc * GMX_SIZE_DELTA_PRECISION),
            initial_collateral_delta_amount=fullCapitalUsdcRaw,
            slippage_percent=slippagePercent / 100,
            swap_path=[marketTokens.marketKey],
        )
        return [UnsignedOrder(label="open_short_atomic", transaction=increaseResult.transaction, expectedEffect="position_opened")]

    def build_close_transactions(
        self,
        marketTokens: MarketTokens,
        position: ShortPosition,
        riskTolerance: Literal["conservative", "aggressive"],
        slippagePercent: float,
        walletAddress: str,
    ) -> list[UnsignedOrder]:
        if riskTolerance == "conservative":
            decreaseResult = DecreaseOrder(
                self.writeConfig,
                market_key=marketTokens.marketKey,
                collateral_address=marketTokens.usdcAddress,
                index_token_address=marketTokens.indexTokenAddress,
                is_long=False,
            ).create_decrease_order(
                size_delta=position.sizeUsdRaw,
                initial_collateral_delta_amount=position.collateralAmountRaw,
                slippage_percent=slippagePercent / 100,
                swap_path=[],
            )
            targetAssetDetails = fetch_erc20_details(
                self.writeConfig.web3, marketTokens.targetAssetAddress, chain_id=self.writeConfig.web3.eth.chain_id
            )
            targetAssetBalanceRaw = targetAssetDetails.contract.functions.balanceOf(walletAddress).call()
            swapResult = SwapOrder(
                self.writeConfig, start_token=marketTokens.targetAssetAddress, out_token=marketTokens.usdcAddress
            ).create_swap_order(
                amount_in=targetAssetBalanceRaw,
                slippage_percent=slippagePercent / 100,
            )
            return [
                UnsignedOrder(label="close_short", transaction=decreaseResult.transaction, expectedEffect="position_closed"),
                UnsignedOrder(label="spot_sell_target_asset", transaction=swapResult.transaction, expectedEffect="spot_liquidated"),
            ]
        decreaseResult = DecreaseOrder(
            self.writeConfig,
            market_key=marketTokens.marketKey,
            collateral_address=marketTokens.targetAssetAddress,
            index_token_address=marketTokens.indexTokenAddress,
            is_long=False,
        ).create_decrease_order(
            size_delta=position.sizeUsdRaw,
            initial_collateral_delta_amount=position.collateralAmountRaw,
            slippage_percent=slippagePercent / 100,
            swap_path=[marketTokens.marketKey],
        )
        return [UnsignedOrder(label="close_short_atomic", transaction=decreaseResult.transaction, expectedEffect="position_closed")]
