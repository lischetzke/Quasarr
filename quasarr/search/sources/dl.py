# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re
import time
from datetime import datetime
from html import unescape

from bs4 import BeautifulSoup

from quasarr.providers.hostname_issues import clear_hostname_issue, mark_hostname_issue
from quasarr.providers.imdb_metadata import get_localized_title, get_year
from quasarr.providers.log import debug, info, trace, warn
from quasarr.providers.sessions.dl import (
    fetch_via_requests_session,
    invalidate_session,
    retrieve_and_validate_session,
)
from quasarr.providers.utils import (
    SEARCH_CAT_BOOKS,
    SEARCH_CAT_MOVIES,
    SEARCH_CAT_SHOWS,
    generate_download_link,
)

hostname = "dl"

RESOLUTION_REGEX = re.compile(r"\d{3,4}p", re.I)
CODEC_REGEX = re.compile(r"x264|x265|h264|h265|hevc|avc", re.I)
XXX_REGEX = re.compile(r"\.xxx\.", re.I)


def convert_to_rss_date(iso_date_str):
    """
    Convert ISO format datetime to RSS date format.
    DL date format: '2025-12-15T20:43:06+0100'
    Returns: 'Sun, 15 Dec 2025 20:43:06 +0100'
    Falls back to current time if conversion fails.
    """
    if not iso_date_str:
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    try:
        dt_obj = datetime.fromisoformat(iso_date_str)
        return dt_obj.strftime("%a, %d %b %Y %H:%M:%S %z")
    except Exception:
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")


def normalize_title_for_arr(title):
    """
    Normalize title for *arr by replacing spaces with dots.
    """
    title = title.replace(" ", ".")
    title = re.sub(r"\s*-\s*", "-", title)
    title = re.sub(r"\.\-\.", "-", title)
    title = re.sub(r"\.{2,}", ".", title)
    title = title.strip(".")
    return title


def dl_feed(shared_state, start_time, search_category):
    """
    Parse the correct forum and return releases.
    """
    releases = []
    host = shared_state.values["config"]("Hostnames").get(hostname)

    if search_category == SEARCH_CAT_BOOKS:
        forum = "magazine-zeitschriften.72"
    elif search_category == SEARCH_CAT_MOVIES:
        forum = "hd.8"
    elif search_category == SEARCH_CAT_SHOWS:
        forum = "hd.14"
    else:
        warn(f"Unknown search category: {search_category}")
        return releases

    if not host:
        debug("hostname not configured")
        return releases

    try:
        sess = retrieve_and_validate_session(shared_state)
        if not sess:
            warn(f"Could not retrieve valid session for {host}")
            return releases

        forum_url = f"https://www.{host}/forums/{forum}/?order=post_date&direction=desc"
        r = sess.get(forum_url, timeout=30)
        r.raise_for_status()

        soup = BeautifulSoup(r.content, "html.parser")

        # Find all thread items in the forum
        items = soup.select("div.structItem.structItem--thread")

        if not items:
            debug("No entries found in Forum")
            return releases

        for item in items:
            try:
                # Extract title from the thread
                title_elem = item.select_one("div.structItem-title a")
                if not title_elem:
                    continue

                title = "".join(title_elem.strings)
                if not title:
                    continue

                title = unescape(title)
                title = normalize_title_for_arr(title)

                # Extract thread URL
                thread_url = title_elem.get("href")
                if not thread_url:
                    continue

                # Make sure URL is absolute
                if thread_url.startswith("/"):
                    thread_url = f"https://www.{host}{thread_url}"

                # Extract date and convert to RFC 2822 format
                date_elem = item.select_one("time.u-dt")
                iso_date = date_elem.get("datetime", "") if date_elem else ""
                published = convert_to_rss_date(iso_date)

                mb = 0
                imdb_id = None
                password = ""

                link = generate_download_link(
                    shared_state,
                    title,
                    thread_url,
                    mb,
                    password,
                    imdb_id or "",
                    hostname,
                )

                releases.append(
                    {
                        "details": {
                            "title": title,
                            "hostname": hostname,
                            "imdb_id": imdb_id,
                            "link": link,
                            "size": mb * 1024 * 1024,
                            "date": published,
                            "source": thread_url,
                        },
                        "type": "protected",
                    }
                )

            except Exception as e:
                debug(f"error parsing Forum item: {e}")
                continue

    except Exception as e:
        warn(f"Forum feed error: {e}")
        mark_hostname_issue(
            hostname, "feed", str(e) if "e" in dir() else "Error occurred"
        )
        invalidate_session(shared_state)

    elapsed = time.time() - start_time
    debug(f"Time taken: {elapsed:.2f}s")

    if releases:
        clear_hostname_issue(hostname)
    return releases


def _replace_umlauts(text):
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }

    for umlaut, replacement in replacements.items():
        text = text.replace(umlaut, replacement)

    return text


