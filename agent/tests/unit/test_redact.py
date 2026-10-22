import base64
import io
import os

import structlog

from deployar.core.crypto import TokenVault, aad_for
from deployar.core.logging import configure_logging
from deployar.core.redact import redact


def test_decrypted_token_is_scrubbed_from_any_log_line() -> None:
    vault = TokenVault({"1": base64.b64encode(os.urandom(32)).decode()}, current_version=1)
    aad = aad_for("liara_connection", "c1", "u1")
    token = "eyJhbGciOi.liara-real-token-9f8e7d"
    blob, version = vault.encrypt(token, aad)
    assert vault.decrypt(blob, version, aad) == token

    out = io.StringIO()
    configure_logging(stream=out)
    log = structlog.get_logger()
    log.info("calling liara", header=f"Bearer {token}", nested={"note": f"got {token} back"})
    log.info(f"raw event with {token}")

    text = out.getvalue()
    assert token not in text
    assert "calling liara" in text


def test_sensitive_keys_are_masked() -> None:
    event = {"event": "x", "Authorization": "abc", "liara_token": "abc", "password": "p", "path": "/v1/me"}
    clean = redact(event)
    assert clean["path"] == "/v1/me"
    for k in ("Authorization", "liara_token", "password"):
        assert clean[k] == "<redacted>"


def test_known_secret_shapes_are_scrubbed() -> None:
    text = redact("DATABASE_URL=postgres://app:hunter2@db:5432/x APPROVAL_SECRET=abc123 Authorization: Bearer xyz.789")
    assert "hunter2" not in text
    assert "abc123" not in text
    assert "xyz.789" not in text
    assert "postgres://app:" in text  # user and host stay readable


def test_lists_and_non_strings_pass_through() -> None:
    assert redact([1, None, {"ok": True}]) == [1, None, {"ok": True}]
