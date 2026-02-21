# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re

# ==============================================================================
# CRITICAL CONFIGURATION
# ==============================================================================

# User agent for all requests, if not overwritten by Flaresolverr
FALLBACK_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"


# ==============================================================================
# SEARCH AND DOWNLOAD CATEGORIES
# ==============================================================================

# Search category source of truth
SEARCH_CATEGORY_DEFINITIONS = {
    "MOVIES": {"id": 2000, "name": "Movies", "emoji": "🎬"},
    "MOVIES_HD": {"id": 2040, "name": "Movies/HD", "emoji": "🎬"},
    "MOVIES_4K": {"id": 2045, "name": "Movies/4K", "emoji": "🎬"},
    "MUSIC": {"id": 3000, "name": "Audio", "emoji": "🎵"},
    "MUSIC_MP3": {"id": 3010, "name": "Audio/MP3", "emoji": "🎵"},
    "MUSIC_FLAC": {"id": 3040, "name": "Audio/FLAC", "emoji": "🎵"},
    "SHOWS": {"id": 5000, "name": "TV", "emoji": "📺"},
    "SHOWS_HD": {"id": 5040, "name": "TV/HD", "emoji": "📺"},
    "SHOWS_4K": {"id": 5045, "name": "TV/4K", "emoji": "📺"},
    "SHOWS_ANIME": {"id": 5070, "name": "Anime", "emoji": "⛩️"},
    "XXX": {"id": 6000, "name": "XXX", "emoji": "🔞"},
    "BOOKS": {"id": 7000, "name": "Books", "emoji": "📚"},
}

# Importable constants for search categories are generated from the source of truth above to ensure consistency and maintainability.
SEARCH_CAT_MOVIES = SEARCH_CATEGORY_DEFINITIONS["MOVIES"]["id"]
SEARCH_CAT_MOVIES_HD = SEARCH_CATEGORY_DEFINITIONS["MOVIES_HD"]["id"]
SEARCH_CAT_MOVIES_4K = SEARCH_CATEGORY_DEFINITIONS["MOVIES_4K"]["id"]
SEARCH_CAT_MUSIC = SEARCH_CATEGORY_DEFINITIONS["MUSIC"]["id"]
SEARCH_CAT_MUSIC_MP3 = SEARCH_CATEGORY_DEFINITIONS["MUSIC_MP3"]["id"]
SEARCH_CAT_MUSIC_FLAC = SEARCH_CATEGORY_DEFINITIONS["MUSIC_FLAC"]["id"]
SEARCH_CAT_SHOWS = SEARCH_CATEGORY_DEFINITIONS["SHOWS"]["id"]
SEARCH_CAT_SHOWS_HD = SEARCH_CATEGORY_DEFINITIONS["SHOWS_HD"]["id"]
SEARCH_CAT_SHOWS_4K = SEARCH_CATEGORY_DEFINITIONS["SHOWS_4K"]["id"]
SEARCH_CAT_SHOWS_ANIME = SEARCH_CATEGORY_DEFINITIONS["SHOWS_ANIME"]["id"]
SEARCH_CAT_XXX = SEARCH_CATEGORY_DEFINITIONS["XXX"]["id"]
SEARCH_CAT_BOOKS = SEARCH_CATEGORY_DEFINITIONS["BOOKS"]["id"]

SEARCH_CATEGORIES = {
    definition["id"]: {"name": definition["name"], "emoji": definition["emoji"]}
    for definition in SEARCH_CATEGORY_DEFINITIONS.values()
}

# Default Set of Download Categories
DOWNLOAD_CATEGORIES = {
    "movies": {"emoji": "🎬"},
    "music": {"emoji": "🎵"},
    "tv": {"emoji": "📺"},
    "docs": {"emoji": "📄"},
}

# ==============================================================================
# HOSTERS & MIRRORS
# ==============================================================================

