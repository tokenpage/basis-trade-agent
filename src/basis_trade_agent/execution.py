import logging
import time

from web3.types import TxParams

from basis_trade_agent.gmx_client import GmxClient, MarketTokens, UnsignedOrder
from basis_trade_agent.wallet import WalletContext

log = logging.getLogger(__name__)


def sign_and_send(walletContext: WalletContext, txParams: TxParams) -> str:
    txToSend = dict(txParams)
    txToSend["nonce"] = walletContext.web3.eth.get_transaction_count(walletContext.account.address, "pending")
    signedTransaction = walletContext.web3.eth.account.sign_transaction(transaction_dict=txToSend, private_key=walletContext.account.key)
    txHash = walletContext.web3.eth.send_raw_transaction(signedTransaction.raw_transaction)
    return txHash.hex()


def ensure_approvals(walletContext: WalletContext, gmxClient: GmxClient, tokenAmountsRaw: list[tuple[str, int]]) -> None:
    for tokenAddress, requiredAmountRaw in tokenAmountsRaw:
        approvalTx = gmxClient.build_approval_transaction_if_needed(tokenAddress, walletContext.account.address, requiredAmountRaw)
        if approvalTx is None:
            continue
        txHash = sign_and_send(walletContext, approvalTx)
        log.info(f"submitted approval tx {txHash} for token {tokenAddress}")
        walletContext.web3.eth.wait_for_transaction_receipt(txHash)


def wait_for_fill(
    walletContext: WalletContext,
    gmxClient: GmxClient,
    txHash: str,
    expectedEffect: str,
    marketTokens: MarketTokens,
    timeoutSeconds: int,
) -> bool:
    walletContext.web3.eth.wait_for_transaction_receipt(txHash)
    walletAddress = walletContext.account.address
    if expectedEffect in ("spot_acquired", "spot_liquidated"):
        targetAssetContract = walletContext.web3.eth.contract(
            address=marketTokens.targetAssetAddress,
            abi=[
                {
                    "constant": True,
                    "inputs": [{"name": "owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function",
                }
            ],
        )
        startingBalance = targetAssetContract.functions.balanceOf(walletAddress).call()
        deadline = time.monotonic() + timeoutSeconds
        while time.monotonic() < deadline:
            currentBalance = targetAssetContract.functions.balanceOf(walletAddress).call()
            if currentBalance != startingBalance:
                return True
            time.sleep(5)
        return False
    deadline = time.monotonic() + timeoutSeconds
    while time.monotonic() < deadline:
        position = gmxClient.get_short_position(marketTokens, walletAddress)
        if expectedEffect == "position_opened" and position is not None:
            return True
        if expectedEffect == "position_closed" and position is None:
            return True
        time.sleep(5)
    return False


def execute_sequence(
    walletContext: WalletContext,
    gmxClient: GmxClient,
    orders: list[UnsignedOrder],
    marketTokens: MarketTokens,
    timeoutSeconds: int,
) -> bool:
    for index, order in enumerate(orders):
        txHash = sign_and_send(walletContext, order.transaction)
        log.info(f"submitted order '{order.label}' tx {txHash}")
        filled = wait_for_fill(walletContext, gmxClient, txHash, order.expectedEffect, marketTokens, timeoutSeconds)
        if not filled:
            remainingLabels = [remainingOrder.label for remainingOrder in orders[index + 1 :]]
            log.critical(
                f"order '{order.label}' tx {txHash} did not confirm expected effect '{order.expectedEffect}' within {timeoutSeconds}s; remaining unexecuted legs: {remainingLabels}"
            )
            return False
        log.info(f"confirmed order '{order.label}' tx {txHash}")
    return True
