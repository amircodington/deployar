"""Secret values by reference: stored encrypted, resolved only inside set_env, never in a tool result."""

import uuid

from sqlalchemy import select

from deployar import messages_fa as fa
from deployar.core.crypto import aad_for, get_vault
from deployar.core.errors import DeployarError
from deployar.core.ids import new_id
from deployar.core.redact import register_secret
from deployar.models import SecretValue
from deployar.tools.registry import ToolContext


async def store_secret(ctx: ToolContext, key: str, value: str, origin: str, project_id: uuid.UUID | None = None) -> str:
    """Returns the value_ref (`secret:<id>`), the only handle the model gets."""
    sid = new_id()
    blob, version = get_vault().encrypt(value, aad_for("secret_value", sid, ctx.user_id))
    register_secret(value)
    async with ctx.sessions.begin() as s:
        s.add(SecretValue(id=sid, user_id=ctx.user_id, project_id=project_id, key=key, ciphertext=blob,
                          key_version=version, origin=origin))  # fmt: skip
    return f"secret:{sid}"


async def load_secret(ctx: ToolContext, ref: str) -> str:
    try:
        sid = uuid.UUID(ref.removeprefix("secret:"))
    except ValueError as e:
        raise DeployarError("bad_value_ref", fa.BAD_VALUE_REF, ref) from e
    async with ctx.sessions() as s:
        row = await s.scalar(select(SecretValue).where(SecretValue.id == sid, SecretValue.user_id == ctx.user_id))
    if row is None:
        raise DeployarError("bad_value_ref", fa.BAD_VALUE_REF, ref)
    return get_vault().decrypt(row.ciphertext, row.key_version, aad_for("secret_value", row.id, ctx.user_id))
