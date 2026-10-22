import uuid

from deployar.core.ids import new_id


def test_new_id_is_uuid7() -> None:
    i = new_id()
    assert isinstance(i, uuid.UUID)
    assert i.version == 7


def test_ids_sort_by_creation() -> None:
    ids = [new_id() for _ in range(100)]
    assert ids == sorted(ids)
