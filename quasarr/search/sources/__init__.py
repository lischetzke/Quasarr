# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import importlib
import inspect
import pkgutil

from quasarr.providers.log import error, warn
from quasarr.search.sources.helpers.abstract_source import AbstractSource

_sources = {}
_source_module_names = []


def get_source_module_names() -> list[str]:
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
    if not _sources:
        for module_name in get_source_module_names():
            try:
                mod = importlib.import_module(f"{__name__}.{module_name}")
            except Exception as e:
                error(f"Error importing {module_name.upper()}: {e}")
                continue

            if hasattr(mod, "Source"):
                if inspect.isclass(mod.Source) and issubclass(
                    mod.Source, AbstractSource
                ):
                    try:
                        _sources[module_name] = mod.Source()
                    except Exception as e:
                        error(f"Error instantiating {module_name.upper()}: {e}")
                else:
                    error(
                        f"Source '{module_name.upper()}.Source' does not implement AbstractSource"
                    )
            else:
                warn(f"Source '{module_name.upper()}' does not expose a Source class")
    return _sources
