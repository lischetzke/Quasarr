# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import importlib
import inspect
import pkgutil

from quasarr.providers.log import error, warn
from quasarr.search.sources.helpers.abstract_source import AbstractSource

_sources = {}


def get_sources() -> dict[str, AbstractSource]:
    if not _sources:
        for _, module_name, _ in pkgutil.iter_modules(__path__):
            mod = importlib.import_module(f"{__name__}.{module_name}")
            if module_name == "abstract" or module_name == "helpers":
                continue

            if hasattr(mod, "Source"):
                if inspect.isclass(mod.Source) and issubclass(
                    mod.Source, AbstractSource
                ):
                    try:
                        _sources[module_name] = mod.Source()
                    except Exception as e:
                        error(f"Error instantiating {module_name}: {e}")
                else:
                    error(
                        f"Source '{module_name.upper()}.Source' does not implement AbstractSource"
                    )
            else:
                warn(f"Source '{module_name.upper()}' does not expose a Search class")
    return _sources
