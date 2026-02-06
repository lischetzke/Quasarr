# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import json
import re

import emoji

from ..providers.log import debug, info
from .sqlite_database import DataBase

DEFAULT_DOWNLOAD_CATEGORIES = ["movies", "tv", "docs"]
DEFAULT_DOWNLOAD_CATEGORY_EMOJIS = {"movies": "🎬", "tv": "📺", "docs": "📄"}

SEARCH_CATEGORIES = {
    "2000": {"name": "Movies", "emoji": "🎬"},
    "5000": {"name": "TV", "emoji": "📺"},
    "7000": {"name": "Books", "emoji": "📚"},
}

# As of 01.02.2026
COMMON_HOSTERS = [
    # --- TIER 1: The Standards (Required for most downloaders) ---
    "Rapidgator",  # Global King. Most files are here.
    "DDownload",  # The "Euro Standard". Cheaper alternative to RG.
    # --- TIER 2: Very Popular / High Retention ---
    "1fichier",  # Massive retention, cheap, very popular in France/Global.
    "Keep2Share",  # "Premium" tier. High speeds, expensive, very stable.
    "Nitroflare",  # Old guard. Expensive, but essential for some exclusive content.
    # --- TIER 3: Common Mirrors (The "Third Link") ---
    "Turbobit",  # Everywhere, but often disliked by free users.
    "Hitfile",  # Turbobit's sibling site. Often seen together.
    "Katfile",  # Very common secondary mirror for smaller uploaders.
    "Alfafile",  # Stable mid-tier host, often seen on DDL blogs.
    # --- TIER 4: Niche / Backup / User Requested ---
    "Filer",  # Strong in German-speaking areas, niche elsewhere.
    "IronFiles",  # Active. Smaller ecosystem, often specific to certain boards.
    "Fikper",  # Newer player (relative to RG), gained traction in 2024-25.
    "Mega",  # Active, but functions differently (cloud drive vs. OCH).
]

TIER_1_HOSTERS = ["Rapidgator", "DDownload"]

SEARCH_SOURCES = [
    "al",
    "by",
    "dd",
    "dl",
    "dt",
    "dj",
    "dw",
    "fx",
    "he",
    "hs",
    "mb",
    "nk",
    "nx",
    "sf",
    "sj",
    "sl",
    "wd",
    "wx",
]


def get_download_categories():
    """Returns a sorted list of all category names, ensuring defaults exist."""
    db = DataBase("categories_download")

    # Ensure default categories always exist
    for cat in DEFAULT_DOWNLOAD_CATEGORIES:
        if not db.retrieve(cat):
            # Store default emoji in the value JSON
            emoji = DEFAULT_DOWNLOAD_CATEGORY_EMOJIS.get(cat, "📁")
            db.store(cat, json.dumps({"emoji": emoji}))
            info(f"Restored default category: {cat}")

    cats = db.retrieve_all_titles()
    return sorted([c[0] for c in cats])


def get_download_category_emoji(name):
    """Returns the emoji for a category."""
    db = DataBase("categories_download")
    data_str = db.retrieve(name)
    if data_str:
        try:
            data = json.loads(data_str)
            return data.get("emoji", "📁")
        except json.JSONDecodeError:
            pass

    # Fallback for defaults if DB is somehow corrupted or old format
    return DEFAULT_DOWNLOAD_CATEGORY_EMOJIS.get(name, "📁")


def get_download_category_mirrors(name, lowercase=False):
    """Returns the list of preferred mirrors for a category."""
    db = DataBase("categories_download")
    data_str = db.retrieve(name)
    if data_str:
        try:
            data = json.loads(data_str)
            mirrors = data.get("mirrors", [])
            if lowercase:
                return [m.lower() for m in mirrors]
            return mirrors
        except json.JSONDecodeError:
            pass
    return []


def get_search_category_sources(cat_id):
    """Returns the list of preferred search sources for a search category ID."""
    db = DataBase("categories_search")
    data_str = db.retrieve(str(cat_id))
    if data_str:
        try:
            data = json.loads(data_str)
            return data.get("search_sources", [])
        except json.JSONDecodeError:
            pass
    return []


