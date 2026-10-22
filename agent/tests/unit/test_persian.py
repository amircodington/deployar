from deployar.core.persian import to_ascii_digits, to_persian_digits


def test_ascii_to_persian() -> None:
    assert to_persian_digits("RAM 512 MB, 2,000,000") == "RAM ۵۱۲ MB, ۲,۰۰۰,۰۰۰"


def test_persian_and_arabic_to_ascii() -> None:
    assert to_ascii_digits("۲,۰۰۰,۰۰۰ تومان") == "2,000,000 تومان"
    assert to_ascii_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"


def test_round_trip() -> None:
    s = "0123456789"
    assert to_ascii_digits(to_persian_digits(s)) == s
