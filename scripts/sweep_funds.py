"""One-shot fund sweep for project retirement.

Closes any open GMX short position, then transfers every ERC20 balance
(target asset, USDC) and the remaining ETH (minus gas) from the agent
wallet to a destination address.

Usage:
    uv run python scripts/sweep_funds.py --config config.yaml [--dry-run]
"""

import argparse
import logging
from pathlib import Path

from eth_defi.gmx.config import GMXConfig
from eth_defi.token import fetch_erc20_details
from web3 import Web3

from basis_trade_agent.activity import append_activity_event, get_activity_path, get_tx_explorer_url
from basis_trade_agent.config import load_config
from basis_trade_agent.execution import execute_sequence, sign_and_send
from basis_trade_agent.gmx_client import GmxClient, resolve_market_and_tokens
from basis_trade_agent.wallet import WalletContext, load_wallet_context

log = logging.getLogger(__name__)

DESTINATION_ADDRESS = "0xcec34E6E3babc36Ef72e31bd5808B87214F4A3A8"
ERC20_TRANSFER_ABI = [
    {
        "constant": False,
        "inputs": [{"name": "to", "type": "address"}, {"name": "value", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    }
]


def close_open_position_if_any(
    walletContext: WalletContext, gmxClient: GmxClient, marketTokens, config, activityPath: Path
) -> None:
    position = gmxClient.get_short_position(marketTokens, walletContext.account.address)
    if position is None:
        log.info("no open short position")
        return
    log.info(f"closing open short position (size ${position.sizeUsd:,.2f})")
    orders = gmxClient.build_close_transactions(
        marketTokens, position, config.riskTolerance, config.slippagePercent, walletContext.account.address
    )
    closed = execute_sequence(walletContext, gmxClient, orders, marketTokens, config.orderFillTimeoutSeconds, activityPath)
    if not closed:
        raise RuntimeError("failed to close open position; aborting sweep before it can move borrowed collateral")


def sweep_erc20(walletContext: WalletContext, tokenAddress: str, destination: str, activityPath: Path, dryRun: bool) -> None:
    web3 = walletContext.web3
    details = fetch_erc20_details(web3, tokenAddress, chain_id=web3.eth.chain_id)
    balanceRaw = details.contract.functions.balanceOf(walletContext.account.address).call()
    if balanceRaw == 0:
        log.info(f"{details.symbol}: zero balance, nothing to sweep")
        return
    humanAmount = balanceRaw / 10**details.decimals
    log.info(f"sweeping {humanAmount} {details.symbol} to {destination}")
    if dryRun:
        return
    contract = web3.eth.contract(address=tokenAddress, abi=ERC20_TRANSFER_ABI)
    txParams = contract.functions.transfer(destination, balanceRaw).build_transaction({"from": walletContext.account.address})
    txHash = sign_and_send(walletContext, txParams)
    txUrl = get_tx_explorer_url(web3.eth.chain_id, txHash)
    append_activity_event(
        activityPath,
        {"kind": "sweep_erc20", "symbol": details.symbol, "amount": humanAmount, "to": destination, "txHash": txHash, "txUrl": txUrl},
    )
    web3.eth.wait_for_transaction_receipt(txHash)
    log.info(f"confirmed {details.symbol} sweep tx {txHash} ({txUrl})")


def sweep_eth(walletContext: WalletContext, destination: str, activityPath: Path, dryRun: bool) -> None:
    web3 = walletContext.web3
    balanceWei = web3.eth.get_balance(walletContext.account.address)
    gasPrice = web3.eth.gas_price
    gasLimit = int(web3.eth.estimate_gas({"from": walletContext.account.address, "to": destination, "value": 1}) * 1.1)
    gasCostWei = gasPrice * gasLimit
    sendableWei = balanceWei - gasCostWei
    if sendableWei <= 0:
        log.info(f"ETH balance {balanceWei / 10**18} too low to cover gas ({gasCostWei / 10**18}); skipping")
        return
    log.info(f"sweeping {sendableWei / 10**18} ETH to {destination} (reserving {gasCostWei / 10**18} for gas)")
    if dryRun:
        return
    txParams = {
        "from": walletContext.account.address,
        "to": destination,
        "value": sendableWei,
        "gas": gasLimit,
        "gasPrice": gasPrice,
        "chainId": web3.eth.chain_id,
    }
    txHash = sign_and_send(walletContext, txParams)
    txUrl = get_tx_explorer_url(web3.eth.chain_id, txHash)
    append_activity_event(
        activityPath,
        {"kind": "sweep_eth", "amount": sendableWei / 10**18, "to": destination, "txHash": txHash, "txUrl": txUrl},
    )
    web3.eth.wait_for_transaction_receipt(txHash)
    log.info(f"confirmed ETH sweep tx {txHash} ({txUrl})")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--destination", default=DESTINATION_ADDRESS)
    parser.add_argument("--dry-run", action="store_true", help="log intended transfers without sending transactions")
    args = parser.parse_args()

    destination = Web3.to_checksum_address(args.destination)
    config = load_config(args.config)
    walletContext = load_wallet_context()
    activityPath = get_activity_path(args.config)

    log.info(f"agent wallet: {walletContext.account.address}")
    log.info(f"destination:  {destination}")
    if args.dry_run:
        log.info("DRY RUN: no transactions will be sent")

    readConfig = GMXConfig(walletContext.web3)
    writeConfig = GMXConfig(walletContext.web3, user_wallet_address=walletContext.account.address)
    gmxClient = GmxClient(readConfig, writeConfig)
    marketTokens = resolve_market_and_tokens(readConfig, config.targetAssetSymbol)

    if not args.dry_run:
        close_open_position_if_any(walletContext, gmxClient, marketTokens, config, activityPath)
    else:
        position = gmxClient.get_short_position(marketTokens, walletContext.account.address)
        if position is not None:
            log.info(f"DRY RUN: would close open short position (size ${position.sizeUsd:,.2f}) before sweeping")

    sweep_erc20(walletContext, marketTokens.targetAssetAddress, destination, activityPath, args.dry_run)
    sweep_erc20(walletContext, marketTokens.usdcAddress, destination, activityPath, args.dry_run)
    sweep_eth(walletContext, destination, activityPath, args.dry_run)

    log.info("sweep complete")


if __name__ == "__main__":
    main()
