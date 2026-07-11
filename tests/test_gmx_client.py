from basis_trade_agent.gmx_client import GmxClient, MarketTokens, ShortPosition

MARKET_TOKENS = MarketTokens(
    marketKey="0xMARKET",
    marketSymbol="BTC",
    indexTokenAddress="0xINDEX",
    usdcAddress="0xUSDC",
    targetAssetAddress="0xWBTC",
    targetAssetDecimals=8,
)


def make_position() -> ShortPosition:
    return ShortPosition(sizeUsd=1000.0, sizeUsdRaw=123456789, collateralAmountRaw=987654, markPrice=60000.0, liquidationPrice=50000.0)


def test_conservative_open_splits_capital_fifty_fifty_with_no_swap_path(mock_order_classes, mock_gmx_config) -> None:
    client = GmxClient(readConfig=mock_gmx_config, writeConfig=mock_gmx_config)
    orders = client.build_open_transactions(MARKET_TOKENS, "conservative", 1000.0, 0.5)
    increaseInstances = mock_order_classes["increase"].instances
    swapInstances = mock_order_classes["swap"].instances
    assert len(orders) == 2
    assert len(increaseInstances) == 1
    assert len(swapInstances) == 1
    increaseCall = increaseInstances[0].createIncreaseOrderCalls[0]
    swapCall = swapInstances[0].createSwapOrderCalls[0]
    assert increaseCall["swap_path"] == []
    assert increaseCall["initial_collateral_delta_amount"] == 500_000_000
    assert increaseCall["size_delta"] == int(500.0 * 10**30)
    assert swapCall["amount_in"] == 500_000_000


def test_aggressive_open_uses_full_capital_with_atomic_swap_path(mock_order_classes, mock_gmx_config) -> None:
    client = GmxClient(readConfig=mock_gmx_config, writeConfig=mock_gmx_config)
    orders = client.build_open_transactions(MARKET_TOKENS, "aggressive", 1000.0, 0.5)
    increaseInstances = mock_order_classes["increase"].instances
    swapInstances = mock_order_classes["swap"].instances
    assert len(orders) == 1
    assert len(increaseInstances) == 1
    assert len(swapInstances) == 0
    increaseCall = increaseInstances[0].createIncreaseOrderCalls[0]
    assert increaseCall["swap_path"] == [MARKET_TOKENS.marketKey]
    assert increaseCall["initial_collateral_delta_amount"] == 1_000_000_000
    assert increaseCall["size_delta"] == int(1000.0 * 10**30)


def test_conservative_close_uses_position_raw_amounts_and_sells_wallet_balance(
    mock_order_classes, mock_gmx_config, patch_target_asset_balance
) -> None:
    client = GmxClient(readConfig=mock_gmx_config, writeConfig=mock_gmx_config)
    position = make_position()
    mockDetails = patch_target_asset_balance(42)
    orders = client.build_close_transactions(MARKET_TOKENS, position, "conservative", 0.5, "0xWALLET")
    decreaseInstances = mock_order_classes["decrease"].instances
    swapInstances = mock_order_classes["swap"].instances
    assert len(orders) == 2
    assert len(decreaseInstances) == 1
    assert len(swapInstances) == 1
    decreaseCall = decreaseInstances[0].createDecreaseOrderCalls[0]
    assert decreaseCall["swap_path"] == []
    assert decreaseCall["size_delta"] == position.sizeUsdRaw
    assert decreaseCall["initial_collateral_delta_amount"] == position.collateralAmountRaw
    assert swapInstances[0].createSwapOrderCalls[0]["amount_in"] == 42
    assert mockDetails.balanceOfCalls == ["0xWALLET"]


def test_aggressive_close_releases_target_asset_collateral_atomically(mock_order_classes, mock_gmx_config) -> None:
    client = GmxClient(readConfig=mock_gmx_config, writeConfig=mock_gmx_config)
    position = make_position()
    orders = client.build_close_transactions(MARKET_TOKENS, position, "aggressive", 0.5, "0xWALLET")
    decreaseInstances = mock_order_classes["decrease"].instances
    assert len(orders) == 1
    assert len(decreaseInstances) == 1
    assert decreaseInstances[0].collateralAddress == MARKET_TOKENS.targetAssetAddress
    decreaseCall = decreaseInstances[0].createDecreaseOrderCalls[0]
    assert decreaseCall["swap_path"] == [MARKET_TOKENS.marketKey]
    assert decreaseCall["size_delta"] == position.sizeUsdRaw
    assert decreaseCall["initial_collateral_delta_amount"] == position.collateralAmountRaw
