"""Static exception data and source classification helpers."""

from __future__ import annotations

import builtins
import importlib.util
import sysconfig
from pathlib import Path

BUILTIN_EXCEPTIONS = {
    "int": ["ValueError", "TypeError"],
    "float": ["ValueError", "TypeError"],
    "str": ["TypeError"],
    "dict": ["TypeError"],
    "list": ["TypeError"],
    "tuple": ["TypeError"],
    "set": ["TypeError"],
    "open": ["FileNotFoundError", "OSError"],
    "len": ["TypeError"],
    "sum": ["TypeError"],
    "min": ["ValueError", "TypeError"],
    "max": ["ValueError", "TypeError"],
    "sorted": ["TypeError"],
    "reversed": ["TypeError"],
    "enumerate": ["TypeError"],
    "zip": ["TypeError"],
    "map": ["TypeError"],
    "filter": ["TypeError"],
}

STDLIB_METHOD_EXCEPTIONS = {
    "pathlib.Path.open": ["FileNotFoundError", "OSError"],
    "pathlib.Path.read_bytes": ["FileNotFoundError", "OSError"],
    "pathlib.Path.read_text": ["FileNotFoundError", "OSError", "UnicodeDecodeError"],
    "pathlib.Path.write_bytes": ["OSError", "TypeError"],
    "pathlib.Path.write_text": ["OSError", "TypeError", "UnicodeEncodeError"],
}

SUMMARY_EXCEPTIONS = {
    "json.loads": ["JSONDecodeError", "TypeError"],
    "requests.delete": ["ConnectionError", "RequestException", "Timeout", "TooManyRedirects"],
    "requests.get": ["ConnectionError", "RequestException", "Timeout", "TooManyRedirects"],
    "requests.patch": ["ConnectionError", "RequestException", "Timeout", "TooManyRedirects"],
    "requests.post": ["ConnectionError", "RequestException", "Timeout", "TooManyRedirects"],
    "requests.put": ["ConnectionError", "RequestException", "Timeout", "TooManyRedirects"],
    "urllib.request.urlopen": ["HTTPError", "URLError"],
}

NATIVE_EXCEPTION_NAMES = frozenset(
    name
    for name, value in vars(builtins).items()
    if isinstance(value, type) and issubclass(value, BaseException)
)

STDLIB_ROOTS = tuple(
    Path(value).resolve()
    for key, value in sysconfig.get_paths().items()
    if key in {"platstdlib", "stdlib"} and value
)


def module_source_path(module_name: str) -> Path | None:
    """Return the Python source path for an importable module, when available."""

    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None:
        return None
    if spec.origin in {"built-in", "frozen"}:
        return None

    origin_path = Path(spec.origin)
    if origin_path.suffix != ".py":
        return None
    return origin_path


def source_kind_for_path(path: Path) -> str:
    """Label a resolved source file as stdlib or third-party library code."""

    resolved_path = path.resolve()
    if is_stdlib_path(resolved_path):
        return "stdlib source"
    return "library source"


def summary_source_for_name(name: str) -> str:
    """Label a summary-backed call as stdlib or third-party."""

    module_name, _, _ = name.rpartition(".")
    if not module_name:
        return "library summary"

    source_path = module_source_path(module_name)
    if source_path is not None and is_stdlib_path(source_path.resolve()):
        return "stdlib summary"
    return "library summary"


def is_stdlib_path(path: Path) -> bool:
    """Return whether a path belongs to the current Python stdlib."""

    return any(is_relative_to(path, root) for root in STDLIB_ROOTS)


def is_relative_to(path: Path, root: Path) -> bool:
    """Compatibility helper for checking whether one path sits under another."""

    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
