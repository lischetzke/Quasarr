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

import requests

# Try importing dependencies
try:
    import questionary

    # prompt_toolkit dependencies
    from prompt_toolkit import Application, PromptSession
    from prompt_toolkit.formatted_text import HTML, to_formatted_text
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.layout import Layout
    from rich.console import Console
    from rich.panel import Panel
except ImportError:
    print("Please install 'rich' and 'questionary' to use this tool.")
    print("pip install rich questionary")
    sys.exit(1)

# --- Configuration & Constants ---
DEFAULT_URL = "http://localhost:8080"
USER_AGENT_RADARR = "Radarr/3.0.0.0 (Mock Client for Testing)"
USER_AGENT_SONARR = "Sonarr/3.0.0.0 (Mock Client for Testing)"
USER_AGENT_LL = "LazyLibrarian/1.7.0 (Mock Client for Testing)"

console = Console()
IS_TTY = sys.stdin.isatty()

# --- Custom Loading Screen (Thread-based Fix) ---


class LoadingScreen:
    def __init__(self, title, func, *args, **kwargs):
        """
        Runs 'func' in a separate thread while showing a spinner.
        Allows cancellation via Left/Backspace.
        Uses threading instead of asyncio to avoid RuntimeWarnings.
        """
        self.title = title
        self.func = func
        self.args = args
        self.kwargs = kwargs

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
        lines.append(HTML(f"<b><ansicyan>--- {self.title.upper()} ---</ansicyan></b>"))
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
    def __init__(self, title, items, page_size=10, initial_index=0, duration=None):
        self.title = title
        self.items = items
        self.page_size = page_size
        self.selected_index = min(initial_index, len(items) - 1) if items else 0
        self.result = None
        self.cancelled = False
        self.duration = duration

    def get_current_page_indices(self):
        page_idx = self.selected_index // self.page_size
        start = page_idx * self.page_size
        end = min(len(self.items), start + self.page_size)
        return start, end, page_idx

    def get_text(self):
        start, end, page_idx = self.get_current_page_indices()
        total_pages = max(1, (len(self.items) + self.page_size - 1) // self.page_size)

        lines = []
        lines.append(HTML(f"<b><ansicyan>--- {self.title.upper()} ---</ansicyan></b>"))
        lines.append(
            HTML(
                "<grey>Keys: [↑/↓] Navigate | [←/→] Page | [Enter] Select | [Backspace] Back</grey>"
            )
        )

        summary = f"Page {page_idx + 1}/{total_pages} (Total: {len(self.items)})"
        if self.duration is not None:
            summary += f" | Took {self.duration:.2f}s"

        lines.append(HTML(f"<i>{summary}</i>"))
        lines.append(HTML(""))

        for i in range(start, end):
            label, _ = self.items[i]
            safe_label = label.replace("<", "&lt;").replace(">", "&gt;")

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
        lines.append(HTML(f"<b><ansicyan>--- {self.title.upper()} ---</ansicyan></b>"))

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
            safe_label = label.replace("<", "&lt;").replace(">", "&gt;")
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

        @kb.add("escape")
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
                    f"<b><ansicyan>--- {self.title.upper()} ---</ansicyan></b>\n<grey>Keys: [Enter] Confirm | [Back] Cancel</grey>\n[{self.default}]: "
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
                f"{self.url}/api", params=request_params, headers=headers, timeout=60
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
                self._get({"t": "movie", "imdbid": ""}, USER_AGENT_RADARR)
            )
        elif feed_type == "tv":
            return self._parse_xml(
                self._get({"t": "tvsearch", "imdbid": ""}, USER_AGENT_SONARR)
            )
        elif feed_type == "doc":
            return self._parse_xml(
                self._get({"t": "book", "author": "", "title": ""}, USER_AGENT_LL)
            )
        return []

    def search_movie(self, imdb_id):
        return self._fetch_all_results(
            {"t": "movie", "imdbid": imdb_id}, USER_AGENT_RADARR
        )

    def search_tv(self, imdb_id, season=None, ep=None):
        params = {"t": "tvsearch", "imdbid": imdb_id}
        if season:
            params["season"] = season
        if ep:
            params["ep"] = ep
        return self._fetch_all_results(params, USER_AGENT_SONARR)

    def search_doc(self, query):
        return self._fetch_all_results({"t": "book", "title": query}, USER_AGENT_LL)

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
                items.append(
                    {
                        "title": item.find("title").text,
                        "link": item.find("link").text,
                        "size": item.find("enclosure").attrib.get("length", "0")
                        if item.find("enclosure") is not None
                        else "0",
                        "pubdate": item.find("pubDate").text,
                    }
                )
            return items
        except:
            return []

    def add_download(self, title, link):
        resp = self._get({"mode": "addurl", "name": link}, USER_AGENT_RADARR)
        return resp.json().get("status", False) if resp else False

    def delete_download(self, nzo_id):
        resp = self._get(
            {"mode": "queue", "name": "delete", "value": nzo_id}, USER_AGENT_RADARR
        )
        return resp.json().get("status", False) if resp else False

    def fail_download(self, package_id):
        try:
            self.session.delete(
                f"{self.url}/sponsors_helper/api/fail/",
                params={"apikey": self.api_key},
                json={"package_id": package_id},
                headers={"X-Api-Key": self.api_key},
                timeout=30,
            ).raise_for_status()
            return True
        except:
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
    while True:
        clear_screen()
        results = LoadingScreen("Fetching Downloads", client.get_downloads).run()
        if results is None:
            clear_screen()
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
            questionary.press_any_key_to_continue().ask()
            clear_screen()
            return

        selector_items = []
        for item in all_items:
            name = item.get("filename") if item["type"] == "queue" else item.get("name")
            status = item.get("status", "Unknown")
            icon = "⬇️" if item["type"] == "queue" else "📜"
            selector_items.append((f"{icon} {name} [{status}]", item))

        result = PaginatedSelector(
            "Downloads", selector_items, page_size=10, initial_index=last_idx
        ).run()
        if result is None:
            clear_screen()
            break

        item, last_idx = result
        clear_screen()
        name = item.get("filename") if item["type"] == "queue" else item.get("name")
        nzo_id = item.get("nzo_id")

        menu = []
        if "[CAPTCHA" in name:
            menu.append(("🔓 Solve CAPTCHA", "captcha"))
        menu.append(("🗑️ Delete", "delete"))
        if item.get("status", "").lower() not in ["failed", "error"]:
            menu.append(("❌ Mark Failed", "fail"))

        action = MenuSelector(f"Manage: {name}", menu).run()
        if action == "captcha":
            webbrowser.open(f"{client.url}/captcha?package_id={nzo_id}")
            time.sleep(2)
        elif action == "delete":
            clear_screen()
            if questionary.confirm(f"Delete '{name}'?").ask():
                if LoadingScreen(
                    f"Deleting {name}", client.delete_download, nzo_id
                ).run():
                    console.print("[green]Deleted[/green]")
                else:
                    console.print("[red]Failed[/red]")
                time.sleep(1)
        elif action == "fail":
            clear_screen()
            if questionary.confirm(f"Mark '{name}' failed?").ask():
                if LoadingScreen(f"Failing {name}", client.fail_download, nzo_id).run():
                    console.print("[green]Marked Failed[/green]")
                else:
                    console.print("[red]Failed[/red]")
                time.sleep(1)


