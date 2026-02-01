# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import inspect
import os
import sys
from typing import Any

from dotenv import load_dotenv
from loguru import logger
from wcwidth import wcswidth

load_dotenv()

_log_handle_a = None
_log_handle_b = None


def add_sink(sink=sys.stdout) -> None:
    global _log_handle_a, _log_handle_b

    if _log_handle_a is not None:
        logger.remove(_log_handle_a)
    if _log_handle_b is not None:
        logger.remove(_log_handle_b)

    _log_handle_a = logger.add(
        sink,
        format="<d>{time:YYYY-MM-DDTHH:mm:ss}</d> <lvl>{level:<5}</lvl> {extra[context]}<b><M>{extra[source]}</M></b>{extra[padding]} {message}",
        colorize=True,
        level=5,
        filter=lambda record: not record["extra"].get("overflow", False),
    )
    _log_handle_b = logger.add(
        sys.stdout,
        format="{extra[padding]:33}{message}",
        colorize=True,
        level=5,
        filter=lambda record: record["extra"].get("overflow", False),
    )


logger.remove(0)
add_sink()
logger.level(name="WARN", no=30, color="<yellow>")
logger.level(name="CRIT", no=50, color="<red>")

log_level_names = {
    50: "CRIT",
    40: "ERROR",
    30: "WARN",
    20: "INFO",
    10: "DEBUG",
    5: "TRACE",
}

# reverse map log_level_names
log_names_to_level = {v: k for k, v in log_level_names.items()}


def _read_env_log(key, default):
    level = os.getenv(key, default)

    try:
        try:
            level = log_names_to_level[level.upper()]
        except Exception:
            level = max(0, min(int(level), 50))
    except Exception:
        level = default

    return level


_log_level = _read_env_log("LOG", 20)


_context_replace = {
    "quasarr": "",  # /quasarr/*
    "arr": "🏴‍☠️",  # /quasarr/arr/*
    "api": "🌐",  # /quasarr/api/*
    "captcha": "🧩",  # /quasarr/api/captcha/*
    "config": "⚙️",  # /quasarr/api/config/*
    "sponsors_helper": "💖",  # /quasarr/api/sponsors_helper/*
    "downloads": "📥",  # /quasarr/downloads/*
    "linkcrypters": "🔐",  # /quasarr/linkcrypters/*
    "filecrypt": "🛡️",  # /quasarr/linkcrypters/filecrypt.py
    "hide": "👻",  # /quasarr/linkcrypters/hide.py
    "packages": "📦",  # /quasarr/api/packages/*
    "providers": "🔌",  # /quasarr/providers/*
    "imdb_metadata": "🎬",  # /quasarr/providers/imdb_metadata.py
    "jd_cache": "📇",  # /quasarr/providers/jd_cache.py
    "log": "📝",  # /quasarr/providers/log.py
    "myjd_api": "🔑",  # /quasarr/providers/myjd_api.py
    "notifications": "🔔",  # /quasarr/providers/notifications.py
    "shared_state": "🧠",  # /quasarr/providers/shared_state.py
    "sessions": "🍪",  # /quasarr/providers/sessions/*
    "search": "🔍",  # /quasarr/search/*
    "storage": "💽",  # /quasarr/storage/*
    "setup": "🛠️",  # /quasarr/storage/setup.py
    "sqlite_database": "🗃️",  # /quasarr/storage/sqlite_database.py
    "sources": "🧲",  # /quasarr/*/sources/*
    "utils": "🧰",  # /quasarr/providers/utils.py
}


def _contexts_to_str(contexts: list[str]) -> str:
    source = ""
    if len(contexts) == 0:
        return "", source

    if contexts:
        if contexts[-1].__len__() == 2:
            source = contexts.pop()
        elif contexts[0] == "quasarr" and contexts.__len__() == 1:
            return "🌌", source

    return "".join(_context_replace.get(c, c) for c in contexts), source.upper()


def get_log_level_name(level: int = _log_level) -> str:
    return log_level_names[level]


def get_log_level(contexts: list[str] = []) -> int:
    level = _log_level

    for context in contexts:
        context_level = _read_env_log(
            "LOG" + f"_{context.upper()}" if context else "", _log_level
        )
        if context_level < level:
            level = context_level

    return level


_log_line_max_length = 160


class _Logger:
    def __init__(self, contexts: list[str] = []):
        self.level = get_log_level(contexts)
        context, source = _contexts_to_str(contexts)
        width = wcswidth(context + source)
        padding = 6 - width

        self.logger_alt = logger.bind(
            context=context,
            source=source,
            padding=" " * padding,
        )
        self.logger = self.logger_alt.opt(colors=True)

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.level > level:
            return
        try:
            try:
                for i in range(0, msg.__len__(), _log_line_max_length):
                    merged_kwargs = {
                        **kwargs,
                        "overflow": i > 0,
                    }

                    self.logger.log(
                        log_level_names[level],
                        msg[i : i + _log_line_max_length],
                        *args,
                        **merged_kwargs,
                    )
            except ValueError as e:
                # Fallback: try logging without color parsing if tags are mismatched
                self.logger_alt.log(log_level_names[level], msg, *args, **kwargs)

                if self.level <= 10:
                    self.logger_alt.debug(
                        f"Log formatting error: {e} | Original message: {msg}"
                    )
        except Exception:
            # Fallback: just print to stderr if logging fails completely
            print(f"LOGGING FAILURE: {msg}", file=sys.stderr)

    def crit(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(50, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(40, msg, *args, **kwargs)

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(30, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(20, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(10, msg, *args, **kwargs)

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(5, msg, *args, **kwargs)


_loggers = {}


def get_logger(context: str) -> _Logger:
    if context not in _loggers:
        _loggers[context] = _Logger(context.split(".") if context else [])
    return _loggers[context]


def _get_logger_for_module() -> _Logger:
    # get the calling module filename
    frame = inspect.currentframe()
    caller_frame = frame.f_back.f_back
    module_name = caller_frame.f_globals["__name__"]

    return get_logger(module_name)


def crit(msg: str) -> None:
    _get_logger_for_module().crit(msg)


def error(msg: str) -> None:
    _get_logger_for_module().error(msg)


def warn(msg: str) -> None:
    _get_logger_for_module().warn(msg)


def info(msg: str) -> None:
    _get_logger_for_module().info(msg)


def debug(msg: str) -> None:
    _get_logger_for_module().debug(msg)


def trace(msg: str) -> None:
    _get_logger_for_module().trace(msg)
