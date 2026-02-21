# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import json
import os
import signal
import threading
import time

from bottle import request, response

from quasarr.constants import (
    DOWNLOAD_CATEGORIES,
    RECOMMENDED_HOSTERS,
    SHARE_HOSTERS,
)
from quasarr.providers.html_templates import render_button, render_form
from quasarr.providers.log import info
from quasarr.search.sources import get_sources
from quasarr.search.sources.helpers import get_hostnames
from quasarr.storage.categories import (
    add_custom_search_category,
    add_download_category,
    delete_download_category,
    delete_search_category,
    get_download_categories,
    get_download_category_emoji,
    get_download_category_mirrors,
    get_search_categories,
    get_search_category_sources,
    update_download_category_emoji,
    update_download_category_mirrors,
    update_search_category_sources,
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
            Use status buttons to change credentials and check for errors.
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
        response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
        response.set_header("Pragma", "no-cache")
        response.set_header("Expires", "0")

        categories = get_download_categories()

        # Generate list items for Download Categories
        download_list_items = ""
        for cat in categories:
            emoji = get_download_category_emoji(cat)
            mirrors = get_download_category_mirrors(cat)
            mirrors_str = ", ".join(mirrors) if mirrors else "All"
            mirrors_json = json.dumps(mirrors)

            delete_btn = ""
            # Prevent deleting default categories
            if cat not in DOWNLOAD_CATEGORIES:
                delete_btn = f"""
                <button class="btn-danger" onclick="deleteCategory('{cat}')">Delete</button>
                """

            # Combined edit button
            edit_btn = f"""
            <button class="btn-primary" onclick='editCategory("{cat}", "{emoji}", {mirrors_json})'>Edit</button>
            """

            download_list_items += f"""
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

        # Generate list items for Search Categories
        search_list_items = ""
        all_search_categories = get_search_categories()
        # Sort by ID
        sorted_search_cats = sorted(
            all_search_categories.items(), key=lambda x: int(x[0])
        )

        supported_categories_union = set()
        for source in get_sources().values():
            supported_categories_union.update(source.supported_categories)

        # filter search categories so that any categories without any supporting sources are removed
        sorted_search_cats = [
            (cat_id, details)
            for cat_id, details in sorted_search_cats
            if int(cat_id) in supported_categories_union or int(cat_id) >= 100000
        ]

        base_category_options = ""

        for cat_id, details in sorted_search_cats:
            cat_id = int(cat_id)
            name = details["name"]
            emoji = details["emoji"]
            search_sources = get_search_category_sources(cat_id)
            base_source_category_id = details.get("base_type", cat_id)
            try:
                base_source_category_id = int(base_source_category_id)
            except (ValueError, TypeError):
                if cat_id >= 100000:
                    base_source_category_id = ((cat_id - 100000) // 1000) * 1000
                else:
                    base_source_category_id = cat_id
            search_sources_str = (
                ", ".join([s.upper() for s in search_sources])
                if search_sources
                else "All"
            )
            search_sources_json = json.dumps(search_sources)

            delete_btn = ""
            # Allow deleting custom categories (ID >= 100000)
            if cat_id >= 100000:
                delete_btn = f"""
                <button class="btn-danger" onclick="deleteSearchCategory('{cat_id}')">Delete</button>
                """
            else:
                base_category_options += (
                    f'<option value="{cat_id}">{name} ({cat_id})</option>'
                )

            edit_btn = f"""
            <button class="btn-primary" onclick='editSearchCategory({cat_id}, "{name}", {search_sources_json}, {base_source_category_id})'>Edit</button>
            """

            search_list_items += f"""
            <div class="category-item">
                <span class="category-emoji">{emoji}</span>
                <div class="category-details">
                    <span class="category-name">{name} ({cat_id})</span>
                    <span class="category-mirrors">Hostnames: {search_sources_str}</span>
                </div>
                <div class="category-actions">
                    {delete_btn}
                    {edit_btn}
                </div>
            </div>
            """

        # Prepare hosters list for JS
        hosters_js = json.dumps(SHARE_HOSTERS)
        recommended_js = json.dumps(RECOMMENDED_HOSTERS)
        search_sources_js = json.dumps(get_hostnames())
        supported_categories_per_source = {
            source.initials: source.supported_categories
            for source in get_sources().values()
        }

        form_html = f"""
        <style>
            .category-list {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                margin-bottom: 1.5rem;
                max-height: 380px;
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
            .add-category-form input, .add-category-form select {{
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
            .mirror-checkbox, .search-source-checkbox {{
                display: none;
            }}
            h3 {{
                margin-top: 0;
                margin-bottom: 0.5rem;
                font-size: 1.2em;
            }}
            p.description {{
                margin-bottom: 1rem;
                color: var(--text-muted);
                font-size: 0.9em;
            }}
        </style>

        <h3>Download Categories</h3>
        <p class="description">Manage categories used for organizing downloads in JDownloader.</p>
        <div class="category-list" id="downloadCategoryList">
            {download_list_items}
        </div>

        <div class="add-category-form category-list">
            <div class="category-item">
                <input type="text" id="newCategoryEmoji" class="emoji-input" placeholder="📁" title="Emoji (single char)">
                <input type="text" id="newCategoryName" placeholder="New category name (a-z, 0-9, _)" pattern="[a-z0-9_]+" title="Lowercase letters, numbers and underscores only">
                <button class="btn-primary" onclick="addCategory()">Add</button>
            </div>
        </div>

        <h3>Search Categories</h3>
        <p class="description">Manage hostname whitelists for Newznab search categories.</p>
        <div class="category-list" id="searchCategoryList">
            {search_list_items}
        </div>
        
        <div class="add-category-form category-list">
            <div class="category-item">
                <select id="newSearchCategoryBase" style="flex: 1;">
                    <option value="" disabled selected>Select Base Category Type</option>
                    {base_category_options}
                </select>
                <button class="btn-primary" onclick="addSearchCategory()">Add Custom Category</button>
            </div>
        </div>

        <p>{render_button("Back", "secondary", {"onclick": "location.href='/'"})}</p>

        <script>
        const ALL_HOSTERS = {hosters_js};
        const TIER1_HOSTERS = {recommended_js};
        const HOSTNAMES = {search_sources_js};
        const SUPPORTED_CATEGORIES_PER_SOURCE = JSON.parse('{json.dumps(supported_categories_per_source)}');

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
        
        function addSearchCategory() {{
            const baseSelect = document.getElementById('newSearchCategoryBase');
            const baseType = baseSelect.value;
            
            if (!baseType) return;
            
            fetch('/api/categories_search', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ base_type: baseType }})
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
                showModal('Error', 'Failed to add search category: ' + error.message);
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

            const content = '<div style="margin-bottom: 1.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;">' +
                            '<h4>Category-Emoji:</h4>' +
                            '<input type="text" id="editEmojiInput" value="' + currentEmoji + '" maxlength="1" style="font-size: 1em; width: 4em; text-align: center; margin: 0.5rem auto; display: block;">' +
                            '</div>' +
                            '<h4>Mirror-Whitelist:</h4>' +
                            '<div class="warning-box">' +
                            '<strong>⚠️ Warning:</strong><br>This does not affect search results.<br>' +
                            'If specific mirrors are set, downloads will fail unless the release contains them.' +
                            '<br><br>' +
                            '<strong>Only starred mirrors (⭐) are recommended.</strong>' +
                            '</div>' +
                            '<div class="mirrors-grid">' +
                            pills +
                            '</div>';
            
            showModal('Edit Download Category: ' + name, content, 
                '<button class="btn-secondary" onclick="closeModal()">Cancel</button>' +
                '<button class="btn-primary" onclick="performEditCategory(\\'' + name + '\\')">Save</button>'
            );
        }}

        function editSearchCategory(catId, name, currentSearchSources, baseCategoryId) {{
            let searchPills = '';
            HOSTNAMES.forEach(source => {{
                if (SUPPORTED_CATEGORIES_PER_SOURCE[source]) {{
                    const parsedBaseCategoryId = parseInt(baseCategoryId, 10);
                    const categoryForFilter = Number.isNaN(parsedBaseCategoryId) ? catId : parsedBaseCategoryId;
                    const supportsCategory = SUPPORTED_CATEGORIES_PER_SOURCE[source].includes(categoryForFilter);
                    if (!supportsCategory) return; // Skip sources that don't support this category
                }}

                const isChecked = currentSearchSources.includes(source);
                const selectedClass = isChecked ? 'selected' : '';
                
                searchPills += '<label class="mirror-pill ' + selectedClass + '" onclick="this.classList.toggle(\\'selected\\')">' +
                         '<input type="checkbox" class="search-source-checkbox" value="' + source + '" ' + (isChecked ? 'checked' : '') + ' onchange="this.parentElement.classList.toggle(\\'selected\\', this.checked)">' +
                         source.toUpperCase() +
                         '</label>';
            }});

            const content = '<h4>Hostname-Whitelist:</h4>' +
                            '<div class="warning-box">' +
                            '<strong>⚠️ Warning:</strong><br>This affects search results.<br>' +
                            'If specific hostnames are set, only these will be searched.' +
                            '</div>' +
                            '<div class="mirrors-grid">' +
                            searchPills +
                            '</div>';
            
            showModal('Edit Search Category: ' + name, content, 
                '<button class="btn-secondary" onclick="closeModal()">Cancel</button>' +
                '<button class="btn-primary" onclick="performEditSearchCategory(\\'' + catId + '\\')">Save</button>'
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

        function performEditSearchCategory(catId) {{
            const selectedSearchSources = [];
            document.querySelectorAll('.search-source-checkbox:checked').forEach(cb => {{
                selectedSearchSources.push(cb.value);
            }});
            
            closeModal();
            
            fetch('/api/categories_search/' + catId + '/search_sources', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ search_sources: selectedSearchSources }})
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
                showModal('Error', 'Failed to update search category: ' + error.message);
            }});
        }}

        function deleteCategory(name) {{
            showModal('Delete Category?', 'Are you sure you want to delete category "' + name + '"?', 
                '<button class="btn-secondary" onclick="closeModal()">Cancel</button>' +
                '<button class="btn-danger" onclick="performDeleteCategory(\\'' + name + '\\')">Delete</button>'
            );
        }}
        
        function deleteSearchCategory(catId) {{
            showModal('Delete Search Category?', 'Are you sure you want to delete search category "' + catId + '"?', 
                '<button class="btn-secondary" onclick="closeModal()">Cancel</button>' +
                '<button class="btn-danger" onclick="performDeleteSearchCategory(\\'' + catId + '\\')">Delete</button>'
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
        
        function performDeleteSearchCategory(catId) {{
            closeModal();
            fetch('/api/categories_search/' + catId, {{
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
                showModal('Error', 'Failed to delete search category: ' + error.message);
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
            success, message = add_download_category(name, emoji)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.post("/api/categories_search")
    def add_search_category_api():
        response.content_type = "application/json"
        try:
            data = request.json
            base_type = data.get("base_type")
            success, message = add_custom_search_category(base_type)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.post("/api/categories/<name>/emoji")
    def update_category_emoji_api(name):
        response.content_type = "application/json"
        try:
            data = request.json
            emoji = data.get("emoji", "📁")
            success, message = update_download_category_emoji(name, emoji)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.post("/api/categories/<name>/mirrors")
    def update_category_mirrors_api(name):
        response.content_type = "application/json"
        try:
            data = request.json
            mirrors = data.get("mirrors", [])
            success, message = update_download_category_mirrors(name, mirrors)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.post("/api/categories_search/<cat_id>/search_sources")
    def update_search_category_sources_api(cat_id):
        response.content_type = "application/json"
        try:
            data = request.json
            search_sources = data.get("search_sources", [])
            success, message = update_search_category_sources(cat_id, search_sources)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.delete("/api/categories/<name>")
    def delete_category_api(name):
        response.content_type = "application/json"
        try:
            success, message = delete_download_category(name)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.delete("/api/categories_search/<cat_id>")
    def delete_search_category_api(cat_id):
        response.content_type = "application/json"
        try:
            success, message = delete_search_category(cat_id)
            return {"success": success, "message": message}
        except Exception as e:
            return {"success": False, "message": str(e)}
