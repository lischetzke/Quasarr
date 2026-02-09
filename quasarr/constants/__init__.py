# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re

# ==============================================================================
# CRITICAL CONFIGURATION
# ==============================================================================

# User agent for all requests, if not overwritten by Flaresolverr
FALLBACK_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"

# These are the supported hostnames in Quasarr
HOSTNAMES = [
    "al",
    "by",
    "dd",
    "dj",
    "dl",
    "dt",
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

# These hostnames require credentials to be used
HOSTNAMES_REQUIRING_LOGIN = ["al", "dd", "dj", "dl", "nx", "sj"]

# These hostnames support not only feed and imdb searches, but also search phrases
HOSTNAMES_SUPPORTING_SEARCH_PHRASE = ["by", "dl", "dt", "nx", "sl", "wd"]

# These hostnames have custom download implementation / getter, right now only FX doesn't
HOSTNAMES_WITH_CUSTOM_DOWNLOAD_HANDLER = [h for h in HOSTNAMES if h != "fx"]

# ==============================================================================
# SEARCH & CATEGORIES
# ==============================================================================

# Numeric newznab categories supported by search
SEARCH_CAT_MOVIES = 2000
SEARCH_CAT_MUSIC = 3000
SEARCH_CAT_SHOWS = 5000
SEARCH_CAT_BOOKS = 7000

SEARCH_CATEGORIES = {
    "2000": {"name": "Movies", "emoji": "🎬"},
    "3000": {"name": "Music", "emoji": "🎵"},
    "5000": {"name": "TV", "emoji": "📺"},
    "7000": {"name": "Books", "emoji": "📚"},
}

DEFAULT_DOWNLOAD_CATEGORIES = ["movies", "music", "tv", "docs"]

DEFAULT_DOWNLOAD_CATEGORY_EMOJIS = {
    "movies": "🎬",
    "music": "🎵",
    "tv": "📺",
    "docs": "📄",
}


# ==============================================================================
# HOSTERS & MIRRORS
# ==============================================================================

# Used to identify share hosters
SHARE_HOSTERS = {
    "rapidgator",
    "ddownload",
    "keep2share",
    "1fichier",
    "katfile",
    "filer",
    "turbobit",
    "nitroflare",
    "filefactory",
    "uptobox",
    "mediafire",
    "mega",
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

# Recommend only these
TIER_1_HOSTERS = ["Rapidgator", "DDownload"]

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

GERMAN_MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]

MONTHS_MAP = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "mär": 3,
    "mrz": 3,
    "mae": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "may": 5,
    "juni": 6,
    "jun": 6,
    "june": 6,
    "juli": 7,
    "jul": 7,
    "july": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "oktober": 10,
    "okt": 10,
    "october": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "december": 12,
}

ENGLISH_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


# ==============================================================================
# DISCORD / NOTIFICATIONS
# ==============================================================================

# Discord message flag for suppressing notifications
SUPPRESS_NOTIFICATIONS = 1 << 12  # 4096
