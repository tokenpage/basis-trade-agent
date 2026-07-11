import logging
import os
from dataclasses import dataclass

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

DEFAULT_ARBITRUM_RPC_URL = "https://arb1.arbitrum.io/rpc"

log = logging.getLogger(__name__)


@dataclass
class WalletContext:
    web3: Web3
    account: LocalAccount


def load_wallet_context() -> WalletContext:
    privateKey = os.environ["BASIS_TRADE_WALLET_PRIVATE_KEY"]
    rpcUrl = os.environ.get("ARBITRUM_RPC_URL")
    if not rpcUrl:
        rpcUrl = DEFAULT_ARBITRUM_RPC_URL
        log.warning(f"ARBITRUM_RPC_URL not set, using default public RPC {rpcUrl} which rate-limits")
    web3 = Web3(Web3.HTTPProvider(rpcUrl))
    account = Account.from_key(privateKey)
    return WalletContext(web3=web3, account=account)
