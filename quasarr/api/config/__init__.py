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
                <button class="btn-danger" onclick="deleteCategory('{cat}')">Delete</button>
                """

            # Combined edit button
            edit_btn = f"""
            <button class="btn-primary" onclick='editCategory("{cat}", "{emoji}", {mirrors_json})'>Edit</button>
            """

            list_items += f"""
            <div class="category-item">
                <span class="category-emoji">{emoji}</span>
                <div class="category-details">
                    <span class="category-name">{cat}</span>
                    <span class="category-mirrors">Mirrors: {mirrors_str}</span>
                </div>
                <div class="category-actions">
                    {delete_btn}
                    {edit_btn}
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
                align-items: stretch;
            }}
            .add-category-form input {{
                margin-bottom: 0 !important;
            }}
            .add-category-form button {{
                margin-top: 0 !important;
            }}
            .add-category-form input[type="text"] {{
                flex: 1;
            }}
            .emoji-input {{
                width: 4em !important;
                text-align: center;
                flex: 0 0 auto !important;
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
            
            /* Mirror Picker Redesign */
            .mirrors-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.5rem;
            }}
            .mirror-pill {{
                padding: 0.5rem 0.75rem;
                border: 1px solid var(--border-color);
                border-radius: 2rem;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.2s;
                user-select: none;
                background: var(--card-bg);
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }}
            .mirror-pill:hover {{
                border-color: var(--primary);
            }}
            .mirror-pill.selected {{
                background-color: var(--primary);
                color: white;
                border-color: var(--primary);
            }}
            .mirror-pill.tier1 {{
                font-weight: 600;
                border-color: var(--success-color);
            }}
            .mirror-pill.tier1.selected {{
                background-color: var(--success-color);
                border-color: var(--success-color);
            }}
            .mirror-checkbox {{
                display: none;
            }}
        </style>

        <div class="category-list" id="categoryList">
            {list_items}
        </div>

        <div class="add-category-form">
            <input type="text" id="newCategoryEmoji" class="emoji-input" placeholder="📁" title="Emoji (single char)">
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

        function editCategory(name, currentEmoji, currentMirrors) {{
            let pills = '';
            ALL_HOSTERS.forEach(hoster => {{
                const isChecked = currentMirrors.includes(hoster);
                const isTier1 = TIER1_HOSTERS.includes(hoster);
                const tierClass = isTier1 ? 'tier1' : '';
                const selectedClass = isChecked ? 'selected' : '';
                const star = isTier1 ? '⭐ ' : '';
                
                pills += '<label class="mirror-pill ' + tierClass + ' ' + selectedClass + '" onclick="this.classList.toggle(\\'selected\\')">' +
                         '<input type="checkbox" class="mirror-checkbox" value="' + hoster + '" ' + (isChecked ? 'checked' : '') + ' onchange="this.parentElement.classList.toggle(\\'selected\\', this.checked)">' +
                         star + hoster +
                         '</label>';
            }});

            const content = '<p style="text-align: center;">Mirror-Filter:</p>' +
                            '<div class="warning-box">' +
                            '<strong>⚠️ Warning:</strong><br>' +
                            'Setting specific mirrors will restrict search results. ' +
                            'If a release does not contain <strong>any</strong> selected mirror, downloading it will fail!' +
                            '<br><br>' +
                            '<strong>Use at your own risk! Only starred mirrors (⭐) are recommended.</strong>' +
                            '</div>' +
                            '<div class="mirrors-grid">' +
                            pills +
                            '</div>' +
                            '<div style="text-align: center; margin-top: 1.5rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">' +
                            '<p>Category-Emoji:</p>' +
                            '<input type="text" id="editEmojiInput" value="' + currentEmoji + '" maxlength="1" style="font-size: 1em; width: 4em; text-align: center; margin: 0.5rem auto; display: block;">' +
                            '</div>';
            
            showModal('Edit Category: ' + name, content, 
                '<button class="btn-secondary" onclick="closeModal()">Cancel</button>' +
                '<button class="btn-primary" onclick="performEditCategory(\\'' + name + '\\')">Save</button>'
            );
        }}

        function performEditCategory(name) {{
            const emojiInput = document.getElementById('editEmojiInput');
            const emoji = emojiInput.value.trim() || '📁';
            
            const selectedMirrors = [];
            document.querySelectorAll('.mirror-checkbox:checked').forEach(cb => {{
                selectedMirrors.push(cb.value);
            }});
            
            closeModal();
            
            // Update emoji first, then mirrors
            fetch('/api/categories/' + name + '/emoji', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ emoji: emoji }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    return fetch('/api/categories/' + name + '/mirrors', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ mirrors: selectedMirrors }})
                    }});
                }} else {{
                    throw new Error(data.message);
                }}
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
                showModal('Error', 'Failed to update category: ' + error.message);
            }});
        }}

        function deleteCategory(name) {{
            showModal('Delete Category?', 'Are you sure you want to delete category "' + name + '"?', 
                '<button class="btn-secondary" onclick="closeModal()">Cancel</button>' +
                '<button class="btn-danger" onclick="performDeleteCategory(\\'' + name + '\\')">Delete</button>'
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
