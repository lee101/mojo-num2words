"""ctypes bindings for the Mojo English number renderer."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB_PATH = os.environ.get(
    "MOJO_NUM2WORDS_LIB", os.path.join(ROOT, "dist", "libmojo-num2words.so")
)

I = ctypes.c_int64
_SIGNATURES = {"mnw_convert_i64": ([I, I, I, I, I, I], I)}


class BuildError(RuntimeError):
    pass


def build(force: bool = False) -> str:
    source = os.path.join(ROOT, "src", "num2words.mojo")
    if os.path.exists(LIB_PATH) and not force:
        if os.environ.get("MOJO_NUM2WORDS_LIB") or os.path.getmtime(LIB_PATH) >= os.path.getmtime(source):
            return LIB_PATH
    if os.environ.get("MOJO_NUM2WORDS_LIB"):
        raise BuildError(f"MOJO_NUM2WORDS_LIB does not exist or is stale: {LIB_PATH}")
    pixi = shutil.which("pixi")
    command = (
        [pixi, "run", "--manifest-path", os.path.join(ROOT, "pixi.toml"), "build"]
        if pixi
        else ["bash", os.path.join(ROOT, "build", "build.sh")]
    )
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    if proc.returncode or not os.path.exists(LIB_PATH):
        raise BuildError((proc.stderr or proc.stdout).strip()[:4000])
    return LIB_PATH


_library: ctypes.CDLL | None = None


def lib() -> ctypes.CDLL:
    global _library
    if _library is None:
        _library = ctypes.CDLL(build())
        for name, (argtypes, restype) in _SIGNATURES.items():
            function = getattr(_library, name)
            function.argtypes = argtypes
            function.restype = restype
    return _library


def addr(array: np.ndarray) -> int:
    return int(array.ctypes.data)