def update_search_category_sources(cat_id, sources):
    """Updates the preferred search sources for a search category ID."""
    if str(cat_id) not in SEARCH_CATEGORIES:
        return False, f"Invalid search category ID: {cat_id}"

    db = DataBase("categories_search")
    data = {"search_sources": sources}

    db.update_store(str(cat_id), json.dumps(data))

    info(f"Updated search-source-whitelist for search category {cat_id} to {sources}")
    return (
        True,
        f"Search category {cat_id} search-source-whitelist updated successfully.",
    )


def add_download_category(name, emj="📁"):
    """Adds a new category."""
    if not name or not name.strip():
        return False, "Category name cannot be empty."

    name = name.strip().lower()

    if len(name) > 20:
        return False, "Category name must be 20 characters or less."

    if not re.match("^[a-z0-9]+$", name):
        return (
            False,
            "Category name can only contain lowercase letters and numbers.",
        )

    if not emj or not emoji.is_emoji(emj):
        debug(f"Invalid emoji: {emj}, falling back to default '📁'")
        emj = "📁"

    db = DataBase("categories_download")
    if db.retrieve(name):
        return False, f"Category '{name}' already exists."

    all_cats = db.retrieve_all_titles()
    custom_count = len(
        [c[0] for c in all_cats if c[0] not in DEFAULT_DOWNLOAD_CATEGORIES]
    )
    if custom_count >= 10:
        return False, "Limit of 10 custom categories reached."

    db.store(name, json.dumps({"emoji": emj}))
    info(f"Added category: {name} with emoji {emj}")
    return True, f"Category '{name}' added successfully."


def update_download_category_emoji(name, emj):
    """Updates the emoji for an existing category."""
    name = name.strip().lower()
    db = DataBase("categories_download")

    if not db.retrieve(name):
        return False, f"Category '{name}' not found."

    if not emj or not emoji.is_emoji(emj):
        debug(f"Invalid emoji: {emj}, falling back to default '📁'")
        emj = "📁"

    # Retrieve existing data to preserve mirrors
    data_str = db.retrieve(name)
    data = {}
    if data_str:
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            pass

    data["emoji"] = emj

    db.update_store(name, json.dumps(data))
    info(f"Updated emoji for category: {name} to {emj}")
    return True, f"Category '{name}' emoji updated successfully."


def update_download_category_mirrors(name, mirrors):
    """Updates the preferred mirrors for a category."""
    name = name.strip().lower()
    db = DataBase("categories_download")

    data_str = db.retrieve(name)
    if not data_str:
        return False, f"Category '{name}' not found."

    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        data = {"emoji": DEFAULT_DOWNLOAD_CATEGORY_EMOJIS.get(name, "📁")}

    data["mirrors"] = mirrors
    db.update_store(name, json.dumps(data))
    info(f"Updated mirror-whitelist for category: {name} to {mirrors}")
    return True, f"Category '{name}' mirror-whitelist updated successfully."


def delete_download_category(name):
    """Deletes a category."""
    name = name.strip().lower()

    if name in DEFAULT_DOWNLOAD_CATEGORIES:
        return False, f"Cannot delete default category '{name}'."

    db = DataBase("categories_download")
    all_categories = db.retrieve_all_titles()

    if not all_categories or len(all_categories) <= 1:
        return False, "Cannot delete the last category."

    if not db.retrieve(name):
        return False, f"Category '{name}' not found."

    db.delete(name)
    info(f"Deleted category: {name}")
    return True, f"Category '{name}' deleted successfully."


def init_default_download_categories():
    """Initializes the database with default categories if they don't exist."""
    # This is now handled in get_categories to ensure they persist
    get_download_categories()


def download_category_exists(name):
    """Checks if a category exists."""
    if not name:
        return False
    db = DataBase("categories_download")
    return db.retrieve(name.lower()) is not None


def get_download_category_from_package_id(package_id):
    """Extract category from a Quasarr package ID."""
    if not package_id:
        return "not_quasarr"

    # Check all dynamic categories
    categories = get_download_categories()
    for cat in categories:
        # Check if the category name is part of the package ID
        # The package ID format is Quasarr_{category}_{hash}
        # So we look for Quasarr_{cat}_
        if f"Quasarr_{cat}_" in package_id:
            return cat
    return "not_quasarr"
