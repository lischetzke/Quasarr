# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import os
import signal
import threading
import time

from bottle import response

from quasarr.providers.html_templates import render_button, render_form
from quasarr.providers.log import info
from quasarr.storage.config import Config
from quasarr.storage.setup import (
    check_credentials,
    clear_skip_login,
    delete_skip_flaresolverr_preference,
    get_flaresolverr_status_data,
    get_skip_login,
    hostname_form_html,
    import_hostnames_from_url,
    save_flaresolverr_url,
    save_hostnames,
)
from quasarr.storage.sqlite_database import DataBase


def setup_config(app, shared_state):
    @app.get("/api/hostname-issues")
    def get_hostname_issues_api():
        response.content_type = "application/json"
        from quasarr.providers.hostname_issues import get_all_hostname_issues

        return {"issues": get_all_hostname_issues()}

    @app.get("/hostnames")
    def hostnames_ui():
        message = """<p>
            At least one hostname must be kept.
        </p>"""
        back_button = f"""<p>
                        {render_button("Back", "secondary", {"onclick": "location.href='/'"})}
                    </p>"""
        return render_form(
            "Hostnames",
            hostname_form_html(
                shared_state,
                message,
                show_skip_management=True,
            )
            + back_button,
        )

    @app.post("/api/hostnames")
    def hostnames_api():
        return save_hostnames(shared_state, timeout=1, first_run=False)

    @app.post("/api/hostnames/check-credentials/<shorthand>")
    def check_credentials_api(shorthand):
        return check_credentials(shared_state, shorthand)

    @app.post("/api/hostnames/import-url")
    def import_hostnames_route():
        return import_hostnames_from_url()

    @app.get("/api/skip-login")
    def get_skip_login_route():
        return get_skip_login()

    @app.delete("/api/skip-login/<shorthand>")
    def clear_skip_login_route(shorthand):
        return clear_skip_login(shorthand)

    @app.get("/flaresolverr")
    def flaresolverr_ui():
        """Web UI page for configuring FlareSolverr."""
        skip_db = DataBase("skip_flaresolverr")
        is_skipped = skip_db.retrieve("skipped")
        current_url = Config("FlareSolverr").get("url") or ""

        skip_indicator = ""
        if is_skipped:
            skip_indicator = """
            <div class="skip-indicator" style="margin-bottom:1rem; padding:0.75rem; background:var(--code-bg, #f8f9fa); border-radius:0.25rem; font-size:0.875rem;">
                <span style="color:#dc3545;">⚠️ FlareSolverr setup was skipped</span>
                <p style="margin:0.5rem 0 0 0; font-size:0.75rem; color:var(--secondary, #6c757d);">
                    Some sites (like AL) won't work until FlareSolverr is configured.
                </p>
            </div>
            """

        form_content = f'''
        {skip_indicator}
        <span><a href="https://github.com/FlareSolverr/FlareSolverr?tab=readme-ov-file#installation" target="_blank">FlareSolverr</a>
        must be running and reachable to Quasarr for some sites to work.</span><br><br>
        <label for="url">FlareSolverr URL</label>
        <input type="text" id="url" name="url" placeholder="http://192.168.0.1:8191/v1" value="{current_url}"><br>
        '''

        form_html = f"""
        <form action="/api/flaresolverr" method="post" onsubmit="return handleSubmit(this)">
            {form_content}
            {render_button("Save", "primary", {"type": "submit", "id": "submitBtn"})}
        </form>
        <p>{render_button("Back", "secondary", {"onclick": "location.href='/';"})}</p>
        <script>
        var formSubmitted = false;
        function handleSubmit(form) {{
            if (formSubmitted) return false;
            formSubmitted = true;
            var btn = document.getElementById('submitBtn');
            if (btn) {{ btn.disabled = true; btn.textContent = 'Saving...'; }}
            return true;
        }}
        function confirmRestart() {{
            showModal('Restart Quasarr?', 'Are you sure you want to restart Quasarr now?', 
                `<button class="btn-secondary" onclick="closeModal()">Cancel</button>
                 <button class="btn-primary" onclick="performRestart()">Restart</button>`
            );
        }}
        function performRestart() {{
            closeModal();
            fetch('/api/restart', {{ method: 'POST' }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    showRestartOverlay();
                }}
            }})
            .catch(error => {{
                showRestartOverlay();
            }});
        }}
        function showRestartOverlay() {{
            document.body.innerHTML = `
              <div style="text-align:center; padding:2rem; font-family:system-ui,-apple-system,sans-serif;">
                <h2>Restarting Quasarr...</h2>
                <p id="restartStatus">Waiting <span id="countdown">10</span> seconds...</p>
                <div id="spinner" style="display:none; margin-top:1rem;">
                  <div style="display:inline-block; width:24px; height:24px; border:3px solid #ccc; border-top-color:#333; border-radius:50%; animation:spin 1s linear infinite;"></div>
                  <style>@keyframes spin {{ to {{ transform: rotate(360deg); }} }}</style>
                </div>
              </div>
            `;
            startCountdown(10);
        }}
        function startCountdown(seconds) {{
            var countdownEl = document.getElementById('countdown');
            var statusEl = document.getElementById('restartStatus');
            var spinnerEl = document.getElementById('spinner');
            var remaining = seconds;
            var interval = setInterval(function() {{
                remaining--;
                if (countdownEl) countdownEl.textContent = remaining;
                if (remaining <= 0) {{
                    clearInterval(interval);
                    statusEl.textContent = 'Reconnecting...';
                    spinnerEl.style.display = 'block';
                    tryReconnect();
                }}
            }}, 1000);
        }}
        function tryReconnect() {{
            var statusEl = document.getElementById('restartStatus');
            var attempts = 0;
            function attempt() {{
                attempts++;
                fetch('/', {{ method: 'HEAD', cache: 'no-store' }})
                .then(response => {{
                    if (response.ok) {{
                        statusEl.textContent = 'Connected! Reloading...';
                        setTimeout(function() {{ window.location.href = '/'; }}, 500);
                    }} else {{
                        scheduleRetry();
                    }}
                }})
                .catch(function() {{
                    scheduleRetry();
                }});
            }}
            function scheduleRetry() {{
                statusEl.textContent = 'Reconnecting... (attempt ' + attempts + ')';
                setTimeout(attempt, 1000);
            }}
            attempt();
        }}
        </script>
        """
        return render_form("FlareSolverr", form_html)

    @app.post("/api/flaresolverr")
    def set_flaresolverr_url():
        """Save FlareSolverr URL from web UI."""
        return save_flaresolverr_url(shared_state)

    @app.get("/api/flaresolverr/status")
    def get_flaresolverr_status():
        """Return FlareSolverr configuration status."""
        return get_flaresolverr_status_data(shared_state)

    @app.delete("/api/skip-flaresolverr")
    def clear_skip_flaresolverr():
        """Clear skip FlareSolverr preference."""
        return delete_skip_flaresolverr_preference()

    @app.post("/api/restart")
    def restart_quasarr():
        """Restart Quasarr. In Docker with the restart loop, exit(0) triggers restart."""
        response.content_type = "application/json"
        info("Restart requested via web UI")

        def delayed_exit():
            time.sleep(0.5)
            # Send SIGINT to main process - triggers KeyboardInterrupt handler
            os.kill(os.getpid(), signal.SIGINT)

        threading.Thread(target=delayed_exit, daemon=True).start()
        return {"success": True, "message": "Restarting..."}
