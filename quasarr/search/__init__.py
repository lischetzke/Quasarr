# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import datetime
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from quasarr.providers.imdb_metadata import get_imdb_metadata
from quasarr.providers.log import add_sink, debug, info
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

# Global lock to ensure only ONE progress bar is active at a time.
SEARCH_UI_LOCK = threading.Lock()


class SearchProgressBar:
    def __init__(self, total, description, silent=False):
        self.total = total
        self.description = description
        self.silent = silent
        self.slots = ["▪️"] * total
        self.finished_count = 0
        self.stream = sys.__stdout__
        self.lock = threading.Lock()

        # Only draw immediately if NOT silent (active bar)
        if not self.silent:
            self._draw()

    def _get_timestamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _draw(self):
        """Draws the dynamic bar to stdout (Active Mode only)."""
        if self.silent:
            return

        bar_str = "".join(self.slots)
        if self.total > 0:
            percent = int((self.finished_count / self.total) * 100)
        else:
            percent = 100

        ts = self._get_timestamp()

        # FIXED: Changed \x1b[32m (Green) to \x1b[1m (Bold) to match default Loguru INFO style
        # \x1b[2m = Dim (Timestamp)
        # \x1b[1m = Bold (INFO level)
        # \x1b[0m = Reset
        prefix = f"\x1b[2m{ts}\x1b[0m \x1b[1mINFO \x1b[0m 🔍    "
        message = f"{self.description} [{bar_str}] {percent}%"

        self.stream.write(f"\r\x1b[K{prefix} {message}")
        self.stream.flush()

    def get_status_message(self):
        """Returns the formatted string for logging (Silent/Fallback Mode)."""
        bar_str = "".join(self.slots)
        if self.total > 0:
            percent = int((self.finished_count / self.total) * 100)
        else:
            percent = 100
        # We omit the 🔍 icon here because info() adds it automatically
        return f"{self.description} [{bar_str}] {percent}%"

    def update(self, index, status):
        """Update slot status and redraw."""
        with self.lock:
            icon_map = {"found": "✅", "empty": "⚪", "error": "❌"}
            self.slots[index] = icon_map.get(status, "?")
            self.finished_count += 1
            if not self.silent:
                self._draw()

    def update_silent(self, index, status):
        """Update slot status WITHOUT redrawing (for background threads)."""
        with self.lock:
            icon_map = {"found": "✅", "empty": "⚪", "error": "❌"}
            self.slots[index] = icon_map.get(status, "?")
            self.finished_count += 1

    def finish(self):
        if self.silent:
            return
        with self.lock:
            self.stream.write("\n")
            self.stream.flush()

    def log_sink(self, message):
        """Sink for intercepting other logs while active."""
        if self.silent:
            return
        with self.lock:
            self.stream.write("\r\x1b[K")
            self.stream.write(message.rstrip() + "\n")
            self._draw()


class CaptureLogs:
    def __init__(self, progress_bar):
        self.progress_bar = progress_bar
        self.init = False

    def __enter__(self):
        add_sink(self.progress_bar.log_sink)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        add_sink()


def get_search_results(
    shared_state,
    request_from,
    imdb_id="",
    search_phrase="",
    mirror=None,
    season="",
    episode="",
):
    if imdb_id and not imdb_id.startswith("tt"):
        imdb_id = f"tt{imdb_id}"

    if imdb_id:
        get_imdb_metadata(imdb_id)

    docs_search = "lazylibrarian" in request_from.lower()

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
    imdb_map = [
        (al, al_search),
        (by, by_search),
        (dd, dd_search),
        (dl, dl_search),
        (dt, dt_search),
        (dj, dj_search),
        (dw, dw_search),
        (fx, fx_search),
        (he, he_search),
        (hs, hs_search),
        (mb, mb_search),
        (nk, nk_search),
        (nx, nx_search),
        (sf, sf_search),
        (sj, sj_search),
        (sl, sl_search),
        (wd, wd_search),
        (wx, wx_search),
    ]

    phrase_map = [
        (by, by_search),
        (dl, dl_search),
        (dt, dt_search),
        (nx, nx_search),
        (sl, sl_search),
        (wd, wd_search),
    ]

    feed_map = [
        (al, al_feed),
        (by, by_feed),
        (dd, dd_feed),
        (dj, dj_feed),
        (dl, dl_feed),
        (dt, dt_feed),
        (dw, dw_feed),
        (fx, fx_feed),
        (he, he_feed),
        (hs, hs_feed),
        (mb, mb_feed),
        (nk, nk_feed),
        (nx, nx_feed),
        (sf, sf_feed),
        (sj, sj_feed),
        (sl, sl_feed),
        (wd, wd_feed),
        (wx, wx_feed),
    ]

    # Add searches
    if imdb_id:
        args, kwargs = (
            (shared_state, start_time, request_from, imdb_id),
            {"mirror": mirror, "season": season, "episode": episode},
        )
        for flag, func in imdb_map:
            if flag:
                search_executor.add(func, args, kwargs, True)

    elif search_phrase and docs_search:
        args, kwargs = (
            (shared_state, start_time, request_from, search_phrase),
            {"mirror": mirror, "season": season, "episode": episode},
        )
        for flag, func in phrase_map:
            if flag:
                search_executor.add(func, args, kwargs)

    elif search_phrase:
        debug(f"Search phrase '{search_phrase}' is not supported for {request_from}.")

    else:
        args, kwargs = ((shared_state, start_time, request_from), {"mirror": mirror})
        for flag, func in feed_map:
            if flag:
                search_executor.add(func, args, kwargs)

    # Clean description for Console UI
    if imdb_id:
        desc_text = f"Searching for IMDb-ID {imdb_id}"
        stype = f"IMDb-ID <b>{imdb_id}</b>"
    elif search_phrase:
        desc_text = f"Searching for '{search_phrase}'"
        stype = f"Search-Phrase <b>{search_phrase}</b>"
    else:
        desc_text = "Running Feed Search"
        stype = "<b>feed</b> search"

    results = search_executor.run_all(desc_text)

    elapsed_time = time.time() - start_time
    info(
        f"Providing <g>{len(results)} releases</g> to <d>{request_from}</d> for {stype}. <blue>Time taken: {elapsed_time:.2f} seconds</blue>"
    )

    return results


