# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import json
import re

from quasarr.downloads.linkcrypters.hide import decrypt_links_if_hide
from quasarr.downloads.sources.al import get_al_download_links
from quasarr.downloads.sources.by import get_by_download_links
from quasarr.downloads.sources.dd import get_dd_download_links
from quasarr.downloads.sources.dj import get_dj_download_links
from quasarr.downloads.sources.dl import get_dl_download_links
from quasarr.downloads.sources.dt import get_dt_download_links
from quasarr.downloads.sources.dw import get_dw_download_links
from quasarr.downloads.sources.he import get_he_download_links
from quasarr.downloads.sources.mb import get_mb_download_links
from quasarr.downloads.sources.nk import get_nk_download_links
from quasarr.downloads.sources.nx import get_nx_download_links
from quasarr.downloads.sources.sf import get_sf_download_links
from quasarr.downloads.sources.sj import get_sj_download_links
from quasarr.downloads.sources.sl import get_sl_download_links
from quasarr.downloads.sources.wd import get_wd_download_links
from quasarr.downloads.sources.wx import get_wx_download_links
from quasarr.providers.log import info
from quasarr.providers.notifications import send_discord_message
from quasarr.providers.statistics import StatsHelper

# =============================================================================
# CRYPTER CONFIGURATION
# =============================================================================

# Patterns match crypter name only - TLDs may change
AUTO_DECRYPT_PATTERNS = {
    'hide': re.compile(r'hide\.', re.IGNORECASE),
}

PROTECTED_PATTERNS = {
    'filecrypt': re.compile(r'filecrypt\.', re.IGNORECASE),
    'tolink': re.compile(r'tolink\.', re.IGNORECASE),
    'keeplinks': re.compile(r'keeplinks\.', re.IGNORECASE),
}

# Source key -> getter function mapping
# All getters have signature: (shared_state, url, mirror, title, password)
# AL uses password as release_id, others ignore it
SOURCE_GETTERS = {
    'al': get_al_download_links,
    'by': get_by_download_links,
    'dd': get_dd_download_links,
    'dj': get_dj_download_links,
    'dl': get_dl_download_links,
    'dt': get_dt_download_links,
    'dw': get_dw_download_links,
    'he': get_he_download_links,
    'mb': get_mb_download_links,
    'nk': get_nk_download_links,
    'nx': get_nx_download_links,
    'sf': get_sf_download_links,
    'sj': get_sj_download_links,
    'sl': get_sl_download_links,
    'wd': get_wd_download_links,
    'wx': get_wx_download_links,
}


# =============================================================================
# LINK CLASSIFICATION
# =============================================================================

def detect_crypter(url):
    """Returns (crypter_name, 'auto'|'protected') or (None, None)."""
    for name, pattern in AUTO_DECRYPT_PATTERNS.items():
        if pattern.search(url):
            return name, 'auto'
    for name, pattern in PROTECTED_PATTERNS.items():
        if pattern.search(url):
            return name, 'protected'
    return None, None


def is_junkies_link(url, shared_state):
    """Check if URL is a junkies (sj/dj) link."""
    sj = shared_state.values["config"]("Hostnames").get("sj")
    dj = shared_state.values["config"]("Hostnames").get("dj")
    url_lower = url.lower()
    return (sj and sj.lower() in url_lower) or (dj and dj.lower() in url_lower)


def classify_links(links, shared_state):
    """
    Classify links into direct/auto/protected categories.
    Direct = anything that's not a known crypter or junkies link.
    Mirror names from source are preserved.
    """
    classified = {'direct': [], 'auto': [], 'protected': []}

    for link in links:
        url = link[0]

        if is_junkies_link(url, shared_state):
            classified['protected'].append(link)
            continue

        crypter, crypter_type = detect_crypter(url)
        if crypter_type == 'auto':
            classified['auto'].append(link)
        elif crypter_type == 'protected':
            classified['protected'].append(link)
        else:
            # Not a known crypter = direct hoster link
            classified['direct'].append(link)

    return classified


# =============================================================================
# LINK PROCESSING
# =============================================================================

def handle_direct_links(shared_state, links, title, password, package_id):
    """Send direct hoster links to JDownloader."""
    urls = [link[0] for link in links]
    info(f"Sending {len(urls)} direct download links for {title}")

    if shared_state.download_package(urls, title, password, package_id):
        StatsHelper(shared_state).increment_package_with_links(urls)
        return {"success": True}
    return {"success": False, "reason": f'Failed to add {len(urls)} links to linkgrabber'}


def handle_auto_decrypt_links(shared_state, links, title, password, package_id):
    """Decrypt hide.cx links and send to JDownloader."""
    result = decrypt_links_if_hide(shared_state, links)

    if result.get("status") != "success":
        return {"success": False, "reason": "Auto-decrypt failed"}

    decrypted_urls = result.get("results", [])
    if not decrypted_urls:
        return {"success": False, "reason": "No links decrypted"}

    info(f"Decrypted {len(decrypted_urls)} download links for {title}")

    if shared_state.download_package(decrypted_urls, title, password, package_id):
        StatsHelper(shared_state).increment_package_with_links(decrypted_urls)
        return {"success": True}
    return {"success": False, "reason": "Failed to add decrypted links to linkgrabber"}


