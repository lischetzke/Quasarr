# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import argparse
import concurrent.futures
import os
import re
import sys
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
from base64 import urlsafe_b64decode
from datetime import datetime
from html import escape
from urllib.parse import urlparse

import requests

# Try importing dependencies
try:
    import questionary
    from prompt_toolkit import Application, PromptSession
    from prompt_toolkit.formatted_text import HTML, to_formatted_text
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.layout import Layout
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
    )
    from rich.table import Table
except ImportError:
    print("Please install 'rich' and 'questionary' to use this tool.")
    print("uv sync --group dev")
    sys.exit(1)

from dotenv import load_dotenv

load_dotenv(override=True)

# --- Configuration & Constants ---
DEFAULT_URL = "http://localhost:8080"
USER_AGENT_RADARR = "Radarr/3.0.0.0 (Mock Client for Testing)"
USER_AGENT_SONARR = "Sonarr/3.0.0.0 (Mock Client for Testing)"
USER_AGENT_LIDARR = "Lidarr/3.0.0.0 (Mock Client for Testing)"
USER_AGENT_LL = "LazyLibrarian/1.7.0 (Mock Client for Testing)"

console = Console()
IS_TTY = sys.stdin.isatty()


class Status:
    def __init__(self):
        self.text = ""


# --- Custom Loading Screen ---
class LoadingScreen:
    def __init__(self, title, func, *args, status_obj=None, **kwargs):
        """
        Runs 'func' in a separate thread while showing a spinner.
        Allows cancellation via Left/Backspace.
        Uses threading instead of asyncio to avoid RuntimeWarnings.
        """
        self.title = title
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.status_obj = status_obj

        # Spinner animation frames
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.start_time = time.time()

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.cancelled = False
        self.app = None

    def get_text(self):
        # Calculate frame based on elapsed time
        frame_idx = int((time.time() - self.start_time) * 10) % len(self.frames)
        spinner = self.frames[frame_idx]

        lines = []
        lines.append(
            HTML(f"<b><ansicyan>--- {escape(self.title.upper())} ---</ansicyan></b>")
        )
        lines.append(HTML("<grey>Keys: [Backspace/←] Cancel Operation</grey>"))
        lines.append(HTML(""))

        if self.cancelled:
            lines.append(HTML("<ansired>❌ Cancelled by user.</ansired>"))
        elif self.future and self.future.done():
            lines.append(HTML("<ansigreen>✔ Done.</ansigreen>"))
        else:
            lines.append(
                HTML(f"<ansigreen>{spinner} Processing request...</ansigreen>")
            )

        if self.status_obj and self.status_obj.text:
            # Escape text to prevent XML parsing errors
            safe_text = escape(self.status_obj.text)
            lines.append(HTML(f"<grey>{safe_text}</grey>"))

        result = []
        for line in lines:
            result.extend(to_formatted_text(line))
            result.append(("", "\n"))
        return result

    def _monitor_task(self):
        """
        Runs in a background thread. Monitors the future and exits the app when done.
        """
        while not self.cancelled:
            if self.future.done():
                try:
                    result = self.future.result()
                except Exception:
                    result = None

                # Signal the app to exit
                if self.app and self.app.is_running:
                    self.app.exit(result=result)
                break
            time.sleep(0.1)

    def run(self):
        kb = KeyBindings()

        @kb.add(Keys.Backspace)
        @kb.add(Keys.Left)
        def _(event):
            self.cancelled = True
            event.app.exit(result=None)

        @kb.add(Keys.ControlC)
        def _(event):
            sys.exit(0)

        text_control = FormattedTextControl(text=self.get_text, show_cursor=False)
        layout = Layout(HSplit([Window(content=text_control)]))

        # refresh_interval is critical here to keep the spinner animating
        self.app = Application(
            layout=layout, key_bindings=kb, full_screen=False, refresh_interval=0.1
        )

        # 1. Start the actual work
        self.future = self.executor.submit(self.func, *self.args, **self.kwargs)

        # 2. Start the monitor thread (daemon ensures it dies if main app dies)
        monitor_thread = threading.Thread(target=self._monitor_task, daemon=True)
        monitor_thread.start()

        # 3. Block until app.exit() is called
        return self.app.run()


