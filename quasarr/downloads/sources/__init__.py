import importlib
import inspect
import pkgutil

from quasarr.downloads.sources.helpers.abstract_source import AbstractSource
from quasarr.providers.log import error, warn

_source_module_names = []
_sources = {}


def get_download_source_module_names() -> list[str]:
    global _source_module_names

    if _source_module_names:
        return _source_module_names

    discovered = []
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name == "helpers" or module_name.startswith("_"):
            continue
        discovered.append(module_name)

    _source_module_names = sorted(discovered)
    return _source_module_names


def get_sources() -> dict[str, AbstractSource]:
    global _sources

    if _sources:
        return _sources

    for module_name in get_download_source_module_names():
        try:
            mod = importlib.import_module(f"{__name__}.{module_name}")
        except Exception as e:
            error(f"Error importing download source {module_name.upper()}: {e}")
            continue

        if not hasattr(mod, "Source"):
            warn(
                f"Download source '{module_name.upper()}' does not expose a Source class"
            )
            continue

        if not inspect.isclass(mod.Source) or not issubclass(
            mod.Source, AbstractSource
        ):
            error(
                f"Download source '{module_name.upper()}.Source' does not implement AbstractSource"
            )
            continue

        try:
            source = mod.Source()
        except Exception as e:
            error(f"Error instantiating download source {module_name.upper()}: {e}")
            continue

        source_key = str(source.initials or module_name).lower().strip()
        if not source_key:
            error(
                f"Download source '{module_name.upper()}' has an invalid initials value"
            )
            continue

        if source_key in _sources:
            warn(
                f"Download source key '{source_key}' already registered; skipping duplicate from {module_name.upper()}"
            )
            continue

        _sources[source_key] = source

    return _sources
