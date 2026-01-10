# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import os
import signal
import threading
import time
from urllib.parse import urlparse

import requests
from bottle import request, response

from quasarr.providers.html_templates import render_form, render_button
from quasarr.providers.log import info
from quasarr.providers.shared_state import extract_valid_hostname
from quasarr.providers.utils import extract_kv_pairs, extract_allowed_keys
from quasarr.storage.config import Config
from quasarr.storage.setup import hostname_form_html, save_hostnames
from quasarr.storage.sqlite_database import DataBase


def setup_config(app, shared_state):
    @app.get('/hostnames')
    def hostnames_ui():
        message = """<p>
            At least one hostname must be kept.
        </p>"""
        back_button = f'''<p>
                        {render_button("Back", "secondary", {"onclick": "location.href='/'"})}
                    </p>'''
        return render_form("Hostnames",
                           hostname_form_html(shared_state, message, show_restart_button=True,
                                              show_skip_management=True) + back_button)

    @app.post("/api/hostnames")
    def hostnames_api():
        return save_hostnames(shared_state, timeout=1, first_run=False)

    @app.post("/api/hostnames/import-url")
    def import_hostnames_from_url():
        """Fetch URL and parse hostnames, return JSON for JS to populate fields."""
        response.content_type = 'application/json'
        try:
            data = request.json
            url = data.get('url', '').strip()

            if not url:
                return {"success": False, "error": "No URL provided"}

            # Validate URL
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return {"success": False, "error": "Invalid URL format"}

            if "/raw/eX4Mpl3" in url:
                return {"success": False, "error": "Example URL detected. Please provide a real URL."}

            # Fetch content
            try:
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                content = resp.text
            except requests.RequestException as e:
                return {"success": False, "error": f"Failed to fetch URL: {str(e)}"}

            # Parse hostnames
            allowed_keys = extract_allowed_keys(Config._DEFAULT_CONFIG, 'Hostnames')
            results = extract_kv_pairs(content, allowed_keys)

            if not results:
                return {"success": False, "error": "No hostnames found in the provided URL"}

            # Validate each hostname
            valid_hostnames = {}
            invalid_hostnames = {}
            for shorthand, hostname in results.items():
                domain_check = extract_valid_hostname(hostname, shorthand)
                domain = domain_check.get('domain')
                if domain:
                    valid_hostnames[shorthand] = domain
                else:
                    invalid_hostnames[shorthand] = domain_check.get('message', 'Invalid')

            if not valid_hostnames:
                return {"success": False, "error": "No valid hostnames found in the provided URL"}

            return {
                "success": True,
                "hostnames": valid_hostnames,
                "errors": invalid_hostnames
            }

        except Exception as e:
            return {"success": False, "error": f"Error: {str(e)}"}

    @app.get("/api/skip-login")
    def get_skip_login():
        """Return list of hostnames with skipped login."""
        response.content_type = 'application/json'
        skip_db = DataBase("skip_login")
        login_required_sites = ['al', 'dd', 'dl', 'nx']
        skipped = []
        for site in login_required_sites:
            if skip_db.retrieve(site):
                skipped.append(site)
        return {"skipped": skipped}

    @app.delete("/api/skip-login/<shorthand>")
    def clear_skip_login(shorthand):
        """Clear skip login preference for a hostname."""
        response.content_type = 'application/json'
        shorthand = shorthand.lower()
        login_required_sites = ['al', 'dd', 'dl', 'nx']
        if shorthand not in login_required_sites:
            return {"success": False, "error": f"Invalid shorthand: {shorthand}"}

        skip_db = DataBase("skip_login")
        skip_db.delete(shorthand)
        info(f'Skip login preference cleared for "{shorthand.upper()}"')
        return {"success": True}

    @app.post("/api/restart")
    def restart_quasarr():
        """Restart Quasarr. In Docker with the restart loop, exit(0) triggers restart."""
        response.content_type = 'application/json'
        info("Restart requested via web UI")

        def delayed_exit():
            time.sleep(0.5)
            # Send SIGINT to main process - triggers KeyboardInterrupt handler
            os.kill(os.getpid(), signal.SIGINT)

        threading.Thread(target=delayed_exit, daemon=True).start()
        return {"success": True, "message": "Restarting..."}