# --- Custom Paginated Selector ---
class PaginatedSelector:
    def __init__(
        self,
        title,
        items,
        page_size=10,
        initial_index=0,
        duration=None,
        allowed_sorts=None,
    ):
        self.title = title
        self.original_items = list(items)  # Keep a copy of original order
        self.items = items
        self.page_size = page_size
        self.selected_index = min(initial_index, len(items) - 1) if items else 0
        self.result = None
        self.cancelled = False
        self.duration = duration

        # Define all possible sort logic
        # Key: (Display Label, Sort Function)
        self.all_sort_logic = {
            "newest": (
                "Newest",
                lambda: (
                    self.items[:]
                    if not self.original_items
                    else list(self.original_items)
                ),
            ),
            "oldest": ("Oldest", lambda: list(reversed(self.original_items))),
            "a-z": ("A-Z", lambda: sorted(self.items, key=lambda x: x[0])),
            "z-a": (
                "Z-A",
                lambda: sorted(self.items, key=lambda x: x[0], reverse=True),
            ),
            "size_desc": (
                "Size ⬇",
                lambda: sorted(self.items, key=self._get_size_key, reverse=True),
            ),
            "size_asc": ("Size ⬆", lambda: sorted(self.items, key=self._get_size_key)),
        }

        # If no specific sorts provided, default to full list
        if allowed_sorts is None:
            self.allowed_sorts = [
                "newest",
                "a-z",
                "z-a",
                "size_desc",
                "size_asc",
                "oldest",
            ]
        else:
            self.allowed_sorts = allowed_sorts

        self.sort_index = 0
        # If "newest" isn't available, apply the first allowed sort immediately
        if self.allowed_sorts and self.allowed_sorts[0] != "newest":
            self._apply_sort()

    def _get_size_key(self, item_tuple):
        # item_tuple is (label, dict)
        try:
            return float(item_tuple[1].get("size", 0))
        except (ValueError, TypeError):
            return 0

    def _apply_sort(self):
        if not self.allowed_sorts:
            return

        current_sort_key = self.allowed_sorts[self.sort_index]
        if current_sort_key in self.all_sort_logic:
            _, sort_func = self.all_sort_logic[current_sort_key]
            self.items = sort_func()

        # Reset selection to top
        self.selected_index = 0

    def get_current_page_indices(self):
        page_idx = self.selected_index // self.page_size
        start = page_idx * self.page_size
        end = min(len(self.items), start + self.page_size)
        return start, end, page_idx

    def get_text(self):
        start, end, page_idx = self.get_current_page_indices()
        total_pages = max(1, (len(self.items) + self.page_size - 1) // self.page_size)

        lines = []
        lines.append(
            HTML(f"<b><ansicyan>--- {escape(self.title.upper())} ---</ansicyan></b>")
        )

        # Header with Sort Info
        current_sort_key = self.allowed_sorts[self.sort_index]
        sort_label = self.all_sort_logic.get(current_sort_key, ("Unknown",))[0]

        lines.append(
            HTML(
                f"<grey>Keys: [↑/↓] Nav | [Enter] Select | [Tab] Sort: <b>{escape(sort_label)}</b> | [Back] Exit</grey>"
            )
        )

        summary = f"Page {page_idx + 1}/{total_pages} (Total: {len(self.items)})"
        if self.duration is not None:
            summary += f" | Took {self.duration:.2f}s"

        lines.append(HTML(f"<i>{escape(summary)}</i>"))
        lines.append(HTML(""))

        for i in range(start, end):
            label, _ = self.items[i]
            safe_label = escape(label)

            if i == self.selected_index:
                lines.append(HTML(f"<reverse>  {safe_label}  </reverse>"))
            else:
                lines.append(HTML(f"  {safe_label}"))

        lines_used = end - start
        if lines_used < self.page_size:
            for _ in range(self.page_size - lines_used):
                lines.append(HTML(""))

        result = []
        for line in lines:
            result.extend(to_formatted_text(line))
            result.append(("", "\n"))

        return result

    def run(self):
        kb = KeyBindings()

        @kb.add(Keys.Up)
        @kb.add("k")
        def _(event):
            self.selected_index = max(0, self.selected_index - 1)

        @kb.add(Keys.Down)
        @kb.add("j")
        def _(event):
            self.selected_index = min(len(self.items) - 1, self.selected_index + 1)

        @kb.add(Keys.Left)
        @kb.add("h")
        def _(event):
            page_idx = self.selected_index // self.page_size
            if page_idx == 0:
                self.cancelled = True
                event.app.exit()
            else:
                new_idx = self.selected_index - self.page_size
                self.selected_index = max(0, new_idx)

        @kb.add(Keys.Right)
        @kb.add("l")
        def _(event):
            new_idx = self.selected_index + self.page_size
            if new_idx < len(self.items):
                self.selected_index = new_idx
            else:
                self.selected_index = len(self.items) - 1

        # Tab Binding for Sorting
        @kb.add(Keys.Tab)
        def _(event):
            if not self.allowed_sorts:
                return
            self.sort_index = (self.sort_index + 1) % len(self.allowed_sorts)
            self._apply_sort()

        @kb.add(Keys.Enter)
        def _(event):
            self.result = (self.items[self.selected_index][1], self.selected_index)
            event.app.exit()

        @kb.add(Keys.Backspace)
        def _(event):
            self.cancelled = True
            event.app.exit()

        @kb.add(Keys.ControlC)
        def _(event):
            sys.exit(0)

        text_control = FormattedTextControl(text=self.get_text, show_cursor=False)
        layout = Layout(HSplit([Window(content=text_control)]))
        app = Application(layout=layout, key_bindings=kb, full_screen=False)
        app.run()

        if self.cancelled:
            return None
        return self.result


# --- Custom Menu Selector ---
class MenuSelector:
    def __init__(self, title, items, allow_back=True):
        self.title = title
        self.items = items
        self.selected_index = 0
        self.result = None
        self.cancelled = False
        self.allow_back = allow_back

    def get_text(self):
        lines = []
        lines.append(
            HTML(f"<b><ansicyan>--- {escape(self.title.upper())} ---</ansicyan></b>")
        )

        if self.allow_back:
            lines.append(
                HTML(
                    "<grey>Keys: [↑/↓] Navigate | [Enter/→] Select | [Backspace/←] Back</grey>"
                )
            )
        else:
            lines.append(
                HTML(
                    "<grey>Keys: [↑/↓] Navigate | [Enter/→] Select | [Ctrl+C] Quit</grey>"
                )
            )

        lines.append(HTML(""))

        for i, (label, _) in enumerate(self.items):
            safe_label = escape(label)
            if i == self.selected_index:
                lines.append(HTML(f"<reverse>  {safe_label}  </reverse>"))
            else:
                lines.append(HTML(f"  {safe_label}"))

        result = []
        for line in lines:
            result.extend(to_formatted_text(line))
            result.append(("", "\n"))
        return result

    def run(self):
        kb = KeyBindings()

        @kb.add(Keys.Up)
        @kb.add("k")
        def _(event):
            self.selected_index = max(0, self.selected_index - 1)

        @kb.add(Keys.Down)
        @kb.add("j")
        def _(event):
            self.selected_index = min(len(self.items) - 1, self.selected_index + 1)

        @kb.add(Keys.Enter)
        @kb.add(Keys.Right)
        @kb.add("l")
        def _(event):
            self.result = self.items[self.selected_index][1]
            event.app.exit()

        if self.allow_back:

            @kb.add(Keys.Backspace)
            @kb.add(Keys.Left)
            @kb.add("h")
            def _(event):
                self.cancelled = True
                event.app.exit()

        @kb.add(Keys.ControlC)
        def _(event):
            sys.exit(0)

        text_control = FormattedTextControl(text=self.get_text, show_cursor=False)
        layout = Layout(HSplit([Window(content=text_control)]))
        app = Application(layout=layout, key_bindings=kb, full_screen=False)
        app.run()

        if self.cancelled:
            return None
        return self.result


# --- Custom Text Input ---
class TextInput:
    def __init__(self, title, default="", validator=None):
        self.title = title
        self.default = default
        self.validator = validator

    def run(self):
        kb = KeyBindings()

        @kb.add(Keys.Escape)
        def _(event):
            event.app.exit(result=None)

        @kb.add("left")
        def _(event):
            if not event.current_buffer.text:
                event.app.exit(result=None)
            else:
                event.current_buffer.cursor_position = max(
                    0, event.current_buffer.cursor_position - 1
                )

        @kb.add("right")
        def _(event):
            buff = event.current_buffer
            if buff.cursor_position == len(buff.text):
                event.app.exit(result=buff.text)
            else:
                buff.cursor_position = min(len(buff.text), buff.cursor_position + 1)

        @kb.add("backspace")
        def _(event):
            if not event.current_buffer.text:
                event.app.exit(result=None)
            else:
                event.current_buffer.delete_before_cursor(1)

        session = PromptSession(key_bindings=kb)

        while True:
            try:
                prompt_text = HTML(
                    f"<b><ansicyan>--- {escape(self.title.upper())} ---</ansicyan></b>\n<grey>Keys: [Enter] Confirm | [Esc] Cancel</grey>\n[{escape(self.default)}]: "
                )
                result = session.prompt(prompt_text, default=self.default)

                if result is None:
                    return None

                if self.validator:
                    if self.validator(result):
                        return result
                    else:
                        clear_screen()
                        console.print(
                            "[bold red]Invalid input. Please try again.[/bold red]"
                        )
                        time.sleep(1)
                        continue
                return result
            except (KeyboardInterrupt, EOFError):
                return None


def press_any_key(message="Press any key to continue..."):
    kb = KeyBindings()

    def exit_app(event):
        event.app.exit()

    @kb.add("<any>")
    def _(event):
        exit_app(event)

    for key in [
        Keys.Up,
        Keys.Down,
        Keys.Left,
        Keys.Right,
        Keys.Enter,
        Keys.Backspace,
        Keys.Escape,
        Keys.Tab,
    ]:
        kb.add(key)(exit_app)

    text_control = FormattedTextControl(
        text=HTML(f"<grey>{escape(message)}</grey>"), show_cursor=False
    )
    layout = Layout(HSplit([Window(content=text_control, height=1)]))
    app = Application(layout=layout, key_bindings=kb, full_screen=False)
    app.run()


def validate_imdb(text):
    if text is None:
        return False
    return bool(re.match(r"^tt\d+$", text))


# --- API Client ---
class QuasarrClient:
    def __init__(self, url, api_key):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()

    def _get(self, params, user_agent):
        request_params = params.copy()
        request_params["apikey"] = self.api_key
        headers = {"User-Agent": user_agent}
        try:
            response = self.session.get(
                f"{self.url}/api", params=request_params, headers=headers, timeout=120
            )
            response.raise_for_status()
            return response
        except requests.RequestException:
            return None

    def get_downloads(self):
        q_resp = self._get({"mode": "queue"}, USER_AGENT_RADARR)
        h_resp = self._get({"mode": "history"}, USER_AGENT_RADARR)
        queue, history = [], []
        if q_resp:
            try:
                queue = q_resp.json().get("queue", {}).get("slots", [])
            except:
                pass
        if h_resp:
            try:
                history = h_resp.json().get("history", {}).get("slots", [])
            except:
                pass
        return queue, history

    def get_feed(self, feed_type):
        if feed_type == "movie":
            return self._parse_xml(
                self._get({"t": "movie", "cat": "2000"}, USER_AGENT_RADARR)
            )
        elif feed_type == "tv":
            return self._parse_xml(
                self._get({"t": "tvsearch", "cat": "5000"}, USER_AGENT_SONARR)
            )
        elif feed_type == "music":
            return self._parse_xml(
                self._get({"t": "music", "cat": "3000"}, USER_AGENT_LIDARR)
            )
        elif feed_type == "doc":
            return self._parse_xml(
                self._get({"t": "book", "cat": "7000"}, USER_AGENT_LL)
            )
        return []

    def search_movie(self, imdb_id):
        return self._fetch_all_results(
            {"t": "movie", "imdbid": imdb_id, "cat": "2000"}, USER_AGENT_RADARR
        )

    def search_tv(self, imdb_id, season=None, ep=None):
        params = {"t": "tvsearch", "imdbid": imdb_id, "cat": "5000"}
        if season:
            params["season"] = season
        if ep:
            params["ep"] = ep
        return self._fetch_all_results(params, USER_AGENT_SONARR)

    def search_music(self, query):
        return self._fetch_all_results(
            {"t": "music", "title": query, "cat": "3000"}, USER_AGENT_LIDARR
        )

    def search_doc(self, query):
        return self._fetch_all_results(
            {"t": "book", "title": query, "cat": "7000"}, USER_AGENT_LL
        )

    def _fetch_all_results(self, base_params, user_agent):
        all_items = []
        offset, limit = 0, 100
        while True:
            params = base_params.copy()
            params.update({"offset": offset, "limit": limit})
            items = self._parse_xml(self._get(params, user_agent))
            if not items:
                break
            all_items.extend(items)
            if len(items) < limit:
                break
            offset += limit
        return all_items

    def _parse_xml(self, response):
        if not response:
            return []
        try:
            root = ET.fromstring(response.content)
            items = []
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                pubdate_elem = item.find("pubDate")

                items.append(
                    {
                        "title": title_elem.text
                        if title_elem is not None and title_elem.text
                        else "",
                        "link": link_elem.text
                        if link_elem is not None and link_elem.text
                        else "",
                        "size": item.find("enclosure").attrib.get("length", "0")
                        if item.find("enclosure") is not None
                        else "0",
                        "pubdate": pubdate_elem.text
                        if pubdate_elem is not None and pubdate_elem.text
                        else "",
                    }
                )
            return items
        except:
            return []

    def add_download(self, title, link, category=None):
        params = {"mode": "addurl", "name": link}
        if category:
            params["cat"] = category

        # Use appropriate User-Agent if category is known
        user_agent = USER_AGENT_RADARR
        if category == "tv":
            user_agent = USER_AGENT_SONARR
        elif category == "music":
            user_agent = USER_AGENT_LIDARR
        elif category == "docs":
            user_agent = USER_AGENT_LL

        resp = self._get(params, user_agent)
        if not resp:
            return None, "Request failed"

        try:
            data = resp.json()
        except Exception:
            return None, "Invalid JSON response"

        # Check for quasarr_error flag
        if data.get("quasarr_error"):
            return None, data.get("quasarr_error")

        # Also check status and nzo_ids as a fallback
        if data.get("status", False) and data.get("nzo_ids"):
            return data.get("nzo_ids"), None
        return None, "Unknown error"

    def delete_download(self, nzo_id):
        resp = self._get(
            {"mode": "queue", "name": "delete", "value": nzo_id}, USER_AGENT_RADARR
        )
        if not resp:
            return False, "Request failed"

        try:
            data = resp.json()
        except Exception:
            return False, "Invalid JSON response"

        if data.get("quasarr_error"):
            return False, data.get("quasarr_error")

        if data.get("status", False):
            return True, None
        return False, "Unknown error"

    def fail_download(self, package_id):
        try:
            resp = self.session.delete(
                f"{self.url}/sponsors_helper/api/fail/",
                params={"apikey": self.api_key},
                json={"package_id": package_id},
                timeout=30,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            if hasattr(e, "response") and e.response is not None:
                console.print(
                    f"[red]Fail download error: {e.response.status_code} - {e.response.text}[/red]"
                )
            else:
                console.print(f"[red]Fail download error: {e}[/red]")
            return False

    def enable_sponsor_status(self):
        try:
            resp = self.session.put(
                f"{self.url}/sponsors_helper/api/set_sponsor_status/",
                params={"apikey": self.api_key},
                json={"activate": True},
                timeout=30,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            if hasattr(e, "response") and e.response is not None:
                console.print(
                    f"[red]Enable sponsor status error: {e.response.status_code} - {e.response.text}[/red]"
                )
            else:
                console.print(f"[red]Enable sponsor status error: {e}[/red]")
            return False


# --- UI Logic ---
def clear_screen():
    console.clear()


def format_size(size_bytes):
    try:
        s = int(size_bytes)
        if s == 0:
            return "0 MB"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if s < 1024:
                return f"{s:.2f} {unit}"
            s /= 1024
    except:
        return "Unknown"


def show_downloads(client):
    last_idx = 0
    # For downloads, we skip "newest/oldest" as API data might be inconsistent for sorting
    download_sorts = ["a-z", "z-a", "size_desc", "size_asc"]

    while True:
        clear_screen()
        results = LoadingScreen("Fetching Downloads", client.get_downloads).run()
        clear_screen()  # Ensure loading screen is cleared immediately

        if results is None:
            return

        queue, history = results
        all_items = []
        for item in queue:
            item["type"] = "queue"
            all_items.append(item)
        for item in history:
            item["type"] = "history"
            all_items.append(item)

        if not all_items:
            console.print(
                Panel("No active downloads.", title="Downloads", border_style="blue")
            )
            press_any_key()
            clear_screen()
            return

        selector_items = []
        for item in all_items:
            # Name
            name = (
                item.get("filename")
                if item["type"] == "queue"
                else item.get("name", "Unknown")
            )
            status = item.get("status", "Unknown")

            # Size
            # Queue often has 'size' (total) or 'mb' (total)
            raw_size = item.get("size", "0")
            size_str = format_size(raw_size)

            # Time / ETA
            time_info = ""
            if item["type"] == "queue":
                # Queue usually has 'timeleft'
                eta = item.get("timeleft", "")
                if eta:
                    time_info = f" | ETA: {eta}"
            else:
                # History usually has completion date
                completed = item.get("completed", "") or item.get("date", "")
                if completed:
                    # Try timestamp conversion if it's a timestamp
                    try:
                        ts = int(completed)
                        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                        time_info = f" | {dt}"
                    except:
                        time_info = f" | {completed}"

            icon = "⬇️" if item["type"] == "queue" else "📜"
            label = f"{icon} {name} (Size: {size_str}{time_info}) [{status}]"
            selector_items.append((label, item))

        result = PaginatedSelector(
            "Downloads",
            selector_items,
            page_size=10,
            initial_index=last_idx,
            allowed_sorts=download_sorts,
        ).run()

        clear_screen()  # Clean up the selector UI immediately

        if result is None:
            break

        item, last_idx = result
        name = item.get("filename") if item["type"] == "queue" else item.get("name")
        nzo_id = item.get("nzo_id")

        menu = []
        if "[CAPTCHA" in name:
            menu.append(("🔓 Solve CAPTCHA", "captcha"))
        menu.append(("🗑️ Delete", "delete"))
        if item.get("status", "").lower() not in ["failed", "error"]:
            menu.append(("❌ Mark Failed", "fail"))

        action = MenuSelector(f"Manage: {name}", menu).run()
        clear_screen()

        if action == "captcha":
            webbrowser.open(f"{client.url}/captcha?package_id={nzo_id}")
            time.sleep(2)
        elif action == "delete":
            if questionary.confirm(f"Delete '{name}'?").ask():
                res = LoadingScreen(
                    f"Deleting {name}", client.delete_download, nzo_id
                ).run()
                if res and res[0]:
                    console.print("[green]Deleted[/green]")
                else:
                    err = res[1] if res else "Cancelled"
                    console.print(f"[red]Failed: {err}[/red]")
                time.sleep(1)
        elif action == "fail":
            if questionary.confirm(f"Mark '{name}' failed?").ask():
                if LoadingScreen(f"Failing {name}", client.fail_download, nzo_id).run():
                    console.print("[green]Marked Failed[/green]")
                else:
                    console.print("[red]Failed[/red]")
                time.sleep(1)


def handle_results_pager(client, results, category=None, duration=None):
    clear_screen()
    if not results:
        console.print(
            Panel("[yellow]No results found.[/yellow]", border_style="yellow")
        )
        press_any_key()
        clear_screen()
        return

    # Default logic for search results includes date sorting
    results.sort(key=lambda x: x.get("pubdate", ""), reverse=True)
    selector_items = [
        (f"{item['title']} ({format_size(item['size'])})", item) for item in results
    ]

    last_idx = 0
    while True:
        clear_screen()
        result = PaginatedSelector(
            "Search Results",
            selector_items,
            page_size=10,
            initial_index=last_idx,
            duration=duration,
        ).run()

        clear_screen()

        if result is None:
            break
        item, last_idx = result

        res = LoadingScreen(
            f"Adding: {item['title']}",
            client.add_download,
            item["title"],
            item["link"],
            category,
        ).run()

        clear_screen()

        if res and res[0]:
            console.print(f"[green]✅ Added '{item['title']}'[/green]")
        elif res:
            console.print(f"[red]❌ Failed to add '{item['title']}': {res[1]}[/red]")
        else:
            console.print("[yellow]⚠️ Cancelled[/yellow]")
        time.sleep(1)


def handle_feeds_menu(client):
    while True:
        clear_screen()
        choice = MenuSelector(
            "Select Feed",
            [
                ("🎬 Movie (Radarr)", "movie"),
                ("📺 TV (Sonarr)", "tv"),
                ("🎵 Music (Lidarr)", "music"),
                ("📄 Doc (LazyLib)", "doc"),
            ],
        ).run()
        clear_screen()

        if not choice:
            break

        start = time.time()
        results = LoadingScreen(
            f"Fetching {choice} Feed", client.get_feed, choice
        ).run()
        clear_screen()

        if results is not None:
            cat_map = {"movie": "movies", "tv": "tv", "music": "music", "doc": "docs"}
            handle_results_pager(
                client, results, cat_map.get(choice), time.time() - start
            )


def handle_searches_menu(client):
    defaults = {
        "movie": "tt0133093",
        "tv": "tt0944947",
        "music": "Taylor Swift",
        "doc": "PC Gamer UK",
    }
    while True:
        clear_screen()
        choice = MenuSelector(
            "Select Search Type",
            [
                ("🎬 Movie (IMDb)", "movie"),
                ("📺 TV (IMDb)", "tv"),
                ("🎵 Music (Query)", "music"),
                ("📄 Doc (Query)", "doc"),
            ],
        ).run()
        clear_screen()

        if not choice:
            break

        if choice == "movie":
            q = TextInput(
                "Movie: IMDb ID", default=defaults["movie"], validator=validate_imdb
            ).run()
            if q:
                clear_screen()
                start = time.time()
                res = LoadingScreen(
                    f"Searching Movie: {q}", client.search_movie, q
                ).run()
                clear_screen()
                if res is not None:
                    handle_results_pager(client, res, "movies", time.time() - start)
        elif choice == "tv":
            q = TextInput(
                "TV: IMDb ID", default=defaults["tv"], validator=validate_imdb
            ).run()
            if q:
                clear_screen()
                s = TextInput(f"TV: {q}\nSeason", default="1").run()
                if s is not None:
                    clear_screen()
                    e = TextInput(f"TV: {q} S{s}\nEpisode", default="1").run()
                    if e is not None:
                        clear_screen()
                        start = time.time()
                        res = LoadingScreen(
                            f"Searching TV: {q}", client.search_tv, q, s, e
                        ).run()
                        clear_screen()
                        if res is not None:
                            handle_results_pager(client, res, "tv", time.time() - start)
        elif choice == "music":
            q = TextInput("Music: Query", default=defaults["music"]).run()
            if q:
                clear_screen()
                start = time.time()
                res = LoadingScreen(
                    f"Searching Music: {q}", client.search_music, q
                ).run()
                clear_screen()
                if res is not None:
                    handle_results_pager(client, res, "music", time.time() - start)
        elif choice == "doc":
            q = TextInput("Doc: Query", default=defaults["doc"]).run()
            if q:
                clear_screen()
                start = time.time()
                res = LoadingScreen(f"Searching Doc: {q}", client.search_doc, q).run()
                clear_screen()
                if res is not None:
                    handle_results_pager(client, res, "docs", time.time() - start)


def handle_hostname_test(client, interactive=True):
    if interactive:
        clear_screen()

    console.print("[bold cyan]--- TEST ALL HOSTNAMES ---[/bold cyan]")
    console.print("[dim]Keys: [Ctrl+C] Cancel Operation[/dim]")
    console.print("")

    feeds = [("movie", "movies"), ("tv", "tv"), ("music", "music"), ("doc", "docs")]

    # 1. Fetch Feeds
    console.print("[cyan]Fetching feeds...[/cyan]")
    all_feed_items = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            # Create a task for each feed
            tasks = {}
            for feed_type, _ in feeds:
                tasks[feed_type] = progress.add_task(
                    f"Fetching {feed_type} feed...", total=None
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_feed = {
                    executor.submit(client.get_feed, feed_type): (feed_type, category)
                    for feed_type, category in feeds
                }

                for future in concurrent.futures.as_completed(future_to_feed):
                    feed_type, category = future_to_feed[future]
                    try:
                        feed_items = future.result()
                        progress.update(
                            tasks[feed_type],
                            completed=1,
                            total=1,
                            description=f"[green]Fetched {feed_type} feed[/green]",
                        )
                        if feed_items:
                            for item in feed_items:
                                all_feed_items.append((feed_type, category, item))
                    except Exception:
                        progress.update(
                            tasks[feed_type],
                            completed=1,
                            total=1,
                            description=f"[red]Failed {feed_type} feed[/red]",
                        )
    except KeyboardInterrupt:
        console.print("[red]Cancelled fetching feeds.[/red]")
        return False

    if not all_feed_items:
        console.print("[bold red]Error: No feed items received.[/bold red]")
        if interactive:
            press_any_key()
        return False

    # Process items to find candidates (group by host, pick oldest)
    items_by_feed_host = {}

    for feed_type, category, item in all_feed_items:
        title = item.get("title") or ""
        link = item.get("link") or ""
        host = None

        # Parse payload to get real info if available
        payload_info = {}
        if link:
            try:
                parsed = urlparse(link)
                if "payload=" in parsed.query:
                    payload = parsed.query.split("payload=")[1].split("&")[0]
                    payload += "=" * (-len(payload) % 4)
                    decoded = urlsafe_b64decode(payload).decode("utf-8")
                    parts = decoded.split("|")
                    if len(parts) >= 6:
                        payload_info = {
                            "title": parts[0],
                            "url": parts[1],
                            "size": parts[2],
                            "pwd": parts[3],
                            "imdb": parts[4],
                            "source": parts[5],
                        }
            except Exception:
                pass

        # 1. Try title prefix [XX]
        match = re.match(r"^\[([A-Za-z0-9\.\-\_]+)\]", title)
        if match:
            host = match.group(1).lower()
            # If title is just prefix, try to use payload title
            if len(title.strip()) <= len(match.group(0)) + 1:
                if payload_info.get("title"):
                    title = payload_info["title"]
                    item["title"] = title

        # 2. Try payload source
        if not host and payload_info.get("source"):
            host = payload_info["source"].lower()
            if not title and payload_info.get("title"):
                title = payload_info["title"]
                item["title"] = title

        # 3. Fallback to domain
        if not host and link:
            try:
                host = urlparse(link).hostname
            except:
                pass

        if not host:
            continue

        _key = (feed_type, host)
        if _key not in items_by_feed_host:
            items_by_feed_host[_key] = []

        items_by_feed_host[_key].append(
            {"feed": feed_type, "category": category, "host": host, "item": item}
        )

    # Prepare tasks: Group by host/feed, candidates reversed (Oldest -> Newest)
    tasks_to_process = []
    for _key, items in items_by_feed_host.items():
        candidates = list(reversed(items))
        tasks_to_process.append(
            {"feed": _key[0], "host": _key[1], "candidates": candidates}
        )

    if interactive:
        clear_screen()
        console.print("[bold cyan]--- TEST ALL HOSTNAMES ---[/bold cyan]")
        console.print("[dim]Keys: [Ctrl+C] Cancel Operation[/dim]")
        console.print("")

    if not tasks_to_process:
        console.print("[bold red]Error: No items to download found.[/bold red]")
        if interactive:
            press_any_key()
        return False

    # 2. Download items
    results = []
    attempted_titles = set()
    console.print(
        f"[cyan]Attempting to add {len(tasks_to_process)} downloads (with retries)...[/cyan]"
    )

    def process_download_task(task):
        feed = task["feed"]
        host = task["host"]
        candidates = task["candidates"]

        # Try up to 3 candidates
        limit = min(3, len(candidates))
        last_error = "No candidates"
        last_title = "Unknown"

        for i in range(limit):
            candidate = candidates[i]
            title = candidate["item"]["title"]
            link = candidate["item"]["link"]
            category = candidate["category"]
            last_title = title

            nzo_ids, error = client.add_download(title, link, category=category)
            if nzo_ids:
                return {
                    "feed": feed,
                    "host": host,
                    "title": title,
                    "success": True,
                    "nzo_ids": nzo_ids,
                    "error": None,
                }
            last_error = error

        return {
            "feed": feed,
            "host": host,
            "title": last_title,
            "success": False,
            "nzo_ids": None,
            "error": last_error,
        }

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,
        ) as progress:
            task_id = progress.add_task(
                "Adding downloads...", total=len(tasks_to_process)
            )

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_task = {
                    executor.submit(process_download_task, task): task
                    for task in tasks_to_process
                }

                for future in concurrent.futures.as_completed(future_to_task):
                    try:
                        res = future.result()
                        attempted_titles.add(res["title"])
                        results.append(res)
                    except Exception:
                        pass
                    progress.advance(task_id)
    except KeyboardInterrupt:
        console.print("[red]Cancelled adding downloads.[/red]")
        # Proceed to summary/cleanup with whatever results we have

    # 3. Summary
    if interactive:
        clear_screen()
    console.print(
        Panel("Summary of Hostname Test", title="Results", border_style="blue")
    )

    # Stats for summary
    stats = {
        "movie": {
            "results": 0,
            "dl_success": 0,
            "dl_fail": 0,
            "del_success": 0,
            "del_fail": 0,
        },
        "tv": {
            "results": 0,
            "dl_success": 0,
            "dl_fail": 0,
            "del_success": 0,
            "del_fail": 0,
        },
        "music": {
            "results": 0,
            "dl_success": 0,
            "dl_fail": 0,
            "del_success": 0,
            "del_fail": 0,
        },
        "doc": {
            "results": 0,
            "dl_success": 0,
            "dl_fail": 0,
            "del_success": 0,
            "del_fail": 0,
        },
    }

    # Group results by feed type
    grouped_results = {}
    for res in results:
        feed = res["feed"]
        if feed not in grouped_results:
            grouped_results[feed] = []
        grouped_results[feed].append(res)

        if feed in stats:
            stats[feed]["results"] += 1
            if res["success"]:
                stats[feed]["dl_success"] += 1
            else:
                stats[feed]["dl_fail"] += 1

    for feed, res_list in grouped_results.items():
        console.print(
            f"[bold underline]{feed.upper()}[/bold underline] ({len(res_list)} items)"
        )
        for res in res_list:
            color = "green" if res["success"] else "red"
            status = "OK" if res["success"] else "FAIL"
            console.print(
                f"  [{color}]{status}[/{color}] - {res['host'].upper()} - {res['title']}"
            )
        console.print("")

    if interactive:
        console.print(
            "[yellow]Press any key to delete these downloads and exit...[/yellow]"
        )
        press_any_key()

    # 4. Cleanup
    if interactive:
        clear_screen()
        console.print("[bold cyan]--- TEST ALL HOSTNAMES ---[/bold cyan]")
        console.print("[dim]Keys: [Ctrl+C] Cancel Operation[/dim]")
        console.print("")

    console.print("[cyan]Cleaning up...[/cyan]")

    # Collect nzo_ids from results
    nzo_ids_to_delete = set()
    nzo_id_to_feed = {}
    for res in results:
        if res.get("nzo_ids"):
            for nid in res["nzo_ids"]:
                nzo_ids_to_delete.add(nid)
                nzo_id_to_feed[nid] = res["feed"]

    # Also fetch current queue/history to find items by name (for failed adds that might be stuck)
    try:
        queue, history = client.get_downloads()
        all_downloads = queue + history

        for item in all_downloads:
            # Check if this item matches any attempted title
            name = item.get("filename") or item.get("name") or ""
            nzo_id = item.get("nzo_id")

            if not nzo_id:
                continue

            # If we already have this ID, skip
            if nzo_id in nzo_ids_to_delete:
                continue

            # Check for title match
            # Simple containment check or exact match
            for title in attempted_titles:
                if title and (title == name or title in name or name in title):
                    nzo_ids_to_delete.add(nzo_id)
                    break
    except Exception:
        pass

    deleted_count = 0
    deletion_errors = []

    if not nzo_ids_to_delete:
        pass
    else:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                transient=True,
            ) as progress:
                task_id = progress.add_task(
                    "Deleting downloads...", total=len(nzo_ids_to_delete)
                )

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_id = {
                        executor.submit(client.delete_download, nzo_id): nzo_id
                        for nzo_id in nzo_ids_to_delete
                    }

                    for future in concurrent.futures.as_completed(future_to_id):
                        try:
                            nzo_id = future_to_id[future]
                            feed = nzo_id_to_feed.get(nzo_id)
                            success, error = future.result()
                            if success:
                                deleted_count += 1
                                if feed in stats:
                                    stats[feed]["del_success"] += 1
                            else:
                                if feed in stats:
                                    stats[feed]["del_fail"] += 1
                                deletion_errors.append(f"ID {nzo_id}: {error}")
                        except Exception:
                            if feed in stats:
                                stats[feed]["del_fail"] += 1
                            deletion_errors.append(f"ID {nzo_id}: Exception")
                        progress.advance(task_id)

            console.print(f"[green]Deleted {deleted_count} downloads.[/green]")
        except KeyboardInterrupt:
            console.print("[red]Cancelled cleanup.[/red]")

    if interactive:
        time.sleep(2)

    # Print Summary Table
    table = Table(title="Bulk Test Summary")
    table.add_column("Feed", style="cyan")
    table.add_column("Downloads (Success/Total)", justify="right")
    table.add_column("Deletions (Success/Total)", justify="right")

    for feed in ["movie", "tv", "music", "doc"]:
        data = stats[feed]
        total_dl = data["results"]
        dl_success = data["dl_success"]

        total_del = data["del_success"] + data["del_fail"]
        del_success = data["del_success"]

        dl_style = (
            "green"
            if dl_success == total_dl and total_dl > 0
            else "red"
            if dl_success == 0 and total_dl > 0
            else "yellow"
        )
        del_style = (
            "green"
            if del_success == total_del and total_dl > 0
            else "red"
            if del_success == 0 and total_dl > 0
            else "yellow"
        )

        table.add_row(
            feed.upper(),
            f"[{dl_style}]{dl_success}/{total_dl}[/{dl_style}]",
            f"[{del_style}]{del_success}/{total_dl}[/{del_style}]",
        )
    console.print(table)
    console.print("")

    # Show failures
    failures = [r for r in results if not r["success"]]
    if failures or deletion_errors:
        console.print("[bold red]Failures:[/bold red]")
        if failures:
            console.print("[red]Downloads:[/red]")
            for f in failures:
                console.print(
                    f"  - {f['feed'].upper()} / {f['host'].upper()}: {f['error']} ({f['title']})"
                )

        if deletion_errors:
            console.print("[red]Deletions:[/red]")
            for err in deletion_errors:
                console.print(f"  - {err}")
        console.print("")

    # Error Checks
    successful_downloads = len([r for r in results if r["success"]])

    # If we attempted downloads but none succeeded
    if results and successful_downloads == 0:
        console.print(
            "[bold red]Error: No downloads were successfully added.[/bold red]"
        )
        if interactive:
            press_any_key()
        return False

    # If we deleted fewer than we successfully added (by ID), that's definitely an error.
    # If we deleted more (because we cleaned up failed ones too), that's fine.
    # But strictly speaking, we want to ensure everything we added is gone.
    # Let's just check if we deleted at least the number of successful ones.
    if deleted_count < successful_downloads:
        console.print(
            f"[bold red]Error: Mismatch! Added {successful_downloads} but deleted {deleted_count}.[/bold red]"
        )
        if interactive:
            press_any_key()
        return False

    if interactive:
        press_any_key()

    return True


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--key")
    parser.add_argument("--test-movie", action="store_true")
    parser.add_argument("--test-tv", action="store_true")
    parser.add_argument("--test-music", action="store_true")
    parser.add_argument("--test-doc", action="store_true")
    parser.add_argument("--test-hostnames", action="store_true")
    args = parser.parse_args()

    api_key = args.key or os.environ.get("QUASARR_API_KEY")

    if any(
        [
            args.test_movie,
            args.test_tv,
            args.test_music,
            args.test_doc,
            args.test_hostnames,
        ]
    ):
        if not api_key:
            sys.exit("API Key required for tests")
        client = QuasarrClient(args.url, api_key)
        if args.test_movie:
            sys.exit(0 if client.search_movie("tt0133093") else 1)
        if args.test_tv:
            sys.exit(0 if client.search_tv("tt0944947") else 1)
        if args.test_music:
            sys.exit(0 if client.search_music("Linkin Park") else 1)
        if args.test_doc:
            sys.exit(0 if client.search_doc("PC Gamer UK") else 1)
        if args.test_hostnames:
            sys.exit(0 if handle_hostname_test(client, interactive=False) else 1)
        return

    if not IS_TTY:
        console.print(
            Panel("[yellow]Non-interactive terminal detected[/yellow]", title="Error")
        )
        sys.exit(1)

    clear_screen()
    if not api_key:
        console.print(Panel.fit(f"[bold blue]Quasarr CLI[/bold blue]\n{args.url}"))
        api_key = questionary.password("API Key:").ask()
        if not api_key:
            sys.exit(1)

    client = QuasarrClient(args.url, api_key)

    while True:
        clear_screen()
        try:
            choice = MenuSelector(
                "Main Menu",
                [
                    ("🧪 Test All Hostnames", "test_hostnames"),
                    ("🔍 Searches", "search"),
                    ("🗞️ Feeds", "feeds"),
                    ("⬇️ Downloads", "downloads"),
                    ("🔓 Enable Sponsor Status", "enable_sponsor"),
                    ("🌐 Open Web UI", "web"),
                    ("🚪 Exit", "exit"),
                ],
                allow_back=False,
            ).run()
            if choice == "feeds":
                handle_feeds_menu(client)
            elif choice == "search":
                handle_searches_menu(client)
            elif choice == "downloads":
                show_downloads(client)
            elif choice == "test_hostnames":
                handle_hostname_test(client)
            elif choice == "enable_sponsor":
                if LoadingScreen(
                    "Enabling Sponsor Status", client.enable_sponsor_status
                ).run():
                    console.print("[green]Sponsor status enabled![/green]")
                else:
                    console.print("[red]Failed to enable sponsor status.[/red]")
                time.sleep(2)
            elif choice == "web":
                webbrowser.open(client.url)
            elif choice == "exit":
                if questionary.confirm("Are you sure you want to exit?").ask():
                    sys.exit(0)
            elif choice is None:
                sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    try:
        run_cli()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)
