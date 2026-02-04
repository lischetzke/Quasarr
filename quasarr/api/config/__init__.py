# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import os
import signal
import threading
import time

from bottle import request, response

from quasarr.providers.html_templates import render_button, render_form
from quasarr.providers.log import info
from quasarr.storage.categories import (
    COMMON_HOSTERS,
    DEFAULT_CATEGORIES,
    TIER_1_HOSTERS,
    add_category,
    delete_category,
    get_categories,
    get_category_emoji,
    get_category_mirrors,
    update_category_emoji,
    update_category_mirrors,
)
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
    save_jdownloader_settings,
    verify_jdownloader_credentials,
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

    @app.post("/api/jdownloader/verify")
    def verify_jdownloader_api():
        return verify_jdownloader_credentials(shared_state)

    @app.post("/api/jdownloader/save")
    def save_jdownloader_api():
        return save_jdownloader_settings(shared_state, is_setup=False)

    @app.get("/categories")
    def categories_ui():
        """Web UI page for managing categories."""
        categories = get_categories()

        # Generate list items
        list_items = ""
        for cat in categories:
            emoji = get_category_emoji(cat)
            mirrors = get_category_mirrors(cat)
            mirrors_str = ", ".join(mirrors) if mirrors else "All"
            mirrors_json = str(mirrors).replace("'", '"')

            delete_btn = ""
            # Prevent deleting default categories
            if cat not in DEFAULT_CATEGORIES:
                delete_btn = f"""
                <button class="btn-subtle" onclick="deleteCategory('{cat}')" title="Delete">🗑️</button>
                """

            # Edit emoji button (for all categories)
            edit_btn = f"""
            <button class="btn-subtle" onclick="editEmoji('{cat}', '{emoji}')" title="Edit Emoji">✏️</button>
            """

            # Edit mirrors button
            mirrors_btn = f"""
            <button class="btn-subtle" onclick='editMirrors("{cat}", {mirrors_json})' title="Edit Mirrors">🔗</button>
            """

            list_items += f"""
            <div class="category-item">
                <span class="category-emoji">{emoji}</span>
                <div class="category-details">
                    <span class="category-name">{cat}</span>
                    <span class="category-mirrors">Mirrors: {mirrors_str}</span>
                </div>
                <div class="category-actions">
                    {mirrors_btn}
                    {edit_btn}
                    {delete_btn}
                </div>
            </div>
            """

        # Prepare hosters list for JS
        hosters_js = str(COMMON_HOSTERS).replace("'", '"')
        tier1_js = str(TIER_1_HOSTERS).replace("'", '"')

        form_html = f"""
        <style>
            .category-list {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                margin-bottom: 1.5rem;
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid var(--border-color, #dee2e6);
                border-radius: 0.5rem;
                padding: 0.5rem;
            }}
            .category-item {{
                display: flex;
                align-items: center;
                padding: 0.75rem;
                background: var(--code-bg, #f8f9fa);
                border-radius: 0.5rem;
                gap: 1rem;
            }}
            .category-emoji {{
                font-size: 1.5em;
                min-width: 1.5em;
                text-align: center;
            }}
            .category-details {{
                flex: 1;
                display: flex;
                flex-direction: column;
            }}
            .category-name {{
                font-weight: 600;
                font-size: 1.1em;
            }}
            .category-mirrors {{
                font-size: 0.85em;
                color: var(--text-muted);
            }}
            .category-actions {{
                display: flex;
                gap: 0.5rem;
            }}
            .add-category-form {{
                display: flex;
                gap: 0.5rem;
                margin-bottom: 1rem;
                align-items: center;
            }}
            .add-category-form input[type="text"] {{
                flex: 1;
            }}
            .emoji-input {{
                width: 3.5em !important;
                text-align: center;
            }}
            .mirrors-selection {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                max-height: 300px;
                overflow-y: auto;
                text-align: left;
                padding: 0.5rem;
                border: 1px solid var(--border-color);
                border-radius: 0.5rem;
                background: var(--code-bg);
            }}
            .mirror-option {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }}
            .mirror-option.tier1 {{
                font-weight: bold;
                color: var(--success-color);
            }}
            .warning-box {{
                background: var(--error-bg);
                color: var(--error-color);
                border: 1px solid var(--error-border);
                padding: 0.75rem;
                border-radius: 0.5rem;
                margin-bottom: 1rem;
                font-size: 0.9em;
                text-align: left;
            }}
        </style>

        <div class="category-list" id="categoryList">
            {list_items}
        </div>

        <div class="add-category-form">
            <input type="text" id="newCategoryEmoji" class="emoji-input" placeholder="📁" maxlength="2" title="Emoji (single char)">
            <input type="text" id="newCategoryName" placeholder="New category name (a-z, 0-9, _)" pattern="[a-z0-9_]+" title="Lowercase letters, numbers and underscores only">
            <button class="btn-primary" onclick="addCategory()">Add</button>
        </div>

        <p>{render_button("Back", "secondary", {"onclick": "location.href='/'"})}</p>

        <script>
        const ALL_HOSTERS = {hosters_js};
        const TIER1_HOSTERS = {tier1_js};

        function addCategory() {{
            const nameInput = document.getElementById('newCategoryName');
            const emojiInput = document.getElementById('newCategoryEmoji');
            const name = nameInput.value.trim();
            const emoji = emojiInput.value.trim() || '📁';
            
            if (!name) return;
            
            fetch('/api/categories', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ name: name, emoji: emoji }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    window.location.reload();
                }} else {{
                    showModal('Error', data.message);
                }}
            }})
            .catch(error => {{
                showModal('Error', 'Failed to add category: ' + error.message);
            }});
        }}

        function editEmoji(name, currentEmoji) {{
            const content = `
                <div style="text-align: center; margin-bottom: 1rem;">
                    <p>Enter a new emoji for <strong>${{name}}</strong>:</p>
                    <input type="text" id="editEmojiInput" value="${{currentEmoji}}" maxlength="2" style="font-size: 2em; width: 3em; text-align: center; margin: 0.5rem auto; display: block;">
                </div>
            `;
            
            showModal('Edit Emoji', content, 
                `<button class="btn-secondary" onclick="closeModal()">Cancel</button>
                 <button class="btn-primary" onclick="performEditEmoji('${{name}}')">Save</button>`
            );
        }}

        function performEditEmoji(name) {{
            const emojiInput = document.getElementById('editEmojiInput');
            const emoji = emojiInput.value.trim() || '📁';
            
            closeModal();
            
            fetch('/api/categories/' + name + '/emoji', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ emoji: emoji }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    window.location.reload();
                }} else {{
                    showModal('Error', data.message);
                }}
            }})
            .catch(error => {{
                showModal('Error', 'Failed to update emoji: ' + error.message);
            }});
        }}

        function editMirrors(name, currentMirrors) {{
            let checkboxes = '';
            ALL_HOSTERS.forEach(hoster => {{
                const isChecked = currentMirrors.includes(hoster) ? 'checked' : '';
                const isTier1 = TIER1_HOSTERS.includes(hoster);
                const tierClass = isTier1 ? 'tier1' : '';
                const labelSuffix = isTier1 ? ' (Recommended)' : '';
                
                checkboxes += `
                    <div class="mirror-option ${{tierClass}}">
                        <input type="checkbox" id="mirror_${{hoster}}" value="${{hoster}}" ${{isChecked}}>
                        <label for="mirror_${{hoster}}">${{hoster}}${{labelSuffix}}</label>
                    </div>
                `;
            }});

            const content = `
                <div class="warning-box">
                    <strong>⚠️ Warning:</strong> Setting specific mirrors will restrict search results. 
                    If a release does not contain ANY of the selected mirrors, it will be skipped.
                    <br><br>
                    We cannot know in advance if a mirror link is still active.
                    <br>
                    <strong>Only Tier 1 mirrors are recommended.</strong>
                </div>
                <div class="mirrors-selection">
                    ${{checkboxes}}
                </div>
            `;
            
            showModal('Edit Mirrors for ' + name, content, 
                `<button class="btn-secondary" onclick="closeModal()">Cancel</button>
                 <button class="btn-primary" onclick="performEditMirrors('${{name}}')">Save</button>`
            );
        }}

        function performEditMirrors(name) {{
            const selectedMirrors = [];
            document.querySelectorAll('.mirrors-selection input[type="checkbox"]:checked').forEach(cb => {{
                selectedMirrors.push(cb.value);
            }});
            
            closeModal();
            
            fetch('/api/categories/' + name + '/mirrors', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ mirrors: selectedMirrors }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    window.location.reload();
                }} else {{
                    showModal('Error', data.message);
                }}
            }})
            .catch(error => {{
                showModal('Error', 'Failed to update mirrors: ' + error.message);
            }});
        }}

        function deleteCategory(name) {{
            showModal('Delete Category?', 'Are you sure you want to delete category "' + name + '"?', 
                `<button class="btn-secondary" onclick="closeModal()">Cancel</button>
                 <button class="btn-danger" onclick="performDeleteCategory('${{name}}')">Delete</button>`
            );
        }}

        function performDeleteCategory(name) {{
            closeModal();
            fetch('/api/categories/' + name, {{
                method: 'DELETE'
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    window.location.reload();
                }} else {{
                    showModal('Error', data.message);
                }}
            }})
            .catch(error => {{
                showModal('Error', 'Failed to delete category: ' + error.message);
            }});
        }}
        </script>
        """
        return render_form("Categories", form_html)

    @app.post("/api/categories")
    def add_category_api():
        response.content_type = "application/json"
        try:
            data = request.json
            name = data.get("name")
            emoji = data.get("emoji", "📁")
            success, message = add_category(name, emoji)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.post("/api/categories/<name>/emoji")
    def update_category_emoji_api(name):
        response.content_type = "application/json"
        try:
            data = request.json
            emoji = data.get("emoji", "📁")
            success, message = update_category_emoji(name, emoji)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.post("/api/categories/<name>/mirrors")
    def update_category_mirrors_api(name):
        response.content_type = "application/json"
        try:
            data = request.json
            mirrors = data.get("mirrors", [])
            success, message = update_category_mirrors(name, mirrors)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.delete("/api/categories/<name>")
    def delete_category_api(name):
        response.content_type = "application/json"
        try:
            success, message = delete_category(name)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}
