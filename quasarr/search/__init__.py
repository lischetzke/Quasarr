# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import importlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone
from email.utils import parsedate_to_datetime

from quasarr.constants import (
    HOSTNAMES,
    HOSTNAMES_SUPPORTING_SEARCH_PHRASE,
    SEARCH_CAT_BOOKS,
    SEARCH_CAT_MOVIES,
    SEARCH_CAT_SHOWS,
)
from quasarr.providers.imdb_metadata import get_imdb_metadata
from quasarr.providers.log import debug, info, trace, warn
from quasarr.providers.utils import (
    determine_search_category,
)
from quasarr.storage.categories import get_search_category_sources


def get_search_results(
    shared_state,
    request_from,
    search_category,
    imdb_id="",
    search_phrase="",
    season="",
    episode="",
    offset=0,
    limit=1000,
):
    if imdb_id and not imdb_id.startswith("tt"):
        imdb_id = f"tt{imdb_id}"

    if imdb_id:
        get_imdb_metadata(imdb_id)

    # Determine search category if not provided
    if not search_category:
        search_category = determine_search_category(request_from)

    # Config retrieval
    config = shared_state.values["config"]("Hostnames")

    # Filter out sources that are not in the search category's whitelist
    whitelisted_sources = get_search_category_sources(search_category)

    if whitelisted_sources:
        debug(
            f"Using whitelist for category <g>{search_category}</g>: {', '.join([s.upper() for s in whitelisted_sources])}"
        )

    start_time = time.time()
    search_executor = SearchExecutor()

    # Build maps dynamically
    imdb_map = []
    phrase_map = []
    feed_map = []

    for source in HOSTNAMES:
        url = config.get(source)
        try:
            module = importlib.import_module(f"quasarr.search.sources.{source}")

            search_func = getattr(module, f"{source}_search", None)
            feed_func = getattr(module, f"{source}_feed", None)

            if search_func:
                imdb_map.append((source, url, search_func))
                if source in HOSTNAMES_SUPPORTING_SEARCH_PHRASE:
                    phrase_map.append((source, url, search_func))

            if feed_func:
                feed_map.append((source, url, feed_func))

        except ImportError:
            warn(f"Could not import search source: {source}")
        except Exception as e:
            warn(f"Error loading search source {source}: {e}")

    # Set up searches

    if imdb_id:
        stype = f"IMDb-ID <b>{imdb_id}</b>"
    elif search_phrase:
        stype = f"Search-Phrase <b>{search_phrase}</b>"
    else:
        stype = "<b>Feed</b> search"

    use_pagination = True

    if imdb_id:
        if search_category == SEARCH_CAT_MOVIES:
            args = (shared_state, start_time, search_category, imdb_id)
            kwargs = {}
            for name, url, func in imdb_map:
                if url and (not whitelisted_sources or name in whitelisted_sources):
                    search_executor.add(
                        func, args, kwargs, use_cache=True, source_name=name.upper()
                    )
        elif search_category == SEARCH_CAT_SHOWS:
            args = (shared_state, start_time, search_category, imdb_id)
            kwargs = {"season": season, "episode": episode}
            for name, url, func in imdb_map:
                if url and (not whitelisted_sources or name in whitelisted_sources):
                    search_executor.add(
                        func, args, kwargs, use_cache=True, source_name=name.upper()
                    )
        else:
            warn(
                f"{stype} is not supported for {request_from}, category: {search_category}"
            )

    elif search_phrase:
        if search_category == SEARCH_CAT_BOOKS:
            args = (shared_state, start_time, search_category, search_phrase)
            kwargs = {}
            for name, url, func in phrase_map:
                if url and (not whitelisted_sources or name in whitelisted_sources):
                    search_executor.add(func, args, kwargs, source_name=name.upper())
        else:
            warn(
                f"{stype} is not supported for {request_from}, category: {search_category}"
            )

    else:
        args = (shared_state, start_time, search_category)
        kwargs = {}
        use_pagination = False
        for name, url, func in feed_map:
            if url and (not whitelisted_sources or name in whitelisted_sources):
                search_executor.add(func, args, kwargs, source_name=name.upper())

    debug(f"Starting <g>{len(search_executor.searches)}</g> searches for {stype}...")

    # Unpack the new return values (all_cached, min_ttl)
    results, status_bar, all_cached, min_ttl = search_executor.run_all()

    elapsed_time = time.time() - start_time

    # Sort results by date (newest first)
    def get_date(item):
        try:
            dt = parsedate_to_datetime(item.get("details", {}).get("date", ""))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return parsedate_to_datetime("Thu, 01 Jan 1970 00:00:00 +0000")

    results.sort(key=get_date, reverse=True)

    # Calculate pagination for logging and return
    total_count = len(results)

    # Slicing
    if use_pagination:
        sliced_results = results[offset : offset + limit]
    else:
        sliced_results = results

    if sliced_results:
        trace(f"First {len(sliced_results)} results sorted by date:")
        for i, res in enumerate(sliced_results):
            details = res.get("details", {})
            trace(f"{i + 1}. {details.get('date')} | {details.get('title')}")

    # Formatting for log (1-based index for humans)
    log_start = min(offset + 1, total_count) if total_count > 0 else 0
    log_end = min(offset + limit, total_count) if use_pagination else total_count

    # Logic to switch between "Time taken" and "from cache"
    if all_cached:
        time_info = f"from cache ({int(min_ttl)}s left)"
    else:
        time_info = f"Time taken: {elapsed_time:.2f} seconds"

    info(
        f"Providing releases <g>{log_start}-{log_end}</g> of <g>{total_count}</g> to <d>{request_from}</d> "
        f"for {stype}{status_bar} <blue>{time_info}</blue>"
    )

    return sliced_results


