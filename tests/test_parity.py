from decimal import Decimal
import inspect

import numpy as np
import pytest
from num2words import num2words as upstream

from mojo_num2words import num2words, num2words_batch
from mojo_num2words._lib import lib


CARDINAL_CASES = [
    -9_223_372_036_854_775_807,
    -101,
    -1,
    0,
    1,
    11,
    19,
    20,
    21,
    40,
    99,
    100,
    101,
    115,
    999,
    1_000,
    1_001,
    1_100,
    10_001,
    1_000_001,
    1_001_001,
    1_234_567_890_123,
    10**18,
    9_223_372_036_854_775_807,
]


@pytest.mark.parametrize("value", CARDINAL_CASES)
def test_cardinal_matches_upstream(value):
    assert num2words(value) == upstream(value)


@pytest.mark.parametrize(
    "value",
    [0, 1, 2, 3, 5, 8, 11, 12, 13, 20, 21, 22, 30, 99, 100, 101, 120, 1_000, 1_001, 1_100, 10**18],
)
def test_ordinal_matches_upstream(value):
    assert num2words(value, to="ordinal") == upstream(value, to="ordinal")
    assert num2words(value, ordinal=True) == upstream(value, ordinal=True)
    assert num2words(value, to="ordinal_num") == upstream(value, to="ordinal_num")


@pytest.mark.parametrize(
    "value",
    [-2024, 0, 1, 99, 100, 101, 1000, 1001, 1010, 1900, 1905, 2000, 2009, 2010, 2024, 9999, 10000],
)
def test_year_matches_upstream(value):
    assert num2words(value, to="year") == upstream(value, to="year")
    assert num2words(value, to="year", suffix="AD") == upstream(
        value, to="year", suffix="AD"
    )


@pytest.mark.parametrize(
    "value",
    [0.0, 1.0, 1.2, 1.02, -1.2, 1.234, 1.239999999, Decimal("1.2300"), "001.020"],
)
def test_float_cardinal_matches_upstream(value):
    assert num2words(value) == upstream(value)
    assert num2words(value, to="year") == upstream(value, to="year")


@pytest.mark.parametrize(
    "currency",
    [
        "AUD",
        "BYN",
        "CAD",
        "EEK",
        "EUR",
        "GBP",
        "LTL",
        "LVL",
        "USD",
        "RUB",
        "SEK",
        "NOK",
        "PLN",
        "MXN",
        "RON",
        "INR",
        "HUF",
        "ISK",
        "UZS",
        "SAR",
    ],
)
@pytest.mark.parametrize("value", [0, 1, 100, 101, 12345, -12345, 0.01, 1.01, Decimal("1.005")])
def test_currency_matches_upstream(currency, value):
    for options in (
        {},
        {"cents": False},
        {"adjective": True},
        {"separator": " and"},
    ):
        assert num2words(value, to="currency", currency=currency, **options) == upstream(
            value, to="currency", currency=currency, **options
        )


def test_randomized_integer_parity_all_modes():
    rng = np.random.default_rng(2026)
    values = rng.integers(0, 2**63 - 1, size=500, dtype=np.int64)
    for mode in ("cardinal", "ordinal", "ordinal_num", "year"):
        got = num2words_batch(values, to=mode)
        expected = [upstream(int(value), to=mode) for value in values]
        assert got == expected


def test_batch_cardinal_matches_scalar_and_preserves_order():
    values = [0, -7, 21, 1001, 10**18, 42, 42]
    assert num2words_batch(values) == [num2words(value) for value in values]
    assert num2words_batch([]) == []


def test_batch_year_suffix_and_negative_default():
    values = [-2024, 2024]
    assert num2words_batch(values, to="year") == [
        upstream(value, to="year") for value in values
    ]
    assert num2words_batch(values, to="year", suffix="CE") == [
        upstream(value, to="year", suffix="CE") for value in values
    ]


@pytest.mark.parametrize("value", [0, 2024, 10_000, -2024])
def test_year_longval_compatibility(value):
    assert num2words(value, to="year", longval=True) == upstream(
        value, to="year", longval=True
    )


