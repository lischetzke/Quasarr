# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

from bottle import request, response

from quasarr.constants import (
    TIMEOUT_SLOW_MODE_DEFINITIONS,
    TIMEOUT_SLOW_MODE_TABLE,
    apply_timeout_slow_mode_settings,
)
from quasarr.storage.sqlite_database import DataBase


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _read_timeout_slow_mode_settings():
    timeout_settings_db = DataBase(TIMEOUT_SLOW_MODE_TABLE)

    settings = {}
    for timeout_key in TIMEOUT_SLOW_MODE_DEFINITIONS:
        settings[timeout_key] = _coerce_bool(
            timeout_settings_db.retrieve(timeout_key),
            default=False,
        )

    return settings


def refresh_timeout_slow_mode_settings(shared_state):
    settings = _read_timeout_slow_mode_settings()
    shared_state.update("timeout_slow_mode", settings)
    apply_timeout_slow_mode_settings(settings)
    return settings


def initialize_timeout_slow_mode_settings(shared_state):
    return refresh_timeout_slow_mode_settings(shared_state)


def get_timeout_slow_mode_settings_data(shared_state):
    response.content_type = "application/json"
    settings = refresh_timeout_slow_mode_settings(shared_state)
    return {"success": True, "settings": settings}


def save_timeout_slow_mode_settings(shared_state):
    response.content_type = "application/json"

    data = request.json
    if not isinstance(data, dict):
        return {"success": False, "message": "Invalid JSON payload"}

    provided_settings = data.get("settings")
    if not isinstance(provided_settings, dict):
        provided_settings = {}

    timeout_settings_db = DataBase(TIMEOUT_SLOW_MODE_TABLE)
    current_settings = _read_timeout_slow_mode_settings()

    for timeout_key in TIMEOUT_SLOW_MODE_DEFINITIONS:
        current_value = current_settings.get(timeout_key, False)
        next_value = _coerce_bool(provided_settings.get(timeout_key), current_value)
        timeout_settings_db.update_store(
            timeout_key,
            "true" if next_value else "false",
        )

    settings = refresh_timeout_slow_mode_settings(shared_state)

    return {
        "success": True,
        "message": "Timeout slow mode settings saved successfully",
        "settings": settings,
    }
