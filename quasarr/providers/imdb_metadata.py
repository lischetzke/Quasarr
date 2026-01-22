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


class IMDbAPI:
    """Handles interactions with api.imdbapi.dev"""
    BASE_URL = "https://api.imdbapi.dev"

    @staticmethod
    def get_title(imdb_id):
        try:
            response = requests.get(f"{IMDbAPI.BASE_URL}/titles/{imdb_id}", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            info(f"Error loading imdbapi.dev for {imdb_id}: {e}")
            return None

    @staticmethod
    def get_akas(imdb_id):
        try:
            response = requests.get(f"{IMDbAPI.BASE_URL}/titles/{imdb_id}/akas", timeout=30)
            response.raise_for_status()
            return response.json().get("akas", [])
        except Exception as e:
            info(f"Error loading localized titles from IMDbAPI.dev for {imdb_id}: {e}")
            return []

    @staticmethod
    def search_titles(query):
        try:
            response = requests.get(f"{IMDbAPI.BASE_URL}/search/titles?query={quote(query)}&limit=5", timeout=30)
            response.raise_for_status()
            return response.json().get("titles", [])
        except Exception as e:
            debug(f"Request on IMDbAPI failed: {e}")
            return []


class IMDbWeb:
    """Handles fallback interactions by scraping imdb.com"""
    BASE_URL = "https://www.imdb.com"

    @staticmethod
    def get_poster(imdb_id, user_agent):
        headers = {'User-Agent': user_agent}
        try:
            request = requests.get(f"{IMDbWeb.BASE_URL}/title/{imdb_id}/", headers=headers, timeout=10).text
            soup = BeautifulSoup(request, "html.parser")
            poster_set = soup.find('div', class_='ipc-poster').div.img["srcset"]
            poster_links = [x for x in poster_set.split(" ") if len(x) > 10]
            return poster_links[-1]
        except Exception as e:
            debug(f"Could not get poster title for {imdb_id} from IMDb: {e}")
            return None

    @staticmethod
    def get_localized_title(imdb_id, language, user_agent):
        headers = {
            'Accept-Language': language,
            'User-Agent': user_agent
        }
        try:
            response = requests.get(f"{IMDbWeb.BASE_URL}/title/{imdb_id}/", headers=headers, timeout=10)
            response.raise_for_status()

            match = re.search(r'<title>(.*?) \(.*?</title>', response.text)
            if not match:
                match = re.search(r'<title>(.*?) - IMDb</title>', response.text)

            if match:
                return match.group(1)
        except Exception as e:
            info(f"Error loading IMDb metadata for {imdb_id}: {e}")

        return None

    @staticmethod
    def search_titles(query, ttype, language, user_agent):
        headers = {
            'Accept-Language': language,
            'User-Agent': user_agent
        }
        try:
            results = requests.get(f"{IMDbWeb.BASE_URL}/find/?q={quote(query)}&s=tt&ttype={ttype}&ref_=fn_{ttype}",
                                   headers=headers, timeout=10)

            if results.status_code == 200:
                soup = BeautifulSoup(results.text, "html.parser")
                props = soup.find("script", text=re.compile("props"))
                if props:
                    details = loads(props.string)
                    return details['props']['pageProps']['titleResults']['results']
            else:
                debug(f"Request on IMDb failed: {results.status_code}")
        except Exception as e:
            debug(f"IMDb scraping fallback failed: {e}")

        return []


class TitleCleaner:
    @staticmethod
    def sanitize(title):
        if not title:
            return ""
        sanitized_title = html.unescape(title)
        sanitized_title = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß&-']", ' ', sanitized_title).strip()
        sanitized_title = sanitized_title.replace(" - ", "-")
        sanitized_title = re.sub(r'\s{2,}', ' ', sanitized_title)
        return sanitized_title

    @staticmethod
    def clean(title):
        try:
            # Regex to find the title part before common release tags
            # Stops at:
            # - Year (19xx or 20xx) preceded by a separator
            # - Language tags (.German, .GERMAN)
            # - Resolution (.1080p, .720p, etc.)
            # - Season info (.S01)
            pattern = r"(.*?)(?:[\.\s](?!19|20)\d{2}|[\.\s]German|[\.\s]GERMAN|[\.\s]\d{3,4}p|[\.\s]S(?:\d{1,3}))"
            match = re.search(pattern, title)
            if match:
                extracted_title = match.group(1)
            else:
                extracted_title = title

            # Remove specific tags that might appear in the title part
            tags_to_remove = [
                r'[\.\s]UNRATED.*', r'[\.\s]Unrated.*', r'[\.\s]Uncut.*', r'[\.\s]UNCUT.*',
                r'[\.\s]Directors[\.\s]Cut.*', r'[\.\s]Final[\.\s]Cut.*', r'[\.\s]DC.*',
                r'[\.\s]REMASTERED.*', r'[\.\s]EXTENDED.*', r'[\.\s]Extended.*',
                r'[\.\s]Theatrical.*', r'[\.\s]THEATRICAL.*'
            ]

            clean_title = extracted_title
            for tag in tags_to_remove:
                clean_title = re.sub(tag, "", clean_title, flags=re.IGNORECASE)

            clean_title = clean_title.replace(".", " ").strip()
            clean_title = re.sub(r'\s+', ' ', clean_title)  # Remove multiple spaces
            clean_title = clean_title.replace(" ", "+")

            return clean_title
        except Exception as e:
            debug(f"Error cleaning title '{title}': {e}")
            return title


def get_poster_link(shared_state, imdb_id):
    imdb_metadata = get_imdb_metadata(imdb_id)
    if imdb_metadata:
        poster_link = imdb_metadata.get("poster_link")
        if poster_link:
            return poster_link

    poster_link = None
    if imdb_id:
        poster_link = IMDbWeb.get_poster(imdb_id, shared_state.values["user_agent"])

    if not poster_link:
        debug(f"Could not get poster title for {imdb_id} from IMDb")

    return poster_link


def get_imdb_metadata(imdb_id):
    db = _get_db("imdb_metadata")
    now = datetime.now().timestamp()

    # Try to load from DB
    cached_metadata = None
    try:
        cached_data = db.retrieve(imdb_id)
        if cached_data:
            cached_metadata = loads(cached_data)
            # If valid, update TTL and return
            if cached_metadata.get("ttl") and cached_metadata["ttl"] > now:
                return cached_metadata
    except Exception as e:
        debug(f"Error retrieving IMDb metadata from DB for {imdb_id}: {e}")

    # Initialize new metadata structure
    imdb_metadata = {
        "title": None,
        "year": None,
        "poster_link": None,
        "localized": {},
        "ttl": 0
    }

    # Fetch from API
    response_json = IMDbAPI.get_title(imdb_id)

    if not response_json:
        # API failed. If we have stale cached data, return it as fallback
        if cached_metadata:
            debug(f"IMDb API failed for {imdb_id}, returning stale cached data.")
            return cached_metadata
        return imdb_metadata

    # Process API response
    imdb_metadata["title"] = TitleCleaner.sanitize(response_json.get("primaryTitle", ""))
    imdb_metadata["year"] = response_json.get("startYear")
    imdb_metadata["ttl"] = now + timedelta(days=7).total_seconds()

    try:
        imdb_metadata["poster_link"] = response_json.get("primaryImage").get("url")
    except Exception as e:
        debug(f"Could not find poster link for {imdb_id} from imdbapi.dev: {e}")
        # Shorten TTL if data is incomplete
        imdb_metadata["ttl"] = now + timedelta(days=1).total_seconds()

    akas = IMDbAPI.get_akas(imdb_id)
    if akas:
        for aka in akas:
            if aka.get("language"):
                continue  # skip entries with specific language tags
            if aka.get("country", {}).get("code", "").lower() == "de":
                imdb_metadata["localized"]["de"] = TitleCleaner.sanitize(aka.get("text"))
                break
    else:
        # Shorten TTL if AKAs failed
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

    localized_title = IMDbWeb.get_localized_title(imdb_id, language, shared_state.values["user_agent"])

    if not localized_title:
        debug(f"Could not get localized title for {imdb_id} in {language} from IMDb")
    else:
        localized_title = TitleCleaner.sanitize(localized_title)
    return localized_title


def get_imdb_id_from_title(shared_state, title, language="de"):
    imdb_id = None

    if re.search(r"S\d{1,3}(E\d{1,3})?", title, re.IGNORECASE):
        ttype_api = "TV_SERIES"
        ttype_web = "tv"
    else:
        ttype_api = "MOVIE"
        ttype_web = "ft"

    title = TitleCleaner.clean(title)

    # Check Search Cache (DB)
    db = _get_db("imdb_searches")
    try:
        cached_data = db.retrieve(title)
        if cached_data:
            data = loads(cached_data)
            # Check TTL (48 hours)
            if data.get("timestamp") and datetime.fromtimestamp(data["timestamp"]) > datetime.now() - timedelta(
                    hours=48):
                return data.get("imdb_id")
    except Exception as e:
        debug(f"Error retrieving search cache for {title}: {e}")

    # Try IMDbAPI.dev first
    search_results = IMDbAPI.search_titles(title)
    if search_results:
        for result in search_results:
            found_title = result.get("primaryTitle")
            found_id = result.get("id")
            found_type = result.get("type")

            # Basic type filtering if possible from result data
            if ttype_api == "TV_SERIES" and found_type not in ["tvSeries", "tvMiniSeries"]:
                continue
            if ttype_api == "MOVIE" and found_type not in ["movie", "tvMovie"]:
                continue

            if shared_state.search_string_in_sanitized_title(title, found_title):
                imdb_id = found_id
                break

        # If no exact match found with type filtering, try relaxed matching
        if not imdb_id:
            for result in search_results:
                found_title = result.get("primaryTitle")
                found_id = result.get("id")
                if shared_state.search_string_in_sanitized_title(title, found_title):
                    imdb_id = found_id
                    break

    # Fallback to IMDb scraping if API failed or returned no results
    if not imdb_id:
        search_results = IMDbWeb.search_titles(title, ttype_web, language, shared_state.values["user_agent"])
        if search_results:
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

    # Update Search Cache
    try:
        db.update_store(title, dumps({
            "imdb_id": imdb_id,
            "timestamp": datetime.now().timestamp()
        }))
    except Exception as e:
        debug(f"Error updating search cache for {title}: {e}")

    if not imdb_id:
        debug(f"No IMDb-ID found for {title}")

    return imdb_id