def test_language_fallback_and_unsupported_language():
    assert num2words(42, lang="en_GB") == upstream(42, lang="en_GB")
    assert num2words(42, lang="en_US") == upstream(42, lang="en_US")
    with pytest.raises(NotImplementedError):
        num2words(42, lang="fr")


def test_errors_match_upstream_categories():
    with pytest.raises(TypeError):
        num2words(-1, to="ordinal")
    with pytest.raises(TypeError):
        num2words(1.5, to="ordinal")
    with pytest.raises(NotImplementedError):
        num2words(1, to="made_up")
    with pytest.raises(NotImplementedError):
        num2words(1, to="currency", currency="ZZZ")
    with pytest.raises(OverflowError):
        num2words(2**63)
    with pytest.raises(TypeError):
        num2words_batch([1.5])


def test_public_signature_matches_upstream():
    assert inspect.signature(num2words) == inspect.signature(upstream)
    assert num2words(1.0, to="ordinal") == upstream(1.0, to="ordinal")
    assert num2words(1.0, to="ordinal_num") == upstream(1.0, to="ordinal_num")


@pytest.mark.parametrize(
    ("values_addr", "count", "mode", "output_addr", "stride", "lengths_addr"),
    [
        (0, 1, 0, 1, 1, 1),
        (1, 1, 0, 0, 1, 1),
        (1, 1, 0, 1, 1, 0),
        (1, -1, 0, 1, 1, 1),
        (1, 1, -1, 1, 1, 1),
        (1, 1, 4, 1, 1, 1),
        (1, 1, 0, 1, 0, 1),
    ],
)
def test_native_rejects_invalid_abi_arguments(
    values_addr, count, mode, output_addr, stride, lengths_addr
):
    assert (
        lib().mnw_convert_i64(
            values_addr, count, mode, output_addr, stride, lengths_addr
        )
        == -2
    )


def test_native_zero_count_accepts_null_buffers():
    assert lib().mnw_convert_i64(0, 0, 0, 0, 1, 0) == 0


def test_native_rejects_wrapping_buffer_spans():
    max_i64 = 2**63 - 1
    assert lib().mnw_convert_i64(1, max_i64, 0, 1, 2, 1) == -2
    assert lib().mnw_convert_i64(max_i64, 1, 0, 1, 1, 1) == -2
    assert lib().mnw_convert_i64(1, 1, 0, max_i64, 1, 1) == -2
    assert lib().mnw_convert_i64(1, 1, 0, 1, 1, max_i64) == -2


def test_native_rejects_unrepresentable_negative_magnitude():
    values = np.array([-(2**63)], dtype=np.int64)
    output = np.empty(256, dtype=np.uint8)
    lengths = np.full(1, -99, dtype=np.int64)
    assert (
        lib().mnw_convert_i64(
            values.ctypes.data,
            1,
            0,
            output.ctypes.data,
            output.size,
            lengths.ctypes.data,
        )
        == -4
    )
    assert lengths[0] == -99


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_native_short_stride_does_not_overwrite_guard_bytes(mode):
    values = np.array([9_223_372_036_854_775_807], dtype=np.int64)
    output = np.full(10, 0xA5, dtype=np.uint8)
    lengths = np.full(1, -99, dtype=np.int64)
    status = lib().mnw_convert_i64(
        values.ctypes.data,
        values.size,
        mode,
        output[2:3].ctypes.data,
        1,
        lengths.ctypes.data,
    )
    assert status == -1
    assert output[:2].tolist() == [0xA5, 0xA5]
    assert output[3:].tolist() == [0xA5] * 7
    assert lengths[0] == -99


def test_native_exact_fit_writes_length_without_a_terminator():
    values = np.array([0], dtype=np.int64)
    output = np.full(6, 0xA5, dtype=np.uint8)
    lengths = np.empty(1, dtype=np.int64)
    status = lib().mnw_convert_i64(
        values.ctypes.data,
        1,
        0,
        output[1:5].ctypes.data,
        4,
        lengths.ctypes.data,
    )
    assert status == 0
    assert lengths[0] == 4
    assert bytes(output[1:5]) == b"zero"
    assert output[[0, 5]].tolist() == [0xA5, 0xA5]
