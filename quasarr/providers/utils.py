# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import os
import re
import socket
import sys
from base64 import urlsafe_b64decode, urlsafe_b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image

from quasarr.constants import (
    HOSTNAMES_REQUIRING_LOGIN,
    SEARCH_CAT_BOOKS,
    SEARCH_CAT_MOVIES,
    SEARCH_CAT_SHOWS,
)
from quasarr.providers.log import crit, error, warn
from quasarr.storage.categories import download_category_exists


class Unbuffered(object):
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)


def is_valid_url(url):
    """Validate if a URL is properly formatted."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def extract_allowed_keys(config, section):
    """
    Extracts allowed keys from the specified section in the configuration.

    :param config: The configuration dictionary.
    :param section: The section from which to extract keys.
    :return: A list of allowed keys.
    """
    if section not in config:
        raise ValueError(f"Section '{section}' not found in configuration.")
    return [key for key, *_ in config[section]]


def extract_kv_pairs(input_text, allowed_keys):
    """
    Extracts key-value pairs from the given text where keys match allowed_keys.

    :param input_text: The input text containing key-value pairs.
    :param allowed_keys: A list of allowed two-letter shorthand keys.
    :return: A dictionary of extracted key-value pairs.
    """
    kv_pattern = re.compile(rf"^({'|'.join(map(re.escape, allowed_keys))})\s*=\s*(.*)$")
    kv_pairs = {}
    debug = os.getenv("DEBUG")

    for line in input_text.splitlines():
        match = kv_pattern.match(line.strip())
        if match:
            key, value = match.groups()
            kv_pairs[key] = value
        elif "[Hostnames]" in line:
            pass
        else:
            if debug:
                print(
                    f"Skipping line because it does not contain any supported hostname: {line}"
                )

    return kv_pairs


def check_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 0))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def check_flaresolverr(shared_state, flaresolverr_url):
    # Ensure it ends with /v<digit+>
    if not re.search(r"/v\d+$", flaresolverr_url):
        error(f"FlareSolverr URL does not end with /v#: {flaresolverr_url}")
        return False

    # Try sending a simple test request
    headers = {"Content-Type": "application/json"}
    data = {"cmd": "request.get", "url": "http://www.google.com/", "maxTimeout": 10000}

    try:
        response = requests.post(
            flaresolverr_url, headers=headers, json=data, timeout=10
        )
        response.raise_for_status()
        json_data = response.json()

        # Check if the structure looks like a valid FlareSolverr response
        if "status" in json_data and json_data["status"] == "ok":
            solution = json_data["solution"]
            solution_ua = solution.get("userAgent", None)
            if solution_ua:
                shared_state.update("user_agent", solution_ua)
            try:
                flaresolverr_version = json_data.get("version")
            except Exception as e:
                error(f"Could not grab Flaresolverr version: {str(e)}")
                return False
            return flaresolverr_version
        else:
            error(f"Unexpected FlareSolverr response: {json_data}")
            return False

    except Exception as e:
        error(f"Failed to connect to FlareSolverr: {e}")
        return False


def validate_address(address, name):
    if not address.startswith("http"):
        crit(f"Error: {name} '{address}' is invalid. It must start with 'http'.")
        sys.exit(1)

    colon_count = address.count(":")
    if colon_count < 1 or colon_count > 2:
        crit(
            f"Error: {name} '{address}' is invalid. It must contain 1 or 2 colons, but it has {colon_count}."
        )
        sys.exit(1)


def is_flaresolverr_available(shared_state):
    """
    Check if FlareSolverr is configured and available.

    Returns:
        bool: True if FlareSolverr URL is set and not skipped, False otherwise
    """
    # Check if FlareSolverr was skipped
    if shared_state.values["database"]("skip_flaresolverr").retrieve("skipped"):
        return False

    # Check if FlareSolverr URL is configured
    flaresolverr_url = shared_state.values["config"]("FlareSolverr").get("url")
    if not flaresolverr_url:
        return False

    return True


def is_site_usable(shared_state, shorthand):
    """
    Check if a site is fully configured and usable.

    For sites that don't require login, just checks if hostname is set.
    For login-required sites (al, dd, dl, nx), also checks that login wasn't skipped
    and that credentials exist.

    Args:
        shared_state: Shared state object
        shorthand: Site shorthand (e.g., 'al', 'dd', etc.)

    Returns:
        bool: True if site is usable, False otherwise
    """
    shorthand = shorthand.lower()

    # Check if hostname is set
    hostname = shared_state.values["config"]("Hostnames").get(shorthand)
    if not hostname:
        return False

    if shorthand not in HOSTNAMES_REQUIRING_LOGIN:
        return True  # No login needed, hostname is enough

    # Check if login was skipped
    if shared_state.values["database"]("skip_login").retrieve(shorthand):
        return False  # Hostname set but login was skipped

    # Check for credentials
    section = "JUNKIES" if shorthand in ["dj", "sj"] else shorthand.upper()
    config = shared_state.values["config"](section)
    user = config.get("user")
    password = config.get("password")

    return bool(user and password)


def generate_download_link(
    shared_state, title, url, size_mb, password, imdb_id, source_key
):
    """
    Generate a download link with a base64 encoded payload.
    The payload format is: title|url|size_mb|password|imdb_id|source_key

    Args:
        shared_state: Shared state object
        title: Release title
        url: Source URL
        size_mb: Size in MB (int or float)
        password: Password for the release (or empty string)
        imdb_id: IMDb ID (or None/empty string)
        source_key: Source shorthand (e.g., 'al', 'dd')

    Returns:
        str: Full download URL
    """
    # Ensure all fields are strings and handle None
    title = str(title) if title else ""
    url = str(url) if url else ""
    size_mb = str(size_mb) if size_mb is not None else "0"
    password = str(password) if password else ""
    imdb_id = str(imdb_id) if imdb_id else ""
    source_key = str(source_key) if source_key else ""

    raw_payload = f"{title}|{url}|{size_mb}|{password}|{imdb_id}|{source_key}"
    encoded_payload = urlsafe_b64encode(raw_payload.encode("utf-8")).decode("utf-8")

    return (
        f"{shared_state.values['internal_address']}/download/?payload={encoded_payload}"
    )


# =============================================================================
# LINK STATUS CHECKING
# =============================================================================


def generate_status_url(href, crypter_type):
    """
    Generate a status URL for crypters that support it.
    Returns None if status URL cannot be generated.
    """
    if crypter_type == "hide":
        # hide.cx links: https://hide.cx/folder/{UUID} or /container/{UUID} → https://hide.cx/state/{UUID}
        match = re.search(
            r"hide\.cx/(?:folder/|container/)?([a-f0-9-]{36})", href, re.IGNORECASE
        )
        if match:
            uuid = match.group(1)
            return f"https://hide.cx/state/{uuid}"

    elif crypter_type == "tolink":
        # tolink links: https://tolink.to/f/{ID} → https://tolink.to/f/{ID}/s/status.png
        match = re.search(r"tolink\.to/f/([a-zA-Z0-9]+)", href, re.IGNORECASE)
        if match:
            link_id = match.group(1)
            return f"https://tolink.to/f/{link_id}/s/status.png"

    return None


def detect_crypter_type(url):
    """Detect crypter type from URL for status checking."""
    url_lower = url.lower()
    if "hide." in url_lower:
        return "hide"
    elif "tolink." in url_lower:
        return "tolink"
    elif "filecrypt." in url_lower:
        return "filecrypt"
    elif "keeplinks." in url_lower:
        return "keeplinks"
    return None


def image_has_green(image_data):
    """
    Analyze image data to check if it contains green pixels.
    Returns True if any significant green is detected (indicating online status).
    """
    try:
        img = Image.open(BytesIO(image_data))
        # Convert palette images with transparency to RGBA first to avoid warning
        if img.mode == "P" and "transparency" in img.info:
            img = img.convert("RGBA")
        img = img.convert("RGB")

        pixels = list(img.getdata())

        for r, g, b in pixels:
            # Check if pixel is greenish: green channel is dominant
            # and has a reasonable absolute value
            if g > 100 and g > r * 1.3 and g > b * 1.3:
                return True

        return False
    except Exception:
        # If we can't analyze, assume online to not skip valid links
        return True


def fetch_status_image(status_url, shared_state=None):
    """
    Fetch a status image and return (status_url, image_data).
    Returns (status_url, None) on failure.
    """
    try:
        headers = {}
        if shared_state:
            user_agent = shared_state.values.get("user_agent")
            if user_agent:
                headers["User-Agent"] = user_agent
        response = requests.get(status_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return (status_url, response.content)
    except Exception:
        pass
    return (status_url, None)


def check_links_online_status(links_with_status, shared_state=None):
    """
    Check online status for links that have status URLs.
    Returns list of links that are online (or have no status URL to check).

    links_with_status: list of [href, identifier, status_url] where status_url can be None
    shared_state: optional shared state for user agent
    """
    links_to_check = [(i, link) for i, link in enumerate(links_with_status) if link[2]]

    if not links_to_check:
        # No status URLs to check, return all links as potentially online
        return [[link[0], link[1]] for link in links_with_status]

    # Batch fetch status images
    status_results = {}  # status_url -> has_green
    status_urls = list(set(link[2] for _, link in links_to_check))

    batch_size = 10
    for i in range(0, len(status_urls), batch_size):
        batch = status_urls[i : i + batch_size]
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [
                executor.submit(fetch_status_image, url, shared_state) for url in batch
            ]
            for future in as_completed(futures):
                try:
                    status_url, image_data = future.result()
                    if image_data:
                        status_results[status_url] = image_has_green(image_data)
                    else:
                        # Could not fetch, assume online
                        status_results[status_url] = True
                except Exception:
                    pass

    # Filter to online links
    online_links = []

    for link in links_with_status:
        href, identifier, status_url = link
        if not status_url:
            # No status URL, include link
            online_links.append([href, identifier])
        elif status_url in status_results:
            if status_results[status_url]:
                online_links.append([href, identifier])
        else:
            # Status check failed, include link
            online_links.append([href, identifier])

    return online_links


def filter_offline_links(links, shared_state=None, log_func=None):
    """
    Filter out offline links from a list of [url, identifier] pairs.
    Only checks links where status can be verified (hide.cx, tolink).
    Returns filtered list of [url, identifier] pairs.
    """
    if not links:
        return links

    # Build list with status URLs
    links_with_status = []
    for link in links:
        url = link[0]
        identifier = link[1] if len(link) > 1 else "unknown"
        crypter_type = detect_crypter_type(url)
        status_url = generate_status_url(url, crypter_type) if crypter_type else None
        links_with_status.append([url, identifier, status_url])

    # Check if any links can be verified
    verifiable_count = sum(1 for l in links_with_status if l[2])
    if verifiable_count == 0:
        # Nothing to verify, return original links
        return links

    if log_func:
        log_func(f"Checking online status for {verifiable_count} verifiable link(s)...")

    # Check status and filter
    online_links = check_links_online_status(links_with_status, shared_state)

    if log_func and len(online_links) < len(links):
        offline_count = len(links) - len(online_links)
        log_func(f"Filtered out {offline_count} offline link(s)")

    return online_links


def parse_payload(payload_str):
    """
    Parse the base64-encoded payload string into its components.

    Format: title|url|size_mb|password|imdb_id|source_key

    Returns:
        dict with keys: title, url, size_mb, password, imdb_id, source_key
    """
    decoded = urlsafe_b64decode(payload_str.encode()).decode()
    parts = decoded.split("|")

    if len(parts) == 6:
        title, url, size_mb, password, imdb_id, source_key = parts
    else:
        raise ValueError(f"expected 6 fields, got {len(parts)}")

    return {
        "title": title,
        "url": url,
        "size_mb": size_mb,
        "password": password if password else None,
        "imdb_id": imdb_id if imdb_id else None,
        "source_key": source_key if source_key else None,
    }


def determine_category(request_from, category=None):
    """
    Determine the category based on the provided category or the client type.
    If category is not provided or invalid, falls back to default mapping based on request_from.
    """
    if category and download_category_exists(category):
        return category

    client_type = extract_client_type(request_from)
    # Default mapping
    category_map = {"lazylibrarian": "docs", "radarr": "movies", "sonarr": "tv"}
    return category_map.get(client_type, "tv")


def determine_search_category(request_from):
    """
    Determine the numeric search category based on the client type.
    Returns 2000 (Movies), 5000 (TV), or 7000 (Books).
    Defaults to 5000 (TV) if unknown.
    """
    client_type = extract_client_type(request_from)
    if client_type == "radarr":
        return SEARCH_CAT_MOVIES
    elif client_type == "lazylibrarian":
        return SEARCH_CAT_BOOKS
    elif client_type == "sonarr":
        return SEARCH_CAT_SHOWS
    else:
        warn(f"Unknown client type '{client_type}' from '{request_from}'")
        return None


def extract_client_type(request_from):
    """
    Extract client type from User-Agent, stripping version info.

    Examples:
        "Radarr/6.0.4.10291 (alpine 3.23.2)" → "radarr"
        "Sonarr/4.0.0.123" → "sonarr"
        "LazyLibrarian/1.0" → "lazylibrarian"
    """
    if not request_from:
        return "unknown"

    # Extract the client name before the version (first part before '/')
    client = request_from.split("/")[0].lower().strip()

    # Normalize known clients
    if "radarr" in client:
        return "radarr"
    elif "sonarr" in client:
        return "sonarr"
    elif "lazylibrarian" in client:
        return "lazylibrarian"

    return client
