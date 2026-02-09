# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re
import time

import requests
from bs4 import BeautifulSoup

from quasarr.constants import SEARCH_CAT_BOOKS, SEARCH_CAT_MUSIC
from quasarr.providers.hostname_issues import clear_hostname_issue, mark_hostname_issue
from quasarr.providers.log import debug, info, trace, warn
from quasarr.providers.utils import (
    convert_to_mb,
    generate_download_link,
    is_imdb_id,
    is_valid_release,
    sanitize_title,
)

hostname = "fx"


def extract_size(text):
    match = re.match(r"(\d+)\s*([A-Za-z]+)", text)
    if match:
        size = match.group(1)
        unit = match.group(2)
        return {"size": size, "sizeunit": unit}
    else:
        raise ValueError(f"Invalid size format: {text}")


def fx_feed(shared_state, start_time, search_category):
    releases = []

    fx = shared_state.values["config"]("Hostnames").get(hostname.lower())

    if search_category in [SEARCH_CAT_BOOKS, SEARCH_CAT_MUSIC]:
        debug(
            f"<d>Skipping <y>{search_category}</y> on <g>{hostname.upper()}</g> (category not supported)!</d>"
        )
        return releases

    password = fx.split(".")[0]
    url = f"https://{fx}/"
    headers = {
        "User-Agent": shared_state.values["user_agent"],
    }

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        feed = BeautifulSoup(r.content, "html.parser")
        items = feed.find_all("article")
    except Exception as e:
        warn(f"Error loading {hostname.upper()} feed: {e}")
        mark_hostname_issue(
            hostname, "feed", str(e) if "e" in dir() else "Error occurred"
        )
        return releases

    if items:
        for item in items:
            try:
                article = BeautifulSoup(str(item), "html.parser")
                try:
                    source = article.find("h2", class_="entry-title").a["href"]
                    titles = article.find_all(
                        "a", href=re.compile("(filecrypt|safe." + fx + ")")
                    )
                except:
                    continue
                i = 0
                for title in titles:
                    link = title["href"]
                    title = sanitize_title(title.text)

                    try:
                        imdb_link = article.find("a", href=re.compile(r"imdb\.com"))
                        imdb_id = re.search(r"tt\d+", str(imdb_link)).group()
                    except:
                        imdb_id = None

                    try:
                        size_info = (
                            article.find_all(
                                "strong",
                                text=re.compile(r"(size|größe)", re.IGNORECASE),
                            )[i]
                            .next.next.text.replace("|", "")
                            .strip()
                        )
                        size_item = extract_size(size_info)
                        mb = convert_to_mb(size_item)
                        size = mb * 1024 * 1024

                        link = generate_download_link(
                            shared_state,
                            title,
                            link,
                            mb,
                            password,
                            imdb_id,
                            hostname,
                        )
                    except:
                        continue

                    try:
                        dates = article.find_all("time")
                        for date in dates:
                            published = date["datetime"]
                    except:
                        continue

                    releases.append(
                        {
                            "details": {
                                "title": title,
                                "hostname": hostname.lower(),
                                "imdb_id": imdb_id,
                                "link": link,
                                "size": size,
                                "date": published,
                                "source": source,
                            },
                            "type": "protected",
                        }
                    )

            except Exception as e:
                info(f"Error parsing {hostname.upper()} feed: {e}")
                mark_hostname_issue(
                    hostname, "feed", str(e) if "e" in dir() else "Error occurred"
                )

    elapsed_time = time.time() - start_time
    debug(f"Time taken: {elapsed_time:.2f}s")

    if releases:
        clear_hostname_issue(hostname)
    return releases


def fx_search(
    shared_state,
    start_time,
    search_category,
    search_string,
    season=None,
    episode=None,
):
    releases = []
    fx = shared_state.values["config"]("Hostnames").get(hostname.lower())
    password = fx.split(".")[0]

    if search_category in [SEARCH_CAT_BOOKS, SEARCH_CAT_MUSIC]:
        debug(
            f"<d>Skipping <y>{search_category}</y> on <g>{hostname.upper()}</g> (category not supported)!</d>"
        )
        return releases

    if search_string != "":
        imdb_id = is_imdb_id(search_string)
    else:
        imdb_id = None

    url = f"https://{fx}/?s={search_string}"
    headers = {
        "User-Agent": shared_state.values["user_agent"],
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        search = BeautifulSoup(r.content, "html.parser")
        results = search.find("h2", class_="entry-title")

    except Exception as e:
        warn(f"Error loading {hostname.upper()} feed: {e}")
        mark_hostname_issue(
            hostname, "search", str(e) if "e" in dir() else "Error occurred"
        )
        return releases

    if results:
        for result in results:
            try:
                result_source = result["href"]
                result_r = requests.get(result_source, headers=headers, timeout=10)
                result_r.raise_for_status()
                feed = BeautifulSoup(result_r.content, "html.parser")
                items = feed.find_all("article")
            except Exception as e:
                warn(f"Error loading {hostname.upper()} feed: {e}")
                mark_hostname_issue(
                    hostname, "search", str(e) if "e" in dir() else "Error occurred"
                )
                return releases

            for item in items:
                try:
                    article = BeautifulSoup(str(item), "html.parser")
                    try:
                        titles = article.find_all("a", href=re.compile(r"filecrypt\."))
                    except:
                        continue
                    i = 0
                    for title in titles:
                        link = title["href"]
                        title = sanitize_title(title.text)

                        if not is_valid_release(
                            title, search_category, search_string, season, episode
                        ):
                            continue

                        try:
                            imdb_link = article.find("a", href=re.compile(r"imdb\.com"))
                            release_imdb_id = re.search(
                                r"tt\d+", str(imdb_link)
                            ).group()
                        except:
                            release_imdb_id = None

                        if imdb_id and release_imdb_id and release_imdb_id != imdb_id:
                            trace(f"Skipping result '{title}' due to IMDb ID mismatch.")
                            continue

                        if release_imdb_id is None:
                            release_imdb_id = imdb_id

                        try:
                            size_info = (
                                article.find_all(
                                    "strong",
                                    text=re.compile(r"(size|größe)", re.IGNORECASE),
                                )[i]
                                .next.next.text.replace("|", "")
                                .strip()
                            )
                            size_item = extract_size(size_info)
                            mb = convert_to_mb(size_item)
                            size = mb * 1024 * 1024

                            link = generate_download_link(
                                shared_state,
                                title,
                                link,
                                mb,
                                password,
                                imdb_id,
                                hostname,
                            )
                        except:
                            continue

                        try:
                            dates = article.find_all("time")
                            for date in dates:
                                published = date["datetime"]
                        except:
                            continue

                        releases.append(
                            {
                                "details": {
                                    "title": title,
                                    "hostname": hostname.lower(),
                                    "imdb_id": imdb_id,
                                    "link": link,
                                    "size": size,
                                    "date": published,
                                    "source": result_source,
                                },
                                "type": "protected",
                            }
                        )

                except Exception as e:
                    info(f"Error parsing search: {e}")
                    mark_hostname_issue(
                        hostname, "search", str(e) if "e" in dir() else "Error occurred"
                    )

    elapsed_time = time.time() - start_time
    debug(f"Time taken: {elapsed_time:.2f}s")

    if releases:
        clear_hostname_issue(hostname)
    return releases