# As of 01.02.2026
# Format: (Name, is_tier1)
HOSTERS = [
    # --- TIER 1: The Standards (Required for most downloaders) ---
    ("Rapidgator", True),  # Global King. Most files are here.
    ("DDownload", True),  # The "Euro Standard". Cheaper alternative to RG.
    # --- TIER 2: Very Popular / High Retention ---
    ("1fichier", False),  # Massive retention, cheap, very popular in France/Global.
    ("Keep2Share", False),  # "Premium" tier. High speeds, expensive, very stable.
    (
        "Nitroflare",
        False,
    ),  # Old guard. Expensive, but essential for some exclusive content.
    # --- TIER 3: Common Mirrors (The "Third Link") ---
    ("Turbobit", False),  # Everywhere, but often disliked by free users.
    ("Hitfile", False),  # Turbobit's sibling site. Often seen together.
    ("Katfile", False),  # Very common secondary mirror for smaller uploaders.
    ("Alfafile", False),  # Stable mid-tier host, often seen on DDL blogs.
    # --- TIER 4: Niche / Backup / User Requested ---
    ("Filer", False),  # Strong in German-speaking areas, niche elsewhere.
    (
        "IronFiles",
        False,
    ),  # Active. Smaller ecosystem, often specific to certain boards.
    ("Fikper", False),  # Newer player (relative to RG), gained traction in 2024-25.
    ("Mega", False),  # Active, but functions differently (cloud drive vs. OCH).
    ("frdl", False),  # Rarely used in some forums
]

# Used to identify share hosters (lowercase for comparison)
SHARE_HOSTERS_LOWERCASE = {h[0].lower() for h in HOSTERS}
SHARE_HOSTERS = [h[0] for h in HOSTERS]

# Recommend only these
RECOMMENDED_HOSTERS = [h[0] for h in HOSTERS if h[1]]

# Common TLDs to strip for mirror name comparison
COMMON_TLDS = {
    ".com",
    ".net",
    ".io",
    ".cc",
    ".to",
    ".me",
    ".org",
    ".co",
    ".de",
    ".eu",
    ".info",
}


# ==============================================================================
# REGEX PATTERNS (CONTENT & PARSING)
# ==============================================================================

# Used to identify release tittles with season or Episode numbers
SEASON_EP_REGEX = re.compile(
    r"(?i)(?:S\d{1,3}(?:E\d{1,3}(?:-\d{1,3})?)?|S\d{1,3}-\d{1,3})"
)

# Used to identify movies
MOVIE_REGEX = re.compile(
    r"^(?!.*(?:S\d{1,3}(?:E\d{1,3}(?:-\d{1,3})?)?|S\d{1,3}-\d{1,3})).*$", re.IGNORECASE
)

# Domain checks
AFFILIATE_REGEX = re.compile(r"af\.php\?v=([a-zA-Z0-9]+)")
FILECRYPT_REGEX = re.compile(
    r"https?://(?:www\.)?filecrypt\.(?:cc|co|to)/[Cc]ontainer/[A-Za-z0-9]+", re.I
)
IMDB_REGEX = re.compile(r"imdb\.com/title/(tt\d+)", re.I)

# Release Title Checks
RESOLUTION_REGEX = re.compile(r"\d{3,4}p", re.I)
CODEC_REGEX = re.compile(r"x264|x265|h264|h265|hevc|avc", re.I)
XXX_REGEX = re.compile(r"\.xxx\.", re.I)

SIZE_REGEX = re.compile(r"Größe[:\s]*(\d+(?:[.,]\d+)?)\s*(MB|GB|TB)", re.I)

DATE_REGEX = re.compile(r"(\d{2}\.\d{2}\.\d{2}),?\s*(\d{1,2}:\d{2})")

# Pattern to extract individual episode release names from text
# Matches: Title.S02E03.Info-GROUP (group name starts after hyphen)
EPISODE_EXTRACT_REGEX = re.compile(
    r"([A-Za-z][A-Za-z0-9.]+\.S\d{2}E\d{2}[A-Za-z0-9.]*-[A-Za-z][A-Za-z0-9]*)", re.I
)

# Pattern to clean trailing common words that may be attached to group names
# e.g., -WAYNEAvg -> -WAYNE, -GROUPBitrate -> -GROUP
TRAILING_GARBAGE_PATTERN = re.compile(
    r"(Avg|Bitrate|Size|Größe|Video|Audio|Duration|Release|Info).*$", re.I
)

