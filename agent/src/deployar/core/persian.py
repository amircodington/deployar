"""Digits are stored ASCII and rendered Persian (ARCHITECTURE.md §11)."""

_ASCII = "0123456789"
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC = "٠١٢٣٤٥٦٧٨٩"

_TO_PERSIAN = str.maketrans(_ASCII, _PERSIAN)
_TO_ASCII = str.maketrans(_PERSIAN + _ARABIC, _ASCII * 2)


def to_persian_digits(text: str) -> str:
    return text.translate(_TO_PERSIAN)


def to_ascii_digits(text: str) -> str:
    return text.translate(_TO_ASCII)
