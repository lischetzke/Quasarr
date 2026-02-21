import importlib
import pkgutil
from typing import Callable

from quasarr.providers.log import error, warn

_source_module_names = []
_source_getters = {}


def get_download_source_module_names() -> list[str]:
    global _source_module_names

    if _source_module_names:
        return _source_module_names

    discovered = []
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name.startswith("_"):
            continue
        discovered.append(module_name)

    _source_module_names = sorted(discovered)
    return _source_module_names


def get_download_source_getters() -> dict[str, Callable]:
    global _source_getters

    if _source_getters:
        return _source_getters

    for module_name in get_download_source_module_names():
        try:
            mod = importlib.import_module(f"{__name__}.{module_name}")
        except Exception as e:
            error(f"Error importing download source {module_name}: {e}")
            continue

        source_key = module_name
        hostname = getattr(mod, "hostname", None)
        if isinstance(hostname, str) and hostname.strip():
            source_key = hostname.lower().strip()

        getter = getattr(mod, f"get_{module_name}_download_links", None)
        if not callable(getter):
            getter = getattr(mod, f"get_{source_key}_download_links", None)

        if not callable(getter):
            warn(
                f"Download source '{module_name.upper()}' does not expose a valid getter"
            )
            continue

        if source_key in _source_getters:
            warn(
                f"Download source key '{source_key}' already registered; skipping duplicate from {module_name.upper()}"
            )
            continue

        _source_getters[source_key] = getter

    return _source_getters
