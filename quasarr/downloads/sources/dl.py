# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re

from bs4 import BeautifulSoup

from quasarr.providers.log import info, debug
from quasarr.providers.sessions.dl import retrieve_and_validate_session, fetch_via_requests_session, invalidate_session

hostname = "dl"


def extract_password_from_post(soup, host):
    """
    Extract password from forum post using multiple strategies.
    Returns empty string if no password found or if explicitly marked as 'no password'.
    """
    post_text = soup.get_text()
    post_text = re.sub(r'\s+', ' ', post_text).strip()

    password_pattern = r'(?:passwort|password|pass|pw)[\s:]+([a-zA-Z0-9._-]{2,50})'
    match = re.search(password_pattern, post_text, re.IGNORECASE)

    if match:
        password = match.group(1).strip()
        if not re.match(r'^(?:download|mirror|link|episode|info|mediainfo|spoiler|hier|click|klick|kein|none|no)',
                        password, re.IGNORECASE):
            debug(f"Found password: {password}")
            return password

    no_password_patterns = [
        r'(?:passwort|password|pass|pw)[\s:]*(?:kein(?:es)?|none|no|nicht|not|nein|-|–|—)',
        r'(?:kein(?:es)?|none|no|nicht|not|nein)\s*(?:passwort|password|pass|pw)',
    ]

    for pattern in no_password_patterns:
        if re.search(pattern, post_text, re.IGNORECASE):
            debug("No password required (explicitly stated)")
            return ""

    default_password = f"www.{host}"
    debug(f"No password found, using default: {default_password}")
    return default_password


def extract_mirror_name_from_link(link_element):
    """
    Extract the mirror/hoster name from the link text or nearby text.
    """
    link_text = link_element.get_text(strip=True)
    common_non_hosters = {'download', 'mirror', 'link', 'hier', 'click', 'klick', 'code', 'spoiler'}

    # Known hoster patterns for image detection
    known_hosters = {
        'rapidgator': ['rapidgator', 'rg'],
        'ddownload': ['ddownload', 'ddl'],
        'turbobit': ['turbobit'],
        '1fichier': ['1fichier'],
    }

    if link_text and len(link_text) > 2:
        cleaned = re.sub(r'[^\w\s-]', '', link_text).strip().lower()
        if cleaned and cleaned not in common_non_hosters:
            main_part = cleaned.split()[0] if ' ' in cleaned else cleaned
            if 2 < len(main_part) < 30:
                return main_part

    parent = link_element.parent
    if parent:
        for sibling in link_element.previous_siblings:
            # Only process Tag elements, skip NavigableString (text nodes)
            if not hasattr(sibling, 'name') or sibling.name is None:
                continue

            # Skip spoiler elements entirely
            classes = sibling.get('class', [])
            if classes and any('spoiler' in str(c).lower() for c in classes):
                continue

            # Check for images with hoster names in src/alt/data-url
            img = sibling.find('img') if sibling.name != 'img' else sibling
            if img:
                img_identifiers = (img.get('src', '') + img.get('alt', '') + img.get('data-url', '')).lower()
                for hoster, patterns in known_hosters.items():
                    if any(pattern in img_identifiers for pattern in patterns):
                        return hoster

            sibling_text = sibling.get_text(strip=True).lower()
            # Skip if text is too long - likely NFO content or other non-mirror text
            if len(sibling_text) > 30:
                continue
            if sibling_text and len(sibling_text) > 2 and sibling_text not in common_non_hosters:
                cleaned = re.sub(r'[^\w\s-]', '', sibling_text).strip()
                if cleaned and 2 < len(cleaned) < 30:
                    return cleaned.split()[0] if ' ' in cleaned else cleaned

    return None


def extract_links_and_password_from_post(post_content, host):
    """
    Extract download links and password from a forum post.
    """
    links = []
    soup = BeautifulSoup(post_content, 'html.parser')

    for link in soup.find_all('a', href=True):
        href = link.get('href')

        if href.startswith('/') or host in href:
            continue

        if re.search(r'filecrypt\.', href, re.IGNORECASE):
            crypter_type = "filecrypt"
        elif re.search(r'hide\.', href, re.IGNORECASE):
            crypter_type = "hide"
        elif re.search(r'keeplinks\.', href, re.IGNORECASE):
            crypter_type = "keeplinks"
        elif re.search(r'tolink\.', href, re.IGNORECASE):
            crypter_type = "tolink"
        else:
            debug(f"Unsupported link crypter/hoster found: {href}")
            continue

        mirror_name = extract_mirror_name_from_link(link)
        identifier = mirror_name if mirror_name else crypter_type

        if [href, identifier] not in links:
            links.append([href, identifier])
            if mirror_name:
                debug(f"Found {crypter_type} link for mirror: {mirror_name}")
            else:
                debug(f"Found {crypter_type} link (no mirror name detected)")

    password = ""
    if links:
        password = extract_password_from_post(soup, host)

    return links, password


def get_dl_download_links(shared_state, url, mirror, title, password):
    """
    KEEP THE SIGNATURE EVEN IF SOME PARAMETERS ARE UNUSED!

    DL source handler - extracts links and password from forum thread.

    Note: The password parameter is unused intentionally - password must be extracted from the post.
    """

    host = shared_state.values["config"]("Hostnames").get(hostname)

    sess = retrieve_and_validate_session(shared_state)
    if not sess:
        info(f"Could not retrieve valid session for {host}")
        return {"links": [], "password": ""}

    try:
        response = fetch_via_requests_session(shared_state, method="GET", target_url=url, timeout=30)

        if response.status_code != 200:
            info(f"Failed to load thread page: {url} (Status: {response.status_code})")
            return {"links": [], "password": ""}

        soup = BeautifulSoup(response.text, 'html.parser')

        first_post = soup.select_one('article.message--post')
        if not first_post:
            info(f"Could not find first post in thread: {url}")
            return {"links": [], "password": ""}

        post_content = first_post.select_one('div.bbWrapper')
        if not post_content:
            info(f"Could not find post content in thread: {url}")
            return {"links": [], "password": ""}

        links, extracted_password = extract_links_and_password_from_post(str(post_content), host)

        if not links:
            info(f"No supported download links found in thread: {url}")
            return {"links": [], "password": ""}

        debug(f"Found {len(links)} download link(s) for: {title} (password: {extracted_password})")
        return {"links": links, "password": extracted_password}

    except Exception as e:
        info(f"Error extracting download links from {url}: {e}")
        invalidate_session(shared_state)
        return {"links": [], "password": ""}