def store_protected_links(shared_state, links, title, password, package_id, size_mb=None, original_url=None):
    """Store protected links for CAPTCHA UI."""
    blob_data = {"title": title, "links": links, "password": password, "size_mb": size_mb}
    if original_url:
        blob_data["original_url"] = original_url

    shared_state.values["database"]("protected").update_store(package_id, json.dumps(blob_data))
    info(f'CAPTCHA-Solution required for "{title}" at: "{shared_state.values["external_address"]}/captcha"')
    return {"success": True}


def process_links(shared_state, source_result, title, password, package_id, imdb_id, source_url, size_mb, label):
    """
    Central link processor with priority: direct → auto-decrypt → protected.
    If ANY direct links exist, use them and ignore crypted fallbacks.
    """
    if not source_result:
        return fail(title, package_id, shared_state,
                    reason=f'Source returned no data for "{title}" on {label} - "{source_url}"')

    links = source_result.get("links", [])
    password = source_result.get("password") or password
    imdb_id = imdb_id or source_result.get("imdb_id")
    title = source_result.get("title") or title

    if not links:
        return fail(title, package_id, shared_state,
                    reason=f'No links found for "{title}" on {label} - "{source_url}"')

    # Filter out 404 links
    valid_links = [link for link in links if "/404.html" not in link[0]]
    if not valid_links:
        return fail(title, package_id, shared_state,
                    reason=f'All links are offline or IP is banned for "{title}" on {label} - "{source_url}"')
    links = valid_links

    classified = classify_links(links, shared_state)

    # PRIORITY 1: Direct hoster links
    if classified['direct']:
        info(f"Found {len(classified['direct'])} direct hoster links for {title}")
        send_discord_message(shared_state, title=title, case="unprotected", imdb_id=imdb_id, source=source_url)
        result = handle_direct_links(shared_state, classified['direct'], title, password, package_id)
        if result["success"]:
            return {"success": True, "title": title}
        return fail(title, package_id, shared_state, reason=result.get("reason"))

    # PRIORITY 2: Auto-decryptable (hide.cx)
    if classified['auto']:
        info(f"Found {len(classified['auto'])} auto-decryptable links for {title}")
        result = handle_auto_decrypt_links(shared_state, classified['auto'], title, password, package_id)
        if result["success"]:
            send_discord_message(shared_state, title=title, case="unprotected", imdb_id=imdb_id, source=source_url)
            return {"success": True, "title": title}
        info(f"Auto-decrypt failed for {title}, checking for protected fallback...")

    # PRIORITY 3: Protected (filecrypt, tolink, keeplinks, junkies)
    if classified['protected']:
        info(f"Found {len(classified['protected'])} protected links for {title}")
        send_discord_message(shared_state, title=title, case="captcha", imdb_id=imdb_id, source=source_url)
        store_protected_links(shared_state, classified['protected'], title, password, package_id,
                              size_mb=size_mb, original_url=source_url)
        return {"success": True, "title": title}

    return fail(title, package_id, shared_state,
                reason=f'No usable links found for "{title}" on {label} - "{source_url}"')


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def download(shared_state, request_from, title, url, mirror, size_mb, password, imdb_id=None):
    """Main download entry point."""
    category = "docs" if "lazylibrarian" in request_from.lower() else \
        "movies" if "radarr" in request_from.lower() else "tv"
    package_id = f"Quasarr_{category}_{str(hash(title + url)).replace('-', '')}"

    if imdb_id and imdb_id.lower() == "none":
        imdb_id = None

    config = shared_state.values["config"]("Hostnames")

    # Find matching source - all getters have unified signature
    source_result = None
    label = None

    for key, getter in SOURCE_GETTERS.items():
        hostname = config.get(key)
        if hostname and hostname.lower() in url.lower():
            source_result = getter(shared_state, url, mirror, title, password)
            label = key.upper()
            break

    # No source matched - check if URL is a known crypter directly
    if source_result is None:
        crypter, crypter_type = detect_crypter(url)
        if crypter_type:
            # For direct crypter URLs, we only know the crypter type, not the hoster inside
            source_result = {"links": [[url, crypter]]}
            label = crypter.upper()

    if source_result is None:
        info(f'Could not find matching source for "{title}" - "{url}"')
        StatsHelper(shared_state).increment_failed_downloads()
        return {"success": False, "package_id": package_id, "title": title}

    result = process_links(shared_state, source_result, title, password, package_id, imdb_id, url, size_mb, label)
    return {"package_id": package_id, **result}


def fail(title, package_id, shared_state, reason="Unknown error"):
    """Mark download as failed."""
    try:
        info(f"Reason for failure: {reason}")
        StatsHelper(shared_state).increment_failed_downloads()
        blob = json.dumps({"title": title, "error": reason})
        shared_state.get_db("failed").store(package_id, json.dumps(blob))
        info(f'Package "{title}" marked as failed!')
    except Exception as e:
        info(f'Error marking package "{package_id}" as failed: {e}')
    return {"success": False, "title": title}
