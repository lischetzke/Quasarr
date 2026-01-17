# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import quasarr.providers.html_images as images
from quasarr.downloads.packages import get_packages, delete_package
from quasarr.providers import shared_state
from quasarr.providers.html_templates import render_button, render_centered_html


def setup_packages_routes(app):
    @app.get('/packages/delete/<package_id>')
    def delete_package_route(package_id):
        success = delete_package(shared_state, package_id)

        # Redirect back to packages page with status message via query param
        from bottle import redirect
        if success:
            redirect('/packages?deleted=1')
        else:
            redirect('/packages?deleted=0')

    @app.get('/packages')
    def packages_status():
        from bottle import request

        try:
            device = shared_state.values["device"]
        except KeyError:
            device = None

        if not device:
            back_btn = render_button("Back", "secondary", {"onclick": "location.href='/'"})
            return render_centered_html(f'''
                <h1><img src="{images.logo}" type="image/png" alt="Quasarr logo" class="logo"/>Quasarr</h1>
                <p>JDownloader connection not established.</p>
                <p>{back_btn}</p>
            ''')

        # Check for delete status from redirect
        deleted = request.query.get('deleted')
        status_message = ""
        if deleted == '1':
            status_message = '<div class="status-message success">✅ Package deleted successfully.</div>'
        elif deleted == '0':
            status_message = '<div class="status-message error">❌ Failed to delete package.</div>'

        # Get packages data
        downloads = get_packages(shared_state)
        queue = downloads.get('queue', [])
        history = downloads.get('history', [])

        # Separate Quasarr packages from others
        quasarr_queue = [p for p in queue if p.get('cat') != 'not_quasarr']
        other_queue = [p for p in queue if p.get('cat') == 'not_quasarr']
        quasarr_history = [p for p in history if p.get('category') != 'not_quasarr']
        other_history = [p for p in history if p.get('category') == 'not_quasarr']

        def get_category_emoji(cat):
            return {'movies': '🎬', 'tv': '📺', 'docs': '📄', 'not_quasarr': '📦'}.get(cat, '📦')

        def format_size(mb=None, bytes_val=None):
            if bytes_val is not None:
                mb = bytes_val / (1024 * 1024)
            if mb is None or mb == 0:
                return "? MB"
            if mb < 1024:
                return f"{mb:.0f} MB"
            return f"{mb / 1024:.1f} GB"

        def escape_js(s):
            return s.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')

        def render_queue_item(item):
            filename = item.get('filename', 'Unknown')
            percentage = item.get('percentage', 0)
            timeleft = item.get('timeleft', '??:??:??')
            mb = item.get('mb', 0)
            cat = item.get('cat', 'not_quasarr')
            is_archive = item.get('is_archive', False)
            nzo_id = item.get('nzo_id', '')

            is_captcha = '[CAPTCHA' in filename
            if is_captcha:
                status_emoji = '🔒'
            elif '[Extracting]' in filename:
                status_emoji = '📦'
            elif '[Paused]' in filename:
                status_emoji = '⏸️'
            elif '[Linkgrabber]' in filename:
                status_emoji = '🔗'
            else:
                status_emoji = '⬇️'

            display_name = filename
            for prefix in ['[Downloading] ', '[Extracting] ', '[Paused] ', '[Linkgrabber] ', '[CAPTCHA not solved!] ']:
                display_name = display_name.replace(prefix, '')

            archive_badge = '<span class="badge archive">📁 ARCHIVE</span>' if is_archive else ''
            cat_emoji = get_category_emoji(cat)
            size_str = format_size(mb=mb)

            # Progress bar - show "waiting..." for 0%
            if percentage == 0:
                progress_html = '<span class="progress-waiting"></span>'
            else:
                progress_html = f'<div class="progress-track"><div class="progress-fill" style="width: {percentage}%"></div></div>'

            # Action buttons - CAPTCHA left, delete right
            if is_captcha and nzo_id:
                actions = f'''
                    <div class="package-actions">
                        <button class="btn-small primary" onclick="location.href='/captcha?package_id={nzo_id}'">🔓 Solve CAPTCHA</button>
                        <span class="spacer"></span>
                        <button class="btn-small danger" onclick="confirmDelete('{nzo_id}', '{escape_js(display_name)}')">🗑️</button>
                    </div>
                '''
            elif nzo_id:
                actions = f'''
                    <div class="package-actions right-only">
                        <button class="btn-small danger" onclick="confirmDelete('{nzo_id}', '{escape_js(display_name)}')">🗑️</button>
                    </div>
                '''
            else:
                actions = ''

            return f'''
                <div class="package-card">
                    <div class="package-header">
                        <span class="status-emoji">{status_emoji}</span>
                        <span class="package-name">{display_name}</span>
                        {archive_badge}
                    </div>
                    <div class="package-progress">
                        {progress_html}
                        <span class="progress-percent">{percentage}%</span>
                    </div>
                    <div class="package-details">
                        <span>⏱️ {timeleft}</span>
                        <span>💾 {size_str}</span>
                        <span>{cat_emoji} {cat}</span>
                    </div>
                    {actions}
                </div>
            '''

        def render_history_item(item):
            name = item.get('name', 'Unknown')
            status = item.get('status', 'Unknown')
            bytes_val = item.get('bytes', 0)
            category = item.get('category', 'not_quasarr')
            is_archive = item.get('is_archive', False)
            extraction_status = item.get('extraction_status', '')
            fail_message = item.get('fail_message', '')
            nzo_id = item.get('nzo_id', '')

            is_error = status.lower() in ['failed', 'error'] or fail_message
            card_class = 'package-card error' if is_error else 'package-card'

            cat_emoji = get_category_emoji(category)
            size_str = format_size(bytes_val=bytes_val)

            archive_badge = ''
            if is_archive:
                if extraction_status == 'SUCCESSFUL':
                    archive_badge = '<span class="badge extracted">✅ EXTRACTED</span>'
                elif extraction_status == 'RUNNING':
                    archive_badge = '<span class="badge pending">⏳ EXTRACTING</span>'
                else:
                    archive_badge = '<span class="badge archive">📁 ARCHIVE</span>'

            status_emoji = '❌' if is_error else '✅'
            error_html = f'<div class="package-error">⚠️ {fail_message}</div>' if fail_message else ''

            # Delete button for history items
            if nzo_id:
                actions = f'''
                    <div class="package-actions right-only">
                        <button class="btn-small danger" onclick="confirmDelete('{nzo_id}', '{escape_js(name)}')">🗑️</button>
                    </div>
                '''
            else:
                actions = ''

            return f'''
                <div class="{card_class}">
                    <div class="package-header">
                        <span class="status-emoji">{status_emoji}</span>
                        <span class="package-name">{name}</span>
                        {archive_badge}
                    </div>
                    <div class="package-details">
                        <span>💾 {size_str}</span>
                        <span>{cat_emoji} {category}</span>
                    </div>
                    {error_html}
                    {actions}
                </div>
            '''

        # Build queue section
        queue_html = ''
        if quasarr_queue:
            queue_items = ''.join(render_queue_item(item) for item in quasarr_queue)
            queue_html = f'''
                <div class="section">
                    <h3>⬇️ Downloading</h3>
                    <div class="packages-list">{queue_items}</div>
                </div>
            '''
        else:
            queue_html = '<div class="section"><p class="empty-message">No active downloads</p></div>'

        # Build history section
        history_html = ''
        if quasarr_history:
            history_items = ''.join(render_history_item(item) for item in quasarr_history[:10])
            history_html = f'''
                <div class="section">
                    <h3>📜 Recent History</h3>
                    <div class="packages-list">{history_items}</div>
                </div>
            '''

        # Build "other packages" section (non-Quasarr)
        other_html = ''
        other_count = len(other_queue) + len(other_history)
        if other_count > 0:
            other_items = ''
            if other_queue:
                other_items += f'<h4>Queue ({len(other_queue)})</h4>'
                other_items += ''.join(render_queue_item(item) for item in other_queue)
            if other_history:
                other_items += f'<h4>History ({len(other_history)})</h4>'
                other_items += ''.join(render_history_item(item) for item in other_history[:5])

            plural = 's' if other_count != 1 else ''
            other_html = f'''
                <div class="other-packages-section">
                    <details id="otherPackagesDetails">
                        <summary id="otherPackagesSummary">Show {other_count} non-Quasarr package{plural}</summary>
                        <div class="other-packages-content">{other_items}</div>
                    </details>
                </div>
            '''

        back_btn = render_button("Back", "secondary", {"onclick": "location.href='/'"})

        packages_html = f'''
            <h1><img src="{images.logo}" type="image/png" alt="Quasarr logo" class="logo"/>Quasarr</h1>
            <h2>Packages</h2>

            {status_message}

            <div class="refresh-indicator" onclick="location.reload()">
                Auto-refresh in <span id="countdown">10</span>s
            </div>

            <div class="packages-container">
                {queue_html}
                {history_html}
                {other_html}
            </div>

            <p>{back_btn}</p>

            <!-- Delete confirmation modal -->
            <div class="modal" id="deleteModal">
                <div class="modal-content">
                    <h3>🗑️ Delete Package?</h3>
                    <p class="modal-package-name" id="modalPackageName"></p>
                    <div class="modal-warning">
                        <strong>⛔ Warning:</strong> This will permanently delete the package AND all associated files from disk. This action cannot be undone!
                    </div>
                    <div class="modal-buttons">
                        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
                        <button class="btn-danger" id="confirmDeleteBtn">🗑️ Delete Package & Files</button>
                    </div>
                </div>
            </div>

            <style>
                .packages-container {{ max-width: 600px; margin: 0 auto; }}
                .section {{ margin: 20px 0; }}
                .section h3 {{ margin-bottom: 15px; padding-bottom: 8px; border-bottom: 1px solid var(--border-color, #ddd); }}
                .packages-list {{ display: flex; flex-direction: column; gap: 10px; }}

                .package-card {{
                    background: var(--card-bg, #f8f9fa);
                    border: 1px solid var(--card-border, #dee2e6);
                    border-radius: 8px;
                    padding: 12px 15px;
                    transition: transform 0.2s, box-shadow 0.2s;
                }}
                .package-card:hover {{ transform: translateY(-1px); box-shadow: 0 2px 8px var(--card-shadow, rgba(0,0,0,0.1)); }}
                .package-card.error {{ border-color: var(--error-border, #dc3545); background: var(--error-bg, #fff5f5); }}

                .package-header {{ display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }}
                .status-emoji {{ font-size: 1.2em; flex-shrink: 0; }}
                .package-name {{ flex: 1; font-weight: 500; word-break: break-word; line-height: 1.3; }}

                .badge {{ font-size: 0.75em; padding: 2px 6px; border-radius: 4px; white-space: nowrap; flex-shrink: 0; }}
                .badge.archive {{ background: var(--badge-archive-bg, #e3f2fd); color: var(--badge-archive-color, #1565c0); }}
                .badge.extracted {{ background: var(--badge-success-bg, #e8f5e9); color: var(--badge-success-color, #2e7d32); }}
                .badge.pending {{ background: var(--badge-warning-bg, #fff3e0); color: var(--badge-warning-color, #e65100); }}

                .package-progress {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
                .progress-track {{ flex: 1; height: 8px; background: var(--progress-track, #e0e0e0); border-radius: 4px; overflow: hidden; }}
                .progress-fill {{ height: 100%; background: var(--progress-fill, #4caf50); border-radius: 4px; min-width: 4px; }}
                .progress-waiting {{ flex: 1; color: var(--text-muted, #888); font-style: italic; font-size: 0.85em; }}
                .progress-percent {{ font-weight: bold; min-width: 40px; text-align: right; font-size: 0.9em; }}

                .package-details {{ display: flex; flex-wrap: wrap; gap: 15px; font-size: 0.85em; color: var(--text-muted, #666); }}
                .package-error {{ margin-top: 8px; padding: 8px; background: var(--error-msg-bg, #ffebee); border-radius: 4px; font-size: 0.85em; color: var(--error-msg-color, #c62828); }}

                .package-actions {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-color, #eee); display: flex; gap: 8px; align-items: center; }}
                .package-actions .spacer {{ flex: 1; }}
                .package-actions.right-only {{ justify-content: flex-end; }}
                .btn-small {{ padding: 5px 12px; font-size: 0.8em; border-radius: 4px; cursor: pointer; transition: all 0.2s; }}
                .btn-small.primary {{ background: var(--btn-primary-bg, #007bff); color: white; border: none; }}
                .btn-small.primary:hover {{ background: var(--btn-primary-hover, #0056b3); }}
                .btn-small.danger {{ background: transparent; color: var(--btn-danger-text, #dc3545); border: 1px solid var(--btn-danger-border, #dc3545); }}
                .btn-small.danger:hover {{ background: var(--btn-danger-hover-bg, #dc3545); color: white; }}

                .empty-message {{ color: var(--text-muted, #888); font-style: italic; text-align: center; padding: 20px; }}
                .refresh-indicator {{ text-align: center; font-size: 0.85em; color: var(--text-muted, #888); margin-bottom: 15px; cursor: pointer; }}
                .refresh-indicator:hover {{ color: var(--link-color, #0066cc); text-decoration: underline; }}

                .other-packages-section {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--border-color, #ddd); }}
                .other-packages-section summary {{ cursor: pointer; padding: 8px 0; color: var(--text-muted, #666); }}
                .other-packages-section summary:hover {{ color: var(--link-color, #0066cc); }}
                .other-packages-content {{ margin-top: 15px; }}
                .other-packages-content h4 {{ margin: 15px 0 10px 0; font-size: 0.95em; color: var(--text-muted, #666); }}

                /* Status message styling */
                .status-message {{
                    padding: 10px 15px;
                    border-radius: 6px;
                    margin-bottom: 15px;
                    font-weight: 500;
                }}
                .status-message.success {{
                    background: var(--success-bg, #d1e7dd);
                    color: var(--success-color, #198754);
                    border: 1px solid var(--success-border, #a3cfbb);
                }}
                .status-message.error {{
                    background: var(--error-bg, #f8d7da);
                    color: var(--error-color, #dc3545);
                    border: 1px solid var(--error-border, #f1aeb5);
                }}

                /* Modal */
                .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }}
                .modal.show {{ display: flex; }}
                .modal-content {{ background: var(--modal-bg, white); padding: 25px; border-radius: 12px; max-width: 400px; width: 90%; text-align: center; }}
                .modal-content h3 {{ margin: 0 0 15px 0; color: var(--error-msg-color, #c62828); }}
                .modal-package-name {{ font-weight: 500; word-break: break-word; padding: 10px; background: var(--code-bg, #f5f5f5); border-radius: 6px; margin: 10px 0; }}
                .modal-warning {{ background: var(--error-msg-bg, #ffebee); color: var(--error-msg-color, #c62828); padding: 12px; border-radius: 6px; margin: 15px 0; font-size: 0.9em; text-align: left; }}
                .modal-buttons {{ display: flex; gap: 10px; justify-content: center; margin-top: 20px; }}
                .btn-danger {{ background: var(--btn-danger-bg, #dc3545); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 500; }}
                .btn-danger:hover {{ opacity: 0.9; }}

                /* Dark mode */
                @media (prefers-color-scheme: dark) {{
                    :root {{
                        --card-bg: #2d3748; --card-border: #4a5568; --card-shadow: rgba(0,0,0,0.3);
                        --border-color: #4a5568; --text-muted: #a0aec0;
                        --progress-track: #4a5568; --progress-fill: #68d391;
                        --error-border: #fc8181; --error-bg: #3d2d2d; --error-msg-bg: #3d2d2d; --error-msg-color: #fc8181;
                        --badge-archive-bg: #1a365d; --badge-archive-color: #63b3ed;
                        --badge-success-bg: #1c4532; --badge-success-color: #68d391;
                        --badge-warning-bg: #3d2d1a; --badge-warning-color: #f6ad55;
                        --link-color: #63b3ed; --modal-bg: #2d3748; --code-bg: #1a202c;
                        --btn-primary-bg: #3182ce; --btn-primary-hover: #2c5282;
                        --btn-danger-text: #fc8181; --btn-danger-border: #fc8181; --btn-danger-hover-bg: #e53e3e;
                        --success-bg: #1c4532; --success-color: #68d391; --success-border: #276749;
                    }}
                }}
            </style>

            <script>
                let countdown = 10;
                const countdownEl = document.getElementById('countdown');
                const refreshInterval = setInterval(() => {{
                    countdown--;
                    if (countdownEl) countdownEl.textContent = countdown;
                    if (countdown <= 0) location.reload();
                }}, 1000);

                // Clear status message from URL after display
                if (window.location.search.includes('deleted=')) {{
                    const url = new URL(window.location);
                    url.searchParams.delete('deleted');
                    window.history.replaceState({{}}, '', url);
                }}

                // Restore collapse state from localStorage
                const otherDetails = document.getElementById('otherPackagesDetails');
                const otherSummary = document.getElementById('otherPackagesSummary');
                if (otherDetails && otherSummary) {{
                    const count = otherSummary.textContent.match(/\\d+/)?.[0] || '0';
                    const plural = count !== '1' ? 's' : '';
                    if (localStorage.getItem('otherPackagesOpen') === 'true') {{
                        otherDetails.open = true;
                        otherSummary.textContent = 'Hide ' + count + ' non-Quasarr package' + plural;
                    }}
                    otherDetails.addEventListener('toggle', () => {{
                        localStorage.setItem('otherPackagesOpen', otherDetails.open);
                        otherSummary.textContent = (otherDetails.open ? 'Hide ' : 'Show ') + count + ' non-Quasarr package' + plural;
                    }});
                }}

                // Delete modal
                let deletePackageId = null;
                function confirmDelete(packageId, packageName) {{
                    deletePackageId = packageId;
                    document.getElementById('modalPackageName').textContent = packageName;
                    document.getElementById('deleteModal').classList.add('show');
                    clearInterval(refreshInterval);
                }}
                function closeModal() {{
                    document.getElementById('deleteModal').classList.remove('show');
                    deletePackageId = null;
                    location.reload();
                }}
                document.getElementById('confirmDeleteBtn').onclick = function() {{
                    if (deletePackageId) location.href = '/packages/delete/' + encodeURIComponent(deletePackageId);
                }};
                document.getElementById('deleteModal').onclick = function(e) {{ if (e.target === this) closeModal(); }};
                document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeModal(); }});
            </script>
        '''

        return render_centered_html(packages_html)
