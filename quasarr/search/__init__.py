# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone
from email.utils import parsedate_to_datetime

from quasarr.providers.imdb_metadata import get_imdb_metadata
from quasarr.providers.log import debug, info, trace, warn
from quasarr.providers.utils import (
    SEARCH_CAT_BOOKS,
    SEARCH_CAT_MOVIES,
    SEARCH_CAT_SHOWS,
    determine_search_category,
)
from quasarr.search.sources.al import al_feed, al_search
from quasarr.search.sources.by import by_feed, by_search
from quasarr.search.sources.dd import dd_feed, dd_search
from quasarr.search.sources.dj import dj_feed, dj_search
from quasarr.search.sources.dl import dl_feed, dl_search
from quasarr.search.sources.dt import dt_feed, dt_search
from quasarr.search.sources.dw import dw_feed, dw_search
from quasarr.search.sources.fx import fx_feed, fx_search
from quasarr.search.sources.he import he_feed, he_search
from quasarr.search.sources.hs import hs_feed, hs_search
from quasarr.search.sources.mb import mb_feed, mb_search
from quasarr.search.sources.nk import nk_feed, nk_search
from quasarr.search.sources.nx import nx_feed, nx_search
from quasarr.search.sources.sf import sf_feed, sf_search
from quasarr.search.sources.sj import sj_feed, sj_search
from quasarr.search.sources.sl import sl_feed, sl_search
from quasarr.search.sources.wd import wd_feed, wd_search
from quasarr.search.sources.wx import wx_feed, wx_search


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
    al = config.get("al")
    by = config.get("by")
    dd = config.get("dd")
    dl = config.get("dl")
    dt = config.get("dt")
    dj = config.get("dj")
    dw = config.get("dw")
    fx = config.get("fx")
    he = config.get("he")
    hs = config.get("hs")
    mb = config.get("mb")
    nk = config.get("nk")
    nx = config.get("nx")
    sf = config.get("sf")
    sj = config.get("sj")
    sl = config.get("sl")
    wd = config.get("wd")
    wx = config.get("wx")

    start_time = time.time()
    search_executor = SearchExecutor()

    # Mappings
    imdb_movies_map = [
        ("al", al, al_search),
        ("by", by, by_search),
        ("dd", dd, dd_search),
        ("dl", dl, dl_search),
        ("dt", dt, dt_search),
        ("dw", dw, dw_search),
        ("fx", fx, fx_search),
        ("he", he, he_search),
        ("hs", hs, hs_search),
        ("mb", mb, mb_search),
        ("nk", nk, nk_search),
        ("nx", nx, nx_search),
        ("sl", sl, sl_search),
        ("wd", wd, wd_search),
        ("wx", wx, wx_search),
    ]

    imdb_shows_map = [
        ("al", al, al_search),
        ("by", by, by_search),
        ("dd", dd, dd_search),
        ("dl", dl, dl_search),
        ("dt", dt, dt_search),
        ("dj", dj, dj_search),
        ("dw", dw, dw_search),
        ("fx", fx, fx_search),
        ("he", he, he_search),
        ("hs", hs, hs_search),
        ("mb", mb, mb_search),
        ("nk", nk, nk_search),
        ("nx", nx, nx_search),
        ("sf", sf, sf_search),
        ("sj", sj, sj_search),
        ("sl", sl, sl_search),
        ("wd", wd, wd_search),
        ("wx", wx, wx_search),
    ]

    phrase_map = [
        ("by", by, by_search),
        ("dl", dl, dl_search),
        ("dt", dt, dt_search),
        ("nx", nx, nx_search),
        ("sl", sl, sl_search),
        ("wd", wd, wd_search),
    ]

    feed_map = [
        ("al", al, al_feed),
        ("by", by, by_feed),
        ("dd", dd, dd_feed),
        ("dj", dj, dj_feed),
        ("dl", dl, dl_feed),
        ("dt", dt, dt_feed),
        ("dw", dw, dw_feed),
        ("fx", fx, fx_feed),
        ("he", he, he_feed),
        ("hs", hs, hs_feed),
        ("mb", mb, mb_feed),
        ("nk", nk, nk_feed),
        ("nx", nx, nx_feed),
        ("sf", sf, sf_feed),
        ("sj", sj, sj_feed),
        ("sl", sl, sl_feed),
        ("wd", wd, wd_feed),
        ("wx", wx, wx_feed),
    ]

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
            for name, url, func in imdb_movies_map:
                if url:
                    search_executor.add(
                        func, args, kwargs, use_cache=True, source_name=name.upper()
                    )
        elif search_category == SEARCH_CAT_SHOWS:
            args = (shared_state, start_time, search_category, imdb_id)
            kwargs = {"season": season, "episode": episode}
            for name, url, func in imdb_shows_map:
                if url:
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
                if url:
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
            if url:
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
