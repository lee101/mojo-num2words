# mojo-num2words

English number-to-words conversion implemented in
[Mojo](https://www.modular.com/mojo) and exposed through a Python API compatible
with [`num2words`](https://pypi.org/project/num2words/) 0.5.14 for the covered
subset.

```python
from mojo_num2words import num2words, num2words_batch

print(num2words(1_234_567))
# one million, two hundred and thirty-four thousand, five hundred and sixty-seven

print(num2words(42, to="ordinal"))
# forty-second

print(num2words_batch([7, 21, 1001]))
# ['seven', 'twenty-one', 'one thousand and one']
```

The scalar entry point has upstream's signature:

```python
num2words(number, ordinal=False, lang="en", to="cardinal", **kwargs)
```

## Coverage

The English `en` converter covers all five upstream conversion modes:

| mode | coverage |
| --- | --- |
| `cardinal` | positive and negative integers, integral floats/decimals, and decimal digit pronunciation |
| `ordinal` | non-negative integral values, including irregular English ordinals |
| `ordinal_num` | numeric ordinals and suffix rules |
| `year` | split-year pronunciation, `suffix=`, negative-year `BC`, and `longval=` compatibility |
| `currency` | all 20 currency codes in upstream's English converter, verbose/terse cents, separators, and currency adjectives |

Language tags which fall back to English upstream, such as `en_GB` and `en_US`,
also work. Native integer conversion covers
`-9,223,372,036,854,775,807` through `9,223,372,036,854,775,807`.
`num2words_batch` converts an integer iterable in one native call and is the
preferred API for bulk work.

Not covered:

- non-English converters;
- arbitrary-precision integers outside the documented native range, including
  `-9,223,372,036,854,775,808`;
- upstream converter classes and their mutable title-case internals.

Unsupported languages and conversion modes raise `NotImplementedError`, as
upstream does. Out-of-range integers raise `OverflowError` instead of silently
falling back to Python.

## Install

The repository pins a Mojo 1.0 nightly toolchain and the upstream package used
by its parity suite.

```bash
pixi install
pixi run build
pixi run test
```

The build creates `dist/libmojo-num2words.so`. The Python wrapper also builds a
missing or stale library on first use. To use a prebuilt library elsewhere, set
`MOJO_NUM2WORDS_LIB=/absolute/path/to/libmojo-num2words.so`.

Run the example without activating a shell:

```bash
pixi run python -c "from mojo_num2words import num2words; print(num2words(2026, to='year'))"
```

This prints `twenty twenty-six`.

## Performance

Measured on 2026-07-30 with an Intel Xeon E5-2697 v4 at 2.30 GHz, 72 logical
CPUs, and Linux 6.8.0-136-generic. Times are the best of three warm runs.
Every benchmark first asserts exact output equality with `num2words` 0.5.14.

| case | mojo-num2words | num2words 0.5.14 | speedup |
| --- | ---: | ---: | ---: |
| cardinal, 100k sequential | 285.1 ms | 9767.4 ms | 34.26x |
| cardinal, 100k random <= 10^15 | 356.3 ms | 38761.8 ms | 108.80x |
| ordinal, 100k sequential | 263.4 ms | 13662.1 ms | 51.87x |
| ordinal_num, 100k sequential | 212.1 ms | 10037.2 ms | 47.31x |
| year, 100k four-digit | 171.5 ms | 6051.8 ms | 35.29x |
| cardinal, 10k scalar calls | 397.0 ms | 2809.5 ms | 7.08x |

Run `pixi run bench` to reproduce the Markdown table. The large batch gains
come from replacing recursive Python object and string construction with one
tight native pass. Scalar calls still pay NumPy and ctypes setup on every
value, so batching remains considerably faster.

No SIMD, parallel, or GPU path is used. The measured batch cases are 34x to
109x faster than upstream. Conversion is branch-heavy, variable-length byte
emission rather than a homogeneous numeric loop, so this implementation uses a
scalar CPU kernel.

## How it works

`src/num2words.mojo` is one compilation unit containing the English
cardinal-group renderer, ordinal morphology, numeric suffix rules, and year
logic. It emits words directly into caller-owned UTF-8 byte rows; it does not
allocate strings or scratch memory.

The Python layer converts an integer batch to one contiguous `int64` array and
allocates a fixed-stride `uint8` output matrix plus one `int64` length per row.
Those three buffers cross the C ABI as integer addresses:

```text
Python int64 values ──┐
uint8 output rows ────┼── ctypes ──> @export("mnw_convert_i64") abi("C")
int64 row lengths ────┘
```

Mojo rebuilds each address as
`UnsafePointer[..., AnyOrigin[mut=True]]`, renders directly into its row, and
records the byte length. Python decodes only the written slices. Floats,
currency rounding, currency nouns, and API validation stay in the thin Python
facade; all integer wording is performed by Mojo.

## Validation

The 276-test suite compares against the real `num2words` 0.5.14 package. It
includes published-style boundary vectors, randomized 64-bit values across all
integer modes, decimal edge cases, every English currency option family,
language fallback, and failure behavior.

## License

MIT
