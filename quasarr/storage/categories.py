# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import json
import re

import emoji

from quasarr.constants import (
    DOWNLOAD_CATEGORIES,
    SEARCH_CAT_BOOKS,
    SEARCH_CAT_MOVIES,
    SEARCH_CAT_MUSIC,
    SEARCH_CAT_SHOWS,
    SEARCH_CATEGORIES,
)

from ..providers.log import debug, info
from .sqlite_database import DataBase


def get_download_categories():
    """Returns a sorted list of all category names, ensuring defaults exist."""
    db = DataBase("categories_download")

    # Ensure default categories always exist
    for cat, cat_info in DOWNLOAD_CATEGORIES.items():
        if not db.retrieve(cat):
            # Store default emoji in the value JSON
            emj = cat_info.get("emoji", "📁")
            db.store(cat, json.dumps({"emoji": emj}))
            info(f"Restored default category: {cat}")

    cats = db.retrieve_all_titles() or []
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
    return DOWNLOAD_CATEGORIES.get(name, {}).get("emoji", "📁")


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


def get_search_categories():
    """Returns a dictionary of all search categories (default + custom)."""
    db = DataBase("categories_search")

    # Ensure default categories always exist in DB (for whitelists)
    for cat_id, cat_info in SEARCH_CATEGORIES.items():
        if not db.retrieve(cat_id):
            db.store(cat_id, json.dumps(cat_info))
            info(f"Restored default search category: {cat_id} ({cat_info['name']})")

    # Start with default categories
    categories = SEARCH_CATEGORIES.copy()

    # Add custom categories from DB
    custom_cats = db.retrieve_all_titles() or []
    for cat_id_tuple in custom_cats:
        cat_id = cat_id_tuple[0]
        data_str = db.retrieve(cat_id)
        if data_str:
            try:
                data = json.loads(data_str)
                # Only include if it has required fields
                if "name" in data and "emoji" in data:
                    categories[cat_id] = data
            except json.JSONDecodeError:
                pass

    return categories


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

    db = DataBase("categories_search")
    data_str = db.retrieve(str(cat_id))
    if not data_str:
        return False, f"Search category ID {cat_id} not found."

    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        return False, f"Database error for category id {cat_id}."

    data["search_sources"] = sources
    db.update_store(str(cat_id), json.dumps(data))

    info(f"Updated search-source-whitelist for search category {cat_id} to {sources}")
    return (
        True,
        f"Search category {cat_id} search-source-whitelist updated successfully.",
    )


def add_custom_search_category(base_type):
    """Adds a new custom search category based on a base type."""
    base_type_map = {
        "movies": SEARCH_CAT_MOVIES,
        "music": SEARCH_CAT_MUSIC,
        "tv": SEARCH_CAT_SHOWS,
        "books": SEARCH_CAT_BOOKS,
    }

    if base_type not in base_type_map:
        return False, "Invalid base category type."

    base_cat_id = base_type_map[base_type]
    base_cat_info = SEARCH_CATEGORIES[str(base_cat_id)]

    db = DataBase("categories_search")
    all_cats = db.retrieve_all_titles() or []

    # Base IDs: Movies=2000, Music=3000, TV=5000, Books=7000
    # Custom IDs: 102000, 103000, 105000, 107000

    start_id = 100000 + base_cat_id

    # Find next available ID
    existing_ids = [int(c[0]) for c in all_cats if c[0].isdigit()]

    # Count total custom categories
    custom_count = 0
    for eid in existing_ids:
        if eid >= 100000:
            custom_count += 1

    if custom_count >= 10:
        return False, "Limit of 10 custom search categories reached."

    # Find next available slot for this specific base type
    next_id = start_id
    while next_id in existing_ids:
        next_id += 10

    # Let's count how many custom categories of this base type exist
    type_count = 0
    for eid in existing_ids:
        if eid >= start_id and eid < start_id + 10000:  # Assuming range won't overlap
            type_count += 1

    name = f"Custom {base_cat_info['name']} {type_count + 1}"

    data = {
        "name": name,
        "emoji": base_cat_info["emoji"],
        "base_type": base_type,
        "search_sources": [],
    }

    db.store(str(next_id), json.dumps(data))
    info(f"Added custom search category: {name} ({next_id})")
    return True, f"Custom category '{name}' added successfully."


def delete_search_category(cat_id):
    """Deletes a custom search category."""
    if str(cat_id) in SEARCH_CATEGORIES:
        return False, "Cannot delete default search categories."

    db = DataBase("categories_search")
    if not db.retrieve(str(cat_id)):
        return False, f"Category {cat_id} not found."

    db.delete(str(cat_id))
    info(f"Deleted search category: {cat_id}")
    return True, f"Search category {cat_id} deleted successfully."


def search_category_exists(cat_id):
    """Checks if a search category exists."""
    if not cat_id:
        return False

    cat_id = str(cat_id)
    if cat_id in SEARCH_CATEGORIES:
        return True

    db = DataBase("categories_search")
    return db.retrieve(cat_id) is not None


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

    all_cats = db.retrieve_all_titles() or []
    custom_count = len([c[0] for c in all_cats if c[0] not in DOWNLOAD_CATEGORIES])
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
        data = {"emoji": DOWNLOAD_CATEGORIES.get(name, {}).get("emoji", "📁")}

    data["mirrors"] = mirrors
    db.update_store(name, json.dumps(data))
    info(f"Updated mirror-whitelist for category: {name} to {mirrors}")
    return True, f"Category '{name}' mirror-whitelist updated successfully."


def delete_download_category(name):
    """Deletes a category."""
    name = name.strip().lower()

    if name in DOWNLOAD_CATEGORIES:
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