def _search_single_page(
    shared_state,
    host,
    search_string,
    search_id,
    page_num,
    imdb_id,
    search_category,
    season,
    episode,
):
    """
    Search a single page. This function is called in parallel for each page.
    """
    page_releases = []

    search_string = _replace_umlauts(search_string)

    try:
        if page_num == 1:
            search_params = {"keywords": search_string, "c[title_only]": 1}
            search_url = f"https://www.{host}/search/search"
        else:
            if not search_id:
                return page_releases, None

            search_params = {"page": page_num, "q": search_string, "o": "relevance"}
            search_url = f"https://www.{host}/search/{search_id}/"

        search_response = fetch_via_requests_session(
            shared_state,
            method="GET",
            target_url=search_url,
            get_params=search_params,
            timeout=10,
        )

        if search_response.status_code != 200:
            debug(f"[Page {page_num}] returned status {search_response.status_code}")
            return page_releases, None

        # Extract search ID from first page
        extracted_search_id = None
        if page_num == 1:
            match = re.search(r"/search/(\d+)/", search_response.url)
            if match:
                extracted_search_id = match.group(1)
                trace(f"[Page 1] Extracted search ID: {extracted_search_id}")

        soup = BeautifulSoup(search_response.text, "html.parser")
        result_items = soup.select("li.block-row")

        if not result_items:
            trace(f"[Page {page_num}] found 0 results")
            return page_releases, extracted_search_id

        trace(f"[Page {page_num}] found {len(result_items)} results")

        for item in result_items:
            try:
                title_elem = item.select_one("h3.contentRow-title a")
                if not title_elem:
                    continue

                # Skip "Wird gesucht" threads
                label = item.select_one(".contentRow-minor .label")
                if label and "wird gesucht" in label.get_text(strip=True).lower():
                    continue

                title = "".join(title_elem.strings)

                title = re.sub(r"\s+", " ", title)
                title = unescape(title)
                title_normalized = normalize_title_for_arr(title)

                # Filter: Skip if no resolution or codec info (unless LazyLibrarian)
                if search_category != SEARCH_CAT_BOOKS:
                    if not (
                        RESOLUTION_REGEX.search(title_normalized)
                        or CODEC_REGEX.search(title_normalized)
                    ):
                        continue

                # Filter: Skip XXX content unless explicitly searched for
                if (
                    XXX_REGEX.search(title_normalized)
                    and "xxx" not in search_string.lower()
                ):
                    continue

                thread_url = title_elem.get("href")
                if thread_url.startswith("/"):
                    thread_url = f"https://www.{host}{thread_url}"

                if not shared_state.is_valid_release(
                    title_normalized, search_category, search_string, season, episode
                ):
                    continue

                # Extract date and convert to RFC 2822 format
                date_elem = item.select_one("time.u-dt")
                iso_date = date_elem.get("datetime", "") if date_elem else ""
                published = convert_to_rss_date(iso_date)

                mb = 0
                password = ""

                link = generate_download_link(
                    shared_state,
                    title_normalized,
                    thread_url,
                    mb,
                    password,
                    imdb_id or "",
                    hostname,
                )

                page_releases.append(
                    {
                        "details": {
                            "title": title_normalized,
                            "hostname": hostname,
                            "imdb_id": imdb_id,
                            "link": link,
                            "size": mb * 1024 * 1024,
                            "date": published,
                            "source": thread_url,
                        },
                        "type": "protected",
                    }
                )

            except Exception as e:
                debug(f"[Page {page_num}] error parsing item: {e}")

        return page_releases, extracted_search_id

    except Exception as e:
        warn(f"[Page {page_num}] error: {e}")
        mark_hostname_issue(
            hostname, "search", str(e) if "e" in dir() else "Error occurred"
        )
        return page_releases, None


def dl_search(
    shared_state,
    start_time,
    search_category,
    search_string,
    season=None,
    episode=None,
):
    """
    Search with sequential pagination to find best quality releases.
    Stops searching if a page returns 0 results or 10 seconds have elapsed.
    """
    releases = []
    host = shared_state.values["config"]("Hostnames").get(hostname)

    imdb_id = shared_state.is_imdb_id(search_string)
    if imdb_id:
        title = get_localized_title(shared_state, imdb_id, "de")
        if not title:
            info(f"no title for IMDb {imdb_id}")
            return releases
        search_string = title
        if not season:
            if year := get_year(imdb_id):
                search_string += f" {year}"

    search_string = unescape(search_string)
    max_search_duration = 7

    trace(
        f"Starting sequential paginated search for '{search_string}' (Season: {season}, Episode: {episode}) - max {max_search_duration}s"
    )

    try:
        sess = retrieve_and_validate_session(shared_state)
        if not sess:
            warn(f"Could not retrieve valid session for {host}")
            return releases

        search_id = None
        page_num = 0
        search_start_time = time.time()
        release_titles_per_page = set()

        # Sequential search through pages until timeout or no results
        while (time.time() - search_start_time) < max_search_duration:
            page_num += 1

            page_releases, extracted_search_id = _search_single_page(
                shared_state,
                host,
                search_string,
                search_id,
                page_num,
                imdb_id,
                search_category,
                season,
                episode,
            )

            page_release_titles = tuple(pr["details"]["title"] for pr in page_releases)
            if page_release_titles in release_titles_per_page:
                trace(f"[Page {page_num}] duplicate page detected, stopping")
                break
            release_titles_per_page.add(page_release_titles)

            # Update search_id from first page
            if page_num == 1:
                search_id = extracted_search_id
                if not search_id:
                    trace("Could not extract search ID, stopping pagination")
                    break

            # Add releases from this page
            releases.extend(page_releases)
            trace(
                f"[Page {page_num}] completed with {len(page_releases)} valid releases"
            )

            # Stop if this page returned 0 results
            if len(page_releases) == 0:
                trace(f"[Page {page_num}] returned 0 results, stopping pagination")
                break

    except Exception as e:
        info(f"search error: {e}")
        mark_hostname_issue(
            hostname, "search", str(e) if "e" in dir() else "Error occurred"
        )
        invalidate_session(shared_state)

    trace(
        f"FINAL - Found {len(releases)} valid releases - providing to {search_category}"
    )

    elapsed = time.time() - start_time
    debug(f"Time taken: {elapsed:.2f}s")

    if releases:
        clear_hostname_issue(hostname)
    return releases
