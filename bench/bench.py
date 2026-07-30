"""Benchmark Mojo batch conversion against upstream num2words."""

from __future__ import annotations

import math
import os
import platform
import sys
import time

import numpy as np

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"),
)

from mojo_num2words import num2words, num2words_batch  # noqa: E402
from num2words import num2words as upstream  # noqa: E402


def timeit(function, repeat: int = 3) -> float:
    best = math.inf
    for _ in range(repeat):
        start = time.perf_counter()
        function()
        best = min(best, time.perf_counter() - start)
    return best


def cpu_name() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown CPU"


def main() -> None:
    rng = np.random.default_rng(7)
    random_values = rng.integers(0, 10**15, size=100_000, dtype=np.int64)
    sequential = np.arange(100_000, dtype=np.int64)
    year_values = rng.integers(1000, 10_000, size=100_000, dtype=np.int64)

    cases = [
        ("cardinal, 100k sequential", sequential, "cardinal"),
        ("cardinal, 100k random <= 10^15", random_values, "cardinal"),
        ("ordinal, 100k sequential", sequential, "ordinal"),
        ("ordinal_num, 100k sequential", sequential, "ordinal_num"),
        ("year, 100k four-digit", year_values, "year"),
    ]

    num2words_batch([1, 21, 1001])
    rows = []
    for name, values, mode in cases:
        ours = lambda: num2words_batch(values, to=mode)
        theirs = lambda: [upstream(int(value), to=mode) for value in values]
        assert ours() == theirs()
        mojo_seconds = timeit(ours)
        upstream_seconds = timeit(theirs)
        rows.append((name, mojo_seconds, upstream_seconds, upstream_seconds / mojo_seconds))

    scalar_values = [int(value) for value in random_values[:10_000]]
    ours_scalar = lambda: [num2words(value) for value in scalar_values]
    theirs_scalar = lambda: [upstream(value) for value in scalar_values]
    assert ours_scalar() == theirs_scalar()
    mojo_seconds = timeit(ours_scalar)
    upstream_seconds = timeit(theirs_scalar)
    rows.append(
        ("cardinal, 10k scalar calls", mojo_seconds, upstream_seconds, upstream_seconds / mojo_seconds)
    )

    print(f"Machine: {cpu_name()}, {os.cpu_count()} logical CPUs, {platform.system()} {platform.release()}")
    print()
    print("| case | mojo-num2words | num2words 0.5.14 | speedup |")
    print("| --- | ---: | ---: | ---: |")
    for name, mojo_seconds, upstream_seconds, speedup in rows:
        print(
            f"| {name} | {mojo_seconds * 1000:.1f} ms | "
            f"{upstream_seconds * 1000:.1f} ms | {speedup:.2f}x |"
        )


if __name__ == "__main__":
    main()