# Pattern to extract average bitrate (e.g., "Avg. Bitrate: 10,6 Mb/s" or "6 040 kb/s")
# Note: Numbers may contain spaces as thousand separators (e.g., "6 040")
BITRATE_REGEX = re.compile(
    r"(?:Avg\.?\s*)?Bitrate[:\s]*([\d\s]+(?:[.,]\d+)?)\s*(kb/s|Mb/s|mb/s)", re.I
)

# Pattern to extract episode duration (e.g., "Dauer: 60 Min. pro Folge")
EPISODE_DURATION_REGEX = re.compile(r"Dauer[:\s]*(\d+)\s*Min\.?\s*pro\s*Folge", re.I)


# ==============================================================================
# DECRYPTION & PROTECTION
# ==============================================================================

# Identifies Linkcrypters that never require CAPTCHA
AUTO_DECRYPT_PATTERNS = {
    "hide": re.compile(r"hide\.", re.IGNORECASE),
}

# Identifies Linkcrypters that may require CAPTCHA
PROTECTED_PATTERNS = {
    "filecrypt": re.compile(r"filecrypt\.", re.IGNORECASE),
    "tolink": re.compile(r"tolink\.", re.IGNORECASE),
    "keeplinks": re.compile(r"keeplinks\.", re.IGNORECASE),
}


# ==============================================================================
# QUASARR PACKAGE MANAGEMENT
# ==============================================================================

# Prefix for all Quasarr Packages
PACKAGE_ID_PREFIX = "Quasarr_"

# Regex for strict Quasarr ID validation: Quasarr_{category}_{32_char_hash}
PACKAGE_ID_PATTERN = re.compile(r"^Quasarr_[a-z]+_[a-f0-9]{32}$")


# ==============================================================================
# JDOWNLOADER / EXTRACTION
# ==============================================================================

# Status Strings from JDownloader (add more languages if needed)
EXTRACTION_COMPLETE_MARKERS = (
    "extraction ok",  # English
    "entpacken ok",  # German
)

# Used during archive detection
ARCHIVE_EXTENSIONS = frozenset(
    [
        ".rar",
        ".zip",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".001",
        ".002",
        ".003",
        ".004",
        ".005",
        ".006",
        ".007",
        ".008",
        ".009",
        ".r00",
        ".r01",
        ".r02",
        ".r03",
        ".r04",
        ".r05",
        ".r06",
        ".r07",
        ".r08",
        ".r09",
        ".part1.rar",
        ".part01.rar",
        ".part001.rar",
        ".part2.rar",
        ".part02.rar",
        ".part002.rar",
    ]
)


# ==============================================================================
# TIME & LOCALIZATION
# ==============================================================================

SESSION_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours

# Source of truth for month names and mappings
# Format: (Month Number, English Name, German Name, [Additional Synonyms])
_MONTHS_CONFIG = [
    (1, "January", "Januar", ["jan"]),
    (2, "February", "Februar", ["feb"]),
    (3, "March", "März", ["maerz", "mär", "mrz", "mae"]),
    (4, "April", "April", ["apr"]),
    (5, "May", "Mai", ["may"]),
    (6, "June", "Juni", ["jun", "june"]),
    (7, "July", "Juli", ["jul", "july"]),
    (8, "August", "August", ["aug"]),
    (9, "September", "September", ["sep"]),
    (10, "October", "Oktober", ["okt", "october"]),
    (11, "November", "November", ["nov"]),
    (12, "December", "Dezember", ["dez", "december"]),
]

ENGLISH_MONTHS = [m[1] for m in _MONTHS_CONFIG]
GERMAN_MONTHS = [m[2] for m in _MONTHS_CONFIG]

MONTHS_MAP = {
    name.lower(): nr
    for nr, en, de, synonyms in _MONTHS_CONFIG
    for name in [en, de] + synonyms
}


# ==============================================================================
# DISCORD / NOTIFICATIONS
# ==============================================================================

# Discord message flag for suppressing notifications
SUPPRESS_NOTIFICATIONS = 1 << 12  # 4096
