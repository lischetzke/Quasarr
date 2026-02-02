# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re
import time
import warnings
from base64 import urlsafe_b64encode
from datetime import datetime

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from quasarr.providers.hostname_issues import clear_hostname_issue, mark_hostname_issue

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
from quasarr.providers.log import debug, warn

hostname = "hs"
supported_mirrors = ["rapidgator", "ddownload", "katfile"]

FILECRYPT_REGEX = re.compile(r"filecrypt\.(?:cc|co|to)/container/", re.I)
SIZE_REGEX = re.compile(r"Größe[:\s]*(\d+(?:[.,]\d+)?)\s*(MB|GB|TB)", re.I)
IMDB_REGEX = re.compile(r"imdb\.com/title/(tt\d+)", re.I)
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


def convert_to_rss_date(date_str):
    """
    HS date format from search: 'dd.mm.yy, HH:MM' e.g. '05.07.25, 17:23'
    """
    match = DATE_REGEX.search(date_str)
    if match:
        date_part = match.group(1)
        time_part = match.group(2)
        dt_obj = datetime.strptime(f"{date_part} {time_part}", "%d.%m.%y %H:%M")
        return dt_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
    return ""


def convert_rss_pubdate(pubdate_str):
    """
    RSS feed pubDate format: 'Mon, 26 Jan 2026 18:53:59 +0000'
    """
    try:
        # Already in RSS format, just clean it up
        dt_obj = datetime.strptime(pubdate_str.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
    except Exception:
        return pubdate_str


def extract_size_from_text(text):
    """Extract size in MB from text like 'Größe: 40883 MB'"""
    match = SIZE_REGEX.search(text)
    if match:
        size_val = float(match.group(1).replace(",", "."))
        unit = match.group(2).upper()
        if unit == "GB":
            return int(size_val * 1024)
        elif unit == "TB":
            return int(size_val * 1024 * 1024)
        return int(size_val)
    return 0


def extract_episode_size_mb(text):
    """
    Calculate episode size from average bitrate and per-episode duration.

    Returns size in MB if both bitrate and per-episode duration are found,
    otherwise returns None (caller should use total size).

    Formula: size_mb = bitrate_mbps * duration_min * 60 / 8
    """
    # Check if this is per-episode duration (contains "pro Folge")
    duration_match = EPISODE_DURATION_REGEX.search(text)
    if not duration_match:
        return None

    duration_min = int(duration_match.group(1))

    # Extract bitrate
    bitrate_match = BITRATE_REGEX.search(text)
    if not bitrate_match:
        return None

    # Parse bitrate value - handle various formats:
    # - "6 040" (space as thousand separator)
    # - "84,284" (comma as thousand separator - 3 digits after comma)
    # - "20,8" or "10,6" (comma as decimal separator - not 3 digits after comma)
    bitrate_str = bitrate_match.group(1).strip()

    # Remove spaces (thousand separator)
    bitrate_str = bitrate_str.replace(" ", "")

    # Handle comma: thousand separator if exactly 3 digits follow, otherwise decimal
    if "," in bitrate_str:
        parts = bitrate_str.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            # Comma is thousand separator (e.g., "84,284" -> "84284")
            bitrate_str = bitrate_str.replace(",", "")
        else:
            # Comma is decimal separator (e.g., "20,8" -> "20.8")
            bitrate_str = bitrate_str.replace(",", ".")

    bitrate_val = float(bitrate_str)
    bitrate_unit = bitrate_match.group(2).lower()

    # Convert to Mb/s
    if bitrate_unit == "kb/s":
        bitrate_mbps = bitrate_val / 1000
    else:  # mb/s
        bitrate_mbps = bitrate_val

    # Calculate size: bitrate (Mb/s) * duration (s) / 8 = MB
    episode_size_mb = int(bitrate_mbps * duration_min * 60 / 8)
    return episode_size_mb


def normalize_mirror_name(name):
    """Normalize mirror names - ddlto/ddl.to -> ddownload"""
    name_lower = name.lower().strip()
    if "ddlto" in name_lower or "ddl.to" in name_lower or "ddownload" in name_lower:
        return "ddownload"
    if "rapidgator" in name_lower:
        return "rapidgator"
    if "katfile" in name_lower:
        return "katfile"
    return name_lower


def build_search_url(base_url, search_term):
    """Build the ASP search URL with all required parameters"""
    params = {
        "s": search_term,
        "asp_active": "1",
        "p_asid": "1",
        "p_asp_data": "1",
        "current_page_id": "162309",
        "qtranslate_lang": "0",
        "filters_changed": "0",
        "filters_initial": "1",
        "asp_gen[]": ["title", "content", "excerpt"],
        "customset[]": "post",
        "termset[category][]": ["10", "13", "14", "15"],
        "termset[formate][]": [
            "41",
            "42",
            "43",
            "44",
            "45",
            "46",
            "47",
            "48",
            "49",
            "50",
            "51",
            "52",
            "53",
            "54",
            "55",
        ],
    }

    # Build URL manually to handle multiple values for same key
    parts = []
    for key, value in params.items():
        if isinstance(value, list):
            for v in value:
                parts.append(f"{key}={v}")
        else:
            parts.append(f"{key}={value}")

    return f"{base_url}/?{'&'.join(parts)}"


def _parse_search_results(
    soup,
    shared_state,
    hd_host,
    password,
    mirror_filter,
    request_from,
    search_string,
    season,
    episode,
):
    """Parse search results page and extract releases with filecrypt links.

    Also extracts individual episode titles from season packs when available.
    For episodes, calculates size from bitrate × duration instead of using total pack size.
    """
    releases = []

    # Find all result entries - they appear as sections with date/title headers
    # Pattern: "dd.mm.yy, HH:MM · [Title](url)"
    for article in soup.find_all(
        ["article", "div"],
        class_=lambda x: x and ("post" in str(x).lower() or "result" in str(x).lower()),
    ):
        try:
            # Find the title link
            title_link = article.find(
                "a",
                href=lambda h: h
                and hd_host in h
                and ("/filme/" in h or "/serien/" in h),
            )
            if not title_link:
                continue

            main_title = title_link.get_text(strip=True)
            if not main_title or len(main_title) < 5:
                continue

            # Replace spaces with dots for release name format
            main_title = main_title.replace(" ", ".")

            source = title_link["href"]

            # Extract size from article content
            article_text = article.get_text()
            total_mb = extract_size_from_text(article_text)
            total_size_bytes = int(total_mb * 1024 * 1024) if total_mb else 0

            # Calculate episode size from bitrate and duration (if available)
            episode_mb = extract_episode_size_mb(article_text)
            episode_size_bytes = int(episode_mb * 1024 * 1024) if episode_mb else None

            # Extract date
            published = convert_to_rss_date(article_text)

            # Extract IMDb ID if present
            imdb_match = IMDB_REGEX.search(str(article))
            imdb_id = imdb_match.group(1) if imdb_match else None

            # Collect all titles to create releases for (episodes first, main title last)
            episode_titles = []

            # Extract individual episode titles from article content
            # Episodes may appear on separate lines or concatenated without separators
            # Use findall to get all matches, then clean up any trailing garbage
            for ep_match in EPISODE_EXTRACT_REGEX.findall(article_text):
                ep_title = ep_match.strip()
                # Clean trailing common words that may be attached to group name
                # e.g., "Title.S02E01-WAYNEAvg" -> "Title.S02E01-WAYNE"
                ep_title = TRAILING_GARBAGE_PATTERN.sub("", ep_title)
                if ep_title and len(ep_title) > 10:
                    episode_titles.append(ep_title)

            # Remove duplicate episodes while preserving order
            seen = set()
            unique_episodes = []
            for t in episode_titles:
                t_lower = t.lower()
                if t_lower not in seen:
                    seen.add(t_lower)
                    unique_episodes.append(t)

            # Create releases for individual episodes (use calculated episode size)
            for title in unique_episodes:
                # Validate release against search criteria
                if not shared_state.is_valid_release(
                    title, request_from, search_string, season, episode
                ):
                    continue

                # Use calculated episode size if available, otherwise fall back to total
                ep_mb = episode_mb if episode_mb else total_mb
                ep_size = episode_size_bytes if episode_size_bytes else total_size_bytes

                payload = urlsafe_b64encode(
                    f"{title}|{source}|{mirror_filter}|{ep_mb}|{password}|{imdb_id}|{hostname}".encode()
                ).decode()
                link = f"{shared_state.values['internal_address']}/download/?payload={payload}"

                releases.append(
                    {
                        "details": {
                            "title": title,
                            "hostname": hostname,
                            "imdb_id": imdb_id,
                            "link": link,
                            "mirror": mirror_filter,
                            "size": ep_size,
                            "date": published,
                            "source": source,
                        },
                        "type": "protected",
                    }
                )

            # Also add the main title (season pack) with full size - if not duplicate
            if main_title.lower() not in seen:
                if shared_state.is_valid_release(
                    main_title, request_from, search_string, season, episode
                ):
                    payload = urlsafe_b64encode(
                        f"{main_title}|{source}|{mirror_filter}|{total_mb}|{password}|{imdb_id}|{hostname}".encode()
                    ).decode()
                    link = f"{shared_state.values['internal_address']}/download/?payload={payload}"

                    releases.append(
                        {
                            "details": {
                                "title": main_title,
                                "hostname": hostname,
                                "imdb_id": imdb_id,
                                "link": link,
                                "mirror": mirror_filter,
                                "size": total_size_bytes,
                                "date": published,
                                "source": source,
                            },
                            "type": "protected",
                        }
                    )

        except Exception as e:
            debug(f"Error parsing {hostname.upper()} search result: {e}")
            continue

    return releases


def hs_feed(shared_state, start_time, request_from, mirror=None):
    """Return recent releases from HS feed"""
    releases = []
    hs = shared_state.values["config"]("Hostnames").get(hostname)
    password = hs

    if not hs:
        return releases

    # HS only supports movies and series
    if "lazylibrarian" in request_from.lower():
        debug(
            f'<d>Skipping {request_from} feed on "{hostname.upper()}" (unsupported media type)!</d>'
        )
        return releases

    if mirror and mirror.lower() not in supported_mirrors:
        debug(
            f'Mirror "{mirror}" not supported by "{hostname.upper()}". Skipping feed!'
        )
        return releases

    base_url = f"https://{hs}"
    feed_url = f"{base_url}/feed/"
    headers = {"User-Agent": shared_state.values["user_agent"]}

    try:
        r = requests.get(feed_url, headers=headers, timeout=30)
        r.raise_for_status()

        # Parse RSS - use html.parser to avoid lxml dependency
        soup = BeautifulSoup(r.content, "html.parser")
        items = soup.find_all("item")

        for item in items:
            try:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pubdate_elem = item.find("pubdate")  # html.parser lowercases tags

                if not title_elem or not link_elem:
                    continue

                title = title_elem.get_text(strip=True)
                # html.parser treats <link> as void element, URL is in next_sibling
                source = link_elem.get_text(strip=True)
                if not source and link_elem.next_sibling:
                    source = link_elem.next_sibling.strip()

                if not source:
                    continue

                # Replace spaces with dots (titles may already have dots)
                title = title.replace(" ", ".")

                published = ""
                if pubdate_elem:
                    published = convert_rss_pubdate(pubdate_elem.get_text(strip=True))

                # Feed doesn't include size, set to 0
                mb = 0
                size_bytes = 0
                imdb_id = None

                payload = urlsafe_b64encode(
                    f"{title}|{source}|{mirror}|{mb}|{password}|{imdb_id}|{hostname}".encode()
                ).decode()
                link = f"{shared_state.values['internal_address']}/download/?payload={payload}"

                releases.append(
                    {
                        "details": {
                            "title": title,
                            "hostname": hostname,
                            "imdb_id": imdb_id,
                            "link": link,
                            "mirror": mirror,
                            "size": size_bytes,
                            "date": published,
                            "source": source,
                        },
                        "type": "protected",
                    }
                )

            except Exception as e:
                debug(f"Error parsing {hostname.upper()} feed item: {e}")
                continue

    except Exception as e:
        warn(f"Error loading {hostname.upper()} feed: {e}")
        mark_hostname_issue(hostname, "feed", str(e))
        return releases

    elapsed_time = time.time() - start_time
    debug(f"Time taken: {elapsed_time:.2f}s")

    if releases:
        clear_hostname_issue(hostname)
    return releases


def hs_search(
    shared_state,
    start_time,
    request_from,
    search_string,
    mirror=None,
    season=None,
    episode=None,
):
    """Search HS for releases by IMDb ID"""
    releases = []
    hs = shared_state.values["config"]("Hostnames").get(hostname)
    password = hs

    if not hs:
        return releases

    # HS only supports movies and series
    if "lazylibrarian" in request_from.lower():
        debug(
            f'<d>Skipping {request_from} search on "{hostname.upper()}" (unsupported media type)!</d>'
        )
        return releases

    if mirror and mirror.lower() not in supported_mirrors:
        debug(
            f'Mirror "{mirror}" not supported by "{hostname.upper()}". Skipping search!'
        )
        return releases

    # HS supports direct IMDb ID search
    imdb_id = shared_state.is_imdb_id(search_string)
    if not imdb_id:
        debug(
            f'"{hostname.upper()}" only supports IMDb ID search, got: {search_string}'
        )
        return releases

    base_url = f"https://{hs}"
    search_url = build_search_url(base_url, imdb_id)
    headers = {"User-Agent": shared_state.values["user_agent"]}

    try:
        r = requests.get(search_url, headers=headers, timeout=30)
        r.raise_for_status()

        soup = BeautifulSoup(r.content, "html.parser")
        releases = _parse_search_results(
            soup,
            shared_state,
            hs,
            password,
            mirror,
            request_from,
            search_string,
            season,
            episode,
        )

    except Exception as e:
        warn(f"Error loading {hostname.upper()} search: {e}")
        mark_hostname_issue(hostname, "search", str(e))
        return releases

    elapsed_time = time.time() - start_time
    debug(f"Time taken: {elapsed_time:.2f}s")

    if releases:
        clear_hostname_issue(hostname)
    return releases
