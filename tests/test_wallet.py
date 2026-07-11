import base64
import hashlib

import pytest
from cryptography.fernet import Fernet, InvalidToken

from basis_trade_agent.wallet import PRIVATE_KEY_ENCRYPTION_PASSWORD, decrypt_private_key


def encrypt_with_password(password: str, plaintext: str) -> str:
    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
    return Fernet(key).encrypt(plaintext.encode()).decode()


def test_decrypt_private_key_recovers_original_value() -> None:
    privateKey = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
    encryptedPrivateKey = encrypt_with_password(PRIVATE_KEY_ENCRYPTION_PASSWORD, privateKey)
    assert decrypt_private_key(encryptedPrivateKey) == privateKey


def test_decrypt_private_key_raises_when_encrypted_with_different_password() -> None:
    privateKey = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
    encryptedPrivateKey = encrypt_with_password("some-other-password", privateKey)
    with pytest.raises(InvalidToken):
        decrypt_private_key(encryptedPrivateKey)


def test_decrypt_private_key_raises_on_malformed_token() -> None:
    with pytest.raises(InvalidToken):
        decrypt_private_key("not-a-valid-fernet-token")
