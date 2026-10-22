"""AES-256-GCM vault for Liara/GitHub tokens (DATA-MODEL.md → Secrets handling).

Blob layout is nonce(12) ‖ ciphertext ‖ tag(16). The AAD binds a ciphertext to its row, so a blob
copied to another row fails to decrypt. Keys are versioned for rotation.
"""

import base64
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from deployar.core.errors import DeployarError
from deployar.core.redact import register_secret

_NONCE = 12


def aad_for(table: str, row_id: object, user_id: object) -> str:
    return f"{table}:{row_id}:{user_id}"


class TokenVault:
    def __init__(self, keys: dict[str, str], current_version: int) -> None:
        self._keys: dict[int, AESGCM] = {}
        for version, b64 in keys.items():
            raw = base64.b64decode(b64)
            if len(raw) != 32:
                raise ValueError(f"token key {version} must be 32 bytes, got {len(raw)}")
            self._keys[int(version)] = AESGCM(raw)
        if current_version not in self._keys:
            raise ValueError(f"current token key version {current_version} is not in the key set")
        self.current_version = current_version

    def encrypt(self, plaintext: str, aad: str) -> tuple[bytes, int]:
        nonce = os.urandom(_NONCE)
        ct = self._keys[self.current_version].encrypt(nonce, plaintext.encode(), aad.encode())
        return nonce + ct, self.current_version

    def decrypt(self, blob: bytes, key_version: int, aad: str) -> str:
        key = self._keys.get(key_version)
        if key is None:
            raise DeployarError("token_key_missing", "کلید رمزگشایی توکن پیدا نشد.", f"version {key_version}")
        try:
            plaintext = key.decrypt(blob[:_NONCE], blob[_NONCE:], aad.encode()).decode()
        except (InvalidTag, ValueError) as e:  # ValueError: blob too short to hold a nonce
            raise DeployarError("token_decrypt_failed", "توکن ذخیره‌شده قابل خواندن نیست.", aad) from e
        register_secret(plaintext)
        return plaintext

    def rotate(self, blob: bytes, key_version: int, aad: str) -> tuple[bytes, int]:
        """Re-encrypt under the current key (used by the rotate_token_keys job)."""
        return self.encrypt(self.decrypt(blob, key_version, aad), aad)


@lru_cache
def get_vault() -> TokenVault:
    from deployar.core.config import get_settings

    s = get_settings()
    return TokenVault(s.token_keys(), s.deployar_token_key_version)
