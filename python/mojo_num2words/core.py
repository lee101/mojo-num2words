"""Python-compatible API backed by the Mojo integer renderer."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from numbers import Integral
from typing import Iterable

import numpy as np

from ._lib import addr, lib

_MIN = -(2**63) + 1
_MAX = 2**63 - 1
_STRIDE = 256
_MODES = {"cardinal": 0, "ordinal": 1, "ordinal_num": 2, "year": 3}

_CURRENCY_FORMS = {
    "AUD": (("dollar", "dollars"), ("cent", "cents")),
    "BYN": (("rouble", "roubles"), ("kopek", "kopeks")),
    "CAD": (("dollar", "dollars"), ("cent", "cents")),
    "EEK": (("kroon", "kroons"), ("sent", "senti")),
    "EUR": (("euro", "euro"), ("cent", "cents")),
    "GBP": (("pound sterling", "pounds sterling"), ("penny", "pence")),
    "LTL": (("litas", "litas"), ("cent", "cents")),
    "LVL": (("lat", "lats"), ("santim", "santims")),
    "USD": (("dollar", "dollars"), ("cent", "cents")),
    "RUB": (("rouble", "roubles"), ("kopek", "kopeks")),
    "SEK": (("krona", "kronor"), ("öre", "öre")),
    "NOK": (("krone", "kroner"), ("øre", "øre")),
    "PLN": (("zloty", "zlotys", "zlotu"), ("grosz", "groszy")),
    "MXN": (("peso", "pesos"), ("cent", "cents")),
    "RON": (("leu", "lei", "de lei"), ("ban", "bani", "de bani")),
    "INR": (("rupee", "rupees"), ("paisa", "paise")),
    "HUF": (("forint", "forint"), ("fillér", "fillér")),
    "ISK": (("króna", "krónur"), ("aur", "aurar")),
    "UZS": (("sum", "sums"), ("tiyin", "tiyins")),
    "SAR": (("saudi riyal", "saudi riyals"), ("halalah", "halalas")),
}
_CURRENCY_ADJECTIVES = {
    "AUD": "Australian",
    "BYN": "Belarusian",
    "CAD": "Canadian",
    "EEK": "Estonian",
    "USD": "US",
    "RUB": "Russian",
    "NOK": "Norwegian",
    "MXN": "Mexican",
    "RON": "Romanian",
    "INR": "Indian",
    "HUF": "Hungarian",
    "ISK": "íslenskar",
    "UZS": "Uzbekistan",
    "SAR": "Saudi",
}


def _check_lang(lang: str) -> None:
    if lang != "en" and lang[:2] != "en":
        raise NotImplementedError()


def _check_i64(value: int) -> int:
    converted = int(value)
    if converted != value:
        raise TypeError(f"{value!r} is not an integer")
    if not _MIN <= converted <= _MAX:
        raise OverflowError(f"integer {converted} is outside the supported 64-bit range")
    return converted


def _native(values: np.ndarray, mode: str) -> list[str]:
    values = np.ascontiguousarray(values, dtype=np.int64)
    count = values.size
    if count == 0:
        return []
    output = np.empty((count, _STRIDE), dtype=np.uint8)
    lengths = np.empty(count, dtype=np.int64)
    status = lib().mnw_convert_i64(
        addr(values), count, _MODES[mode], addr(output), _STRIDE, addr(lengths)
    )
    if status == -1:
        raise RuntimeError("native output stride is too small")
    if status == -3:
        raise TypeError("negative values cannot be converted to ordinals or years")
    if status == -4:
        raise OverflowError("integer is outside the supported 64-bit magnitude range")
    if status:
        raise RuntimeError(f"native conversion failed with status {status}")
    if np.any(lengths < 0) or np.any(lengths > _STRIDE):
        raise RuntimeError("native conversion returned an invalid output length")
    return [bytes(output[i, : lengths[i]]).decode("ascii") for i in range(count)]


def _integer(value: int, mode: str) -> str:
    return _native(np.array([_check_i64(value)], dtype=np.int64), mode)[0]


def _as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _cardinal_non_integer(value) -> str:
    try:
        float_value = float(value)
        decimal = Decimal(str(float_value))
    except (ValueError, TypeError):
        raise TypeError(f"type({value}) not in [long, int, float]")
    if not decimal.is_finite():
        raise TypeError(f"type({value}) not in [long, int, float]")
    precision = abs(decimal.as_tuple().exponent)
    integer = int(float_value)
    fractional = abs(float_value - integer) * 10**precision
    post = (
        int(round(fractional))
        if abs(round(fractional) - fractional) < 0.01
        else int(fractional)
    )
    text = str(post).zfill(precision)
    words = [_integer(integer, "cardinal"), "point"]
    words.extend(_integer(int(digit), "cardinal") for digit in text)
    return " ".join(words)


def _plural(value: int, forms: tuple[str, ...]) -> str:
    return forms[0] if value == 1 else forms[1]


def _currency_parts(value) -> tuple[int, int, bool]:
    if isinstance(value, Integral):
        negative = value < 0
        integer, cents = divmod(abs(int(value)), 100)
        return integer, cents, negative
    decimal = _as_decimal(value).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    negative = decimal < 0
    integer, fraction = divmod(abs(decimal), 1)
    return int(integer), int(fraction * 100), negative


def _currency(
    value,
    currency: str = "EUR",
    cents: bool = True,
    separator: str = ",",
    adjective: bool = False,
) -> str:
    try:
        major_forms, minor_forms = _CURRENCY_FORMS[currency]
    except KeyError as error:
        raise NotImplementedError(
            f'Currency code "{currency}" not implemented for "Num2Word_EN"'
        ) from error
    major, minor, negative = _currency_parts(value)
    major_forms = (
        tuple(f"{_CURRENCY_ADJECTIVES[currency]} {form}" for form in major_forms)
        if adjective and currency in _CURRENCY_ADJECTIVES
        else major_forms
    )
    major_words, minor_words = _native(
        np.array([_check_i64(major), _check_i64(minor)], dtype=np.int64), "cardinal"
    )
    if not cents:
        minor_words = f"{minor:02d}"
    prefix = "minus " if negative else ""
    return (
        f"{prefix}{major_words} {_plural(major, major_forms)}{separator} "
        f"{minor_words} {_plural(minor, minor_forms)}"
    )


def _year_non_integer(number, suffix) -> str:
    value = number
    if value < 0:
        value = abs(value)
        suffix = "BC" if not suffix else suffix
    high, low = divmod(value, 100)
    if high == 0 or (high % 10 == 0 and low < 10) or high >= 100:
        text = num2words(value)
    else:
        high_text = num2words(high)
        if low == 0:
            low_text = "hundred"
        elif low < 10:
            low_text = f"oh-{num2words(low)}"
        else:
            low_text = num2words(low)
        text = f"{high_text} {low_text}"
    return text if not suffix else f"{text} {suffix}"


def num2words(number, ordinal=False, lang="en", to="cardinal", **kwargs):
    """Match upstream ``num2words`` for English and signed 64-bit magnitudes."""
    _check_lang(lang)
    if ordinal:
        to = "ordinal"
    if to not in {"cardinal", "ordinal", "ordinal_num", "year", "currency"}:
        raise NotImplementedError()
    if to == "currency":
        return _currency(number, **kwargs)
    if isinstance(number, str):
        number = Decimal(number)
    try:
        is_integer = int(number) == number
    except (ValueError, TypeError, OverflowError):
        is_integer = False
    if to == "cardinal" and not is_integer:
        return _cardinal_non_integer(number)
    if to == "year" and not is_integer:
        suffix = kwargs.pop("suffix", None)
        kwargs.pop("longval", None)
        if kwargs:
            raise TypeError(f"unexpected keyword argument: {next(iter(kwargs))}")
        return _year_non_integer(number, suffix)
    if not is_integer:
        if to == "ordinal":
            raise TypeError(f"Cannot treat float {number} as ordinal.")
        if to == "ordinal_num":
            raise TypeError(f"Cannot treat float {number} as ordinal.")
        number = int(number)
    value = int(number)
    if to in {"ordinal", "ordinal_num"} and value < 0:
        raise TypeError(f"Cannot treat negative num {number} as ordinal.")
    if to == "ordinal_num":
        if kwargs:
            raise TypeError(f"unexpected keyword argument: {next(iter(kwargs))}")
        suffix = _integer(value, "ordinal_num")[-2:]
        return f"{number}{suffix}"
    if to == "year":
        suffix = kwargs.pop("suffix", None)
        kwargs.pop("longval", None)
        if kwargs:
            raise TypeError(f"unexpected keyword argument: {next(iter(kwargs))}")
        if value < 0:
            value = abs(value)
            suffix = "BC" if not suffix else suffix
        result = _integer(value, "year")
        return result if not suffix else f"{result} {suffix}"
    if kwargs:
        raise TypeError(f"unexpected keyword argument: {next(iter(kwargs))}")
    return _integer(value, to)


def num2words_batch(
    numbers: Iterable[int],
    ordinal: bool = False,
    lang: str = "en",
    to: str = "cardinal",
    **kwargs,
) -> list[str]:
    """Convert an integer iterable with one native call."""
    _check_lang(lang)
    if ordinal:
        to = "ordinal"
    if to not in _MODES:
        return [num2words(value, lang=lang, to=to, **kwargs) for value in numbers]
    raw = list(numbers)
    values = np.array([_check_i64(value) for value in raw], dtype=np.int64)
    if to in {"ordinal", "ordinal_num"} and np.any(values < 0):
        value = raw[int(np.flatnonzero(values < 0)[0])]
        raise TypeError(f"Cannot treat negative num {value} as ordinal.")
    if to == "year":
        suffix = kwargs.pop("suffix", None)
        kwargs.pop("longval", None)
        if kwargs:
            raise TypeError(f"unexpected keyword argument: {next(iter(kwargs))}")
        negative = values < 0
        values = np.abs(values)
        result = _native(values, to)
        return [
            text + (f" {suffix or 'BC'}" if is_negative else (f" {suffix}" if suffix else ""))
            for text, is_negative in zip(result, negative)
        ]
    if kwargs:
        raise TypeError(f"unexpected keyword argument: {next(iter(kwargs))}")
    return _native(values, to)
