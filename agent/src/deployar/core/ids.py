"""UUIDv7 ids: time-ordered, so primary keys index well and sort by creation."""

import uuid

from uuid_utils.compat import uuid7


def new_id() -> uuid.UUID:
    return uuid7()
