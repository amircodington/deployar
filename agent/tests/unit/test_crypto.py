import base64
import os

import pytest

from deployar.core.crypto import TokenVault, aad_for
from deployar.core.errors import DeployarError


def key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


K1, K2 = key(), key()
AAD = aad_for("liara_connection", "conn-1", "user-1")


def test_round_trip() -> None:
    vault = TokenVault({"1": K1}, current_version=1)
    blob, version = vault.encrypt("liara-secret-token", AAD)
    assert version == 1
    assert b"liara-secret-token" not in blob
    assert vault.decrypt(blob, version, AAD) == "liara-secret-token"


def test_ciphertext_moved_to_another_row_fails() -> None:
    vault = TokenVault({"1": K1}, current_version=1)
    blob, version = vault.encrypt("liara-secret-token", AAD)
    other_row = aad_for("liara_connection", "conn-2", "user-1")
    with pytest.raises(DeployarError) as e:
        vault.decrypt(blob, version, other_row)
    assert e.value.code == "token_decrypt_failed"


def test_tampered_ciphertext_fails() -> None:
    vault = TokenVault({"1": K1}, current_version=1)
    blob, version = vault.encrypt("liara-secret-token", AAD)
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(DeployarError):
        vault.decrypt(tampered, version, AAD)


def test_key_rotation_round_trips() -> None:
    old = TokenVault({"1": K1}, current_version=1)
    blob, version = old.encrypt("liara-secret-token", AAD)

    mixed = TokenVault({"1": K1, "2": K2}, current_version=2)
    assert mixed.decrypt(blob, version, AAD) == "liara-secret-token"  # old rows still readable
    new_blob, new_version = mixed.rotate(blob, version, AAD)
    assert new_version == 2

    rotated = TokenVault({"2": K2}, current_version=2)  # key 1 removed after the batch job
    assert rotated.decrypt(new_blob, new_version, AAD) == "liara-secret-token"


def test_unknown_key_version_fails() -> None:
    vault = TokenVault({"2": K2}, current_version=2)
    with pytest.raises(DeployarError) as e:
        vault.decrypt(b"\0" * 40, 1, AAD)
    assert e.value.code == "token_key_missing"


def test_bad_keys_rejected() -> None:
    with pytest.raises(ValueError):
        TokenVault({"1": base64.b64encode(b"short").decode()}, current_version=1)
    with pytest.raises(ValueError):
        TokenVault({"1": K1}, current_version=2)
