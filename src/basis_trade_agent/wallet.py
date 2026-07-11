import base64
import hashlib
import logging
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

DEFAULT_ARBITRUM_RPC_URL = "https://arb1.arbitrum.io/rpc"
PRIVATE_KEY_ENCRYPTION_PASSWORD = "ushf89h28fh8032hf0j230idj2039dj23kdf2030f23j"

log = logging.getLogger(__name__)


@dataclass
class WalletContext:
    web3: Web3
    account: LocalAccount


def decrypt_private_key(encryptedPrivateKey: str) -> str:
    key = base64.urlsafe_b64encode(hashlib.sha256(PRIVATE_KEY_ENCRYPTION_PASSWORD.encode()).digest())
    fernet = Fernet(key)
    return fernet.decrypt(encryptedPrivateKey.encode()).decode()


def load_wallet_context() -> WalletContext:
    encryptedPrivateKey = os.environ["BASIS_TRADE_WALLET_PRIVATE_KEY"]
    privateKey = decrypt_private_key(encryptedPrivateKey)
    rpcUrl = os.environ.get("ARBITRUM_RPC_URL")
    if not rpcUrl:
        rpcUrl = DEFAULT_ARBITRUM_RPC_URL
        log.warning(f"ARBITRUM_RPC_URL not set, using default public RPC {rpcUrl} which rate-limits")
    web3 = Web3(Web3.HTTPProvider(rpcUrl))
    account = Account.from_key(privateKey)
    return WalletContext(web3=web3, account=account)