def handle_results_pager(client, results, duration=None):
    clear_screen()
    if not results:
        console.print(
            Panel("[yellow]No results found.[/yellow]", border_style="yellow")
        )
        questionary.press_any_key_to_continue().ask()
        clear_screen()
        return

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
        if result is None:
            clear_screen()
            break
        item, last_idx = result
        clear_screen()

        success = LoadingScreen(
            f"Adding: {item['title']}", client.add_download, item["title"], item["link"]
        ).run()
        if success is True:
            console.print(f"[green]✅ Added '{item['title']}'[/green]")
        elif success is False:
            console.print(f"[red]❌ Failed to add '{item['title']}'[/red]")
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
                ("📄 Doc (LazyLib)", "doc"),
            ],
        ).run()
        if not choice:
            clear_screen()
            break

        clear_screen()
        start = time.time()
        results = LoadingScreen(
            f"Fetching {choice} Feed", client.get_feed, choice
        ).run()
        if results is not None:
            handle_results_pager(client, results, time.time() - start)


def handle_searches_menu(client):
    defaults = {"movie": "tt0133093", "tv": "tt0944947", "doc": "PC Gamer UK"}
    while True:
        clear_screen()
        choice = MenuSelector(
            "Select Search Type",
            [
                ("🎬 Movie (IMDb)", "movie"),
                ("📺 TV (IMDb)", "tv"),
                ("📄 Doc (Query)", "doc"),
            ],
        ).run()
        if not choice:
            clear_screen()
            break

        clear_screen()
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
                if res is not None:
                    handle_results_pager(client, res, time.time() - start)
        elif choice == "tv":
            q = TextInput(
                "TV: IMDb ID", default=defaults["tv"], validator=validate_imdb
            ).run()
            if q:
                clear_screen()
                s = TextInput(f"TV: {q}\nSeason", default="1").run()
                if s:
                    clear_screen()
                    e = TextInput(f"TV: {q} S{s}\nEpisode", default="1").run()
                    if e:
                        clear_screen()
                        start = time.time()
                        res = LoadingScreen(
                            f"Searching TV: {q}", client.search_tv, q, s, e
                        ).run()
                        if res is not None:
                            handle_results_pager(client, res, time.time() - start)
        elif choice == "doc":
            q = TextInput("Doc: Query", default=defaults["doc"]).run()
            if q:
                clear_screen()
                start = time.time()
                res = LoadingScreen(f"Searching Doc: {q}", client.search_doc, q).run()
                if res is not None:
                    handle_results_pager(client, res, time.time() - start)


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--key")
    parser.add_argument("--test-movie", action="store_true")
    parser.add_argument("--test-tv", action="store_true")
    parser.add_argument("--test-doc", action="store_true")
    args = parser.parse_args()

    api_key = args.key or os.environ.get("QUASARR_API_KEY")

    if any([args.test_movie, args.test_tv, args.test_doc]):
        if not api_key:
            sys.exit("API Key required for tests")
        client = QuasarrClient(args.url, api_key)
        if args.test_movie:
            sys.exit(0 if client.search_movie("tt0133093") else 1)
        if args.test_tv:
            sys.exit(0 if client.search_tv("tt0944947") else 1)
        if args.test_doc:
            sys.exit(0 if client.search_doc("PC Gamer UK") else 1)
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
                    ("🔍 Searches", "search"),
                    ("🗞️ Feeds", "feeds"),
                    ("⬇️ Downloads", "downloads"),
                ],
                allow_back=False,
            ).run()
            if choice == "feeds":
                handle_feeds_menu(client)
            elif choice == "search":
                handle_searches_menu(client)
            elif choice == "downloads":
                show_downloads(client)
            elif choice is None:
                sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    try:
        run_cli()
    except:
        sys.exit(1)