class SearchExecutor:
    def __init__(self):
        self.searches = []

    def add(self, func, args, kwargs, use_cache=False, source_name=None):
        key_args = list(args)
        key_args[1] = None
        key_args = tuple(key_args)
        key = hash((func.__name__, key_args, frozenset(kwargs.items())))
        self.searches.append(
            (
                key,
                lambda: func(*args, **kwargs),
                use_cache,
                source_name or func.__name__,
            )
        )

    def run_all(self):
        results = []
        future_to_meta = {}

        # Track cache state
        all_cached = len(self.searches) > 0
        min_ttl = float("inf")
        bar_str = ""  # Initialize to prevent UnboundLocalError on full cache

        with ThreadPoolExecutor() as executor:
            current_index = 0
            pending_futures = []

            for key, func, use_cache, source_name in self.searches:
                cached_result = None
                exp = 0

                if use_cache:
                    # Get both result and expiry
                    cached_result, exp = search_cache.get(key)

                if cached_result is not None:
                    debug(f"Using cached result for {key}")
                    results.extend(cached_result)

                    # Calculate TTL for this cached item
                    ttl = exp - time.time()
                    if ttl < min_ttl:
                        min_ttl = ttl
                else:
                    all_cached = False
                    future = executor.submit(func)
                    cache_key = key if use_cache else None
                    future_to_meta[future] = (current_index, cache_key, source_name)
                    pending_futures.append(future)
                    current_index += 1

            if pending_futures:
                results_badges = [""] * len(pending_futures)

                for future in as_completed(pending_futures):
                    index, cache_key, source_name = future_to_meta[future]
                    try:
                        res = future.result()
                        if res and len(res) > 0:
                            badge = f"<bg green><black>{source_name}</black></bg green>"
                        else:
                            debug(f"❌ No results returned by <g>{source_name}</g>")
                            badge = f"<bg black><white>{source_name}</white></bg black>"

                        results_badges[index] = badge
                        results.extend(res)
                        if cache_key:
                            search_cache.set(cache_key, res)
                    except Exception as e:
                        results_badges[index] = (
                            f"<bg red><white>{source_name}</white></bg red>"
                        )
                        info(f"Search error: {e}")

                bar_str = f" [{' '.join(results_badges)}]"

        return results, bar_str, all_cached, min_ttl


class SearchCache:
    def __init__(self):
        self.last_cleaned = time.time()
        self.cache = {}

    def clean(self, now):
        if now - self.last_cleaned < 60:
            return
        keys_to_delete = [k for k, (_, exp) in self.cache.items() if now >= exp]
        for k in keys_to_delete:
            del self.cache[k]
        self.last_cleaned = now

    def get(self, key):
        val, exp = self.cache.get(key, (None, 0))
        # Return tuple (value, expiry) if valid, else (None, 0)
        return (val, exp) if time.time() < exp else (None, 0)

    def set(self, key, value, ttl=300):
        now = time.time()
        self.cache[key] = (value, now + ttl)
        self.clean(now)


search_cache = SearchCache()