class SearchExecutor:
    def __init__(self):
        self.searches = []

    def add(self, func, args, kwargs, use_cache=False):
        key_args = list(args)
        key_args[1] = None
        key_args = tuple(key_args)
        key = hash((func.__name__, key_args, frozenset(kwargs.items())))
        self.searches.append((key, lambda: func(*args, **kwargs), use_cache))

    def run_all(self, description):
        results = []
        future_to_meta = {}

        with ThreadPoolExecutor() as executor:
            current_index = 0
            pending_futures = []
            cache_used = False

            for key, func, use_cache in self.searches:
                cached_result = None
                if use_cache:
                    cached_result = search_cache.get(key)

                if cached_result is not None:
                    debug(f"Using cached result for {key}")
                    cache_used = True
                    results.extend(cached_result)
                else:
                    future = executor.submit(func)
                    cache_key = key if use_cache else None
                    future_to_meta[future] = (current_index, cache_key)
                    pending_futures.append(future)
                    current_index += 1

            total_active = len(pending_futures)

            # Try to acquire lock non-blocking
            lock_acquired = SEARCH_UI_LOCK.acquire(blocking=False)

            try:
                # Update description with count
                full_desc = f"{description} ({total_active} hostnames)"

                if lock_acquired and total_active > 0:
                    # === ACTIVE MODE ===
                    # Shows dynamic bar with \r updates
                    progress = SearchProgressBar(total_active, full_desc, silent=False)

                    try:
                        with CaptureLogs(progress):
                            for future in as_completed(pending_futures):
                                index, cache_key = future_to_meta[future]
                                try:
                                    res = future.result()
                                    status = (
                                        "found" if res and len(res) > 0 else "empty"
                                    )
                                    progress.update(index, status)

                                    results.extend(res)
                                    if cache_key:
                                        search_cache.set(cache_key, res)
                                except Exception as e:
                                    progress.update(index, "error")
                                    info(f"Search error: {e}")
                    finally:
                        progress.finish()

                else:
                    # === FALLBACK MODE ===
                    # Shows 0% log -> waits -> Shows 100% log
                    if total_active > 0:
                        fallback_bar = SearchProgressBar(
                            total_active, full_desc, silent=True
                        )

                        # Log the "0%" state immediately
                        info(fallback_bar.get_status_message())

                        for future in as_completed(pending_futures):
                            index, cache_key = future_to_meta[future]
                            try:
                                res = future.result()
                                status = "found" if res and len(res) > 0 else "empty"

                                # Silent update to track status for the final log
                                fallback_bar.update_silent(index, status)

                                results.extend(res)
                                if cache_key:
                                    search_cache.set(cache_key, res)
                            except Exception as e:
                                fallback_bar.update_silent(index, "error")
                                info(f"Search error: {e}")

                        # Log the "100%" state at the end
                        info(fallback_bar.get_status_message())
                    else:
                        pass

            finally:
                if lock_acquired:
                    SEARCH_UI_LOCK.release()

            if cache_used:
                info("Presenting cached results for some items.")

        return results


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
        return val if time.time() < exp else None

    def set(self, key, value, ttl=300):
        now = time.time()
        self.cache[key] = (value, now + ttl)
        self.clean(now)


search_cache = SearchCache()
