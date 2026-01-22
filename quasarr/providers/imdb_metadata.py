# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import html
import re
from datetime import datetime, timedelta
from json import loads, dumps
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from quasarr.providers.log import info, debug


def _get_db(table_name):
    """Lazy import to avoid circular dependency."""
    from quasarr.storage.sqlite_database import DataBase
    return DataBase(table_name)


def get_poster_link(shared_state, imdb_id):
    imdb_metadata = get_imdb_metadata(imdb_id)
    if imdb_metadata:
        poster_link = imdb_metadata.get("poster_link")
        if poster_link:
            return poster_link

    poster_link = None
    if imdb_id:
        headers = {'User-Agent': shared_state.values["user_agent"]}
        request = requests.get(f"https://www.imdb.com/title/{imdb_id}/", headers=headers, timeout=10).text
        soup = BeautifulSoup(request, "html.parser")
        try:
            poster_set = soup.find('div', class_='ipc-poster').div.img[
                "srcset"]  # contains links to posters in ascending resolution
            poster_links = [x for x in poster_set.split(" ") if
                            len(x) > 10]  # extract all poster links ignoring resolution info
            poster_link = poster_links[-1]  # get the highest resolution poster
        except:
            pass

    if not poster_link:
        debug(f"Could not get poster title for {imdb_id} from IMDb")

    return poster_link

def sanitize_title(title):
    sanitized_title = html.unescape(title)
    sanitized_title = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß&-']", ' ', sanitized_title).strip()
    sanitized_title = sanitized_title.replace(" - ", "-")
    sanitized_title = re.sub(r'\s{2,}', ' ', sanitized_title)
    return sanitized_title

def get_imdb_metadata(imdb_id):
    db = _get_db("imdb_metadata")
    now = datetime.now().timestamp()

    try:
        imdb_metadata = loads(db.retrieve(imdb_id))
        if imdb_metadata["ttl"] and imdb_metadata["ttl"] > now:
            return imdb_metadata.data
    except:
        imdb_metadata = {
            "title": None,
            "year": None,
            "poster_link": None,
            "localized": {},
            "ttl": 0
        }

    imdb_metadata["ttl"] = now + timedelta(days=30).total_seconds()

    try:
        response = requests.get(f"https://api.imdbapi.dev/titles/{imdb_id}", timeout=10)
        response.raise_for_status()
        response_json = response.json()
    except Exception as e:
        info(f"Error loading imdbapi.dev for {imdb_id}: {e}")
        return imdb_metadata

    imdb_metadata["title"] = sanitize_title(response_json.get("primaryTitle", ""))
    imdb_metadata["year"] = response_json.get("startYear")

    try:
        imdb_metadata["poster_link"] = response_json.get("primaryImage").get("url")
    except Exception as e:
        debug(f"Could not find poster link for {imdb_id} from imdbapi.dev: {e}")
        imdb_metadata["ttl"] = now + timedelta(days=1).total_seconds()

    try:
        response = requests.get(f"https://api.imdbapi.dev/titles/{imdb_id}/akas", timeout=10)
        response.raise_for_status()
        
        for aka in response.json().get("akas"):
            if aka.get("language"):
                continue # skip entries with specific language tags
            if aka.get("country").get("code").lower() == "de":
                imdb_metadata["localized"]["de"] = sanitize_title(aka.get("text"))
                break
    except Exception as e:
        info(f"Error loading localized titles from IMDbAPI.dev for {imdb_id}: {e}")
        imdb_metadata["ttl"] = now + timedelta(days=1).total_seconds()
    
    db.update_store(imdb_id, dumps(imdb_metadata))
    return imdb_metadata

def get_year(imdb_id):
    imdb_metadata = get_imdb_metadata(imdb_id)
    if imdb_metadata:
        return imdb_metadata.get("year")
    return None

def get_localized_title(shared_state, imdb_id, language='de'):
    imdb_metadata = get_imdb_metadata(imdb_id)
    if imdb_metadata:
        localized_title = imdb_metadata.get("localized").get(language)
        if localized_title:
            return localized_title
        return imdb_metadata.get("title")
    
    localized_title = None

    headers = {
        'Accept-Language': language,
        'User-Agent': shared_state.values["user_agent"]
    }

    try:
        response = requests.get(f"https://www.imdb.com/title/{imdb_id}/", headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        info(f"Error loading IMDb metadata for {imdb_id}: {e}")
        return localized_title

    try:
        match = re.findall(r'<title>(.*?) \(.*?</title>', response.text)
        localized_title = match[0]
    except:
        try:
            match = re.findall(r'<title>(.*?) - IMDb</title>', response.text)
            localized_title = match[0]
        except:
            pass

    if not localized_title:
        debug(f"Could not get localized title for {imdb_id} in {language} from IMDb")
    else:
        localized_title = sanitize_title(localized_title)
    return localized_title


def get_clean_title(title):
    try:
        extracted_title = re.findall(r"(.*?)(?:.(?!19|20)\d{2}|\.German|.GERMAN|\.\d{3,4}p|\.S(?:\d{1,3}))", title)[0]
        leftover_tags_removed = re.sub(
            r'(|.UNRATED.*|.Unrated.*|.Uncut.*|.UNCUT.*)(|.Directors.Cut.*|.Final.Cut.*|.DC.*|.REMASTERED.*|.EXTENDED.*|.Extended.*|.Theatrical.*|.THEATRICAL.*)',
            "", extracted_title)
        clean_title = leftover_tags_removed.replace(".", " ").strip().replace(" ", "+")

    except:
        clean_title = title
    return clean_title


def get_imdb_id_from_title(shared_state, title, language="de"):
    imdb_id = None

    if re.search(r"S\d{1,3}(E\d{1,3})?", title, re.IGNORECASE):
        ttype = "tv"
    else:
        ttype = "ft"

    title = get_clean_title(title)

    threshold = 60 * 60 * 48  # 48 hours
    context = "recents_imdb"
    recently_searched = shared_state.get_recently_searched(shared_state, context, threshold)
    if title in recently_searched:
        title_item = recently_searched[title]
        if title_item["timestamp"] > datetime.now() - timedelta(seconds=threshold):
            return title_item["imdb_id"]

    headers = {
        'Accept-Language': language,
        'User-Agent': shared_state.values["user_agent"]
    }

    results = requests.get(f"https://www.imdb.com/find/?q={quote(title)}&s=tt&ttype={ttype}&ref_=fn_{ttype}",
                           headers=headers, timeout=10)

    if results.status_code == 200:
        soup = BeautifulSoup(results.text, "html.parser")
        props = soup.find("script", text=re.compile("props"))
        details = loads(props.string)
        search_results = details['props']['pageProps']['titleResults']['results']

        if len(search_results) > 0:
            for result in search_results:
                try:
                    found_title = result["listItem"]["titleText"]
                    found_id = result["listItem"]["titleId"]
                except KeyError:
                    found_title = result["titleNameText"]
                    found_id = result['id']

                if shared_state.search_string_in_sanitized_title(title, found_title):
                    imdb_id = found_id
                    break
    else:
        debug(f"Request on IMDb failed: {results.status_code}")

    recently_searched[title] = {
        "imdb_id": imdb_id,
        "timestamp": datetime.now()
    }
    shared_state.update(context, recently_searched)

    if not imdb_id:
        debug(f"No IMDb-ID found for {title}")

    return imdb_id
