# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import os

from quasarr.providers.log import info
from quasarr.providers.notifications._helpers import resolve_poster_url

silent_env = os.getenv("SILENT", "")
silent = bool(silent_env)
silent_max = silent_env.lower() == "max"


def send_notification(
    shared_state, title, case, imdb_id=None, details=None, source=None
):
    """
    Send a notification to all configured providers (Discord, Telegram).

    Each provider is attempted independently — a failure in one does not block others.

    :param shared_state: Shared state object containing configuration.
    :param title: Title of the notification.
    :param case: A string representing the scenario (e.g., 'captcha', 'failed', 'unprotected').
    :param imdb_id: A string starting with "tt" followed by at least 7 digits, representing an object on IMDb
    :param details: A dictionary containing additional details, such as version and link for updates.
    :param source: Optional source of the notification, sent as a field in the embed.
    :return: True if at least one provider sent successfully, False otherwise.
    """
    from quasarr.providers.notifications import discord, telegram

    has_discord = bool(shared_state.values.get("discord"))
    has_telegram = bool(shared_state.values.get("telegram_bot_token")) and bool(
        shared_state.values.get("telegram_chat_id")
    )

    if not has_discord and not has_telegram:
        return False

    # SILENT=MAX blocks all messages except explicit failure cases.
    if silent_max and case not in ["failed", "disabled"]:
        return True

    # Resolve poster image once for all providers.
    image_url = None
    if case in ("unprotected", "captcha"):
        image_url = resolve_poster_url(shared_state, title, imdb_id)

    any_success = False

    if has_discord:
        try:
            if discord.send(
                shared_state,
                title,
                case,
                details=details,
                source=source,
                image_url=image_url,
            ):
                any_success = True
        except Exception as e:
            info(f"Discord notification error: {e}")

    if has_telegram:
        try:
            if telegram.send(
                shared_state,
                title,
                case,
                details=details,
                source=source,
                image_url=image_url,
            ):
                any_success = True
        except Exception as e:
            info(f"Telegram notification error: {e}")

    return any_success
