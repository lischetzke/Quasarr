# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import quasarr.providers.html_images as images
from quasarr.downloads.packages import get_packages, delete_package
from quasarr.providers import shared_state
from quasarr.providers.html_templates import render_button, render_centered_html


def _get_category_emoji(cat):
    return {'movies': '🎬', 'tv': '📺', 'docs': '📄', 'not_quasarr': '❓'}.get(cat, '❓')


def _format_size(mb=None, bytes_val=None):
    if bytes_val is not None:
        # Handle bytes directly for better precision with small files
        if bytes_val == 0:
            return "? MB"
        if bytes_val < 1024 * 1024:  # Less than 1 MB
            kb = bytes_val / 1024
            if kb < 1:
                return f"{bytes_val} B"
            return f"{kb:.0f} KB"
        mb = bytes_val / (1024 * 1024)
    if mb is None or mb == 0:
        return "? MB"
    if mb < 1:
        return f"{mb * 1024:.0f} KB"
    if mb < 1024:
        return f"{mb:.0f} MB"
    return f"{mb / 1024:.1f} GB"


def _escape_js(s):
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')


def _render_queue_item(item):
    filename = item.get('filename', 'Unknown')
    percentage = item.get('percentage', 0)
    timeleft = item.get('timeleft', '??:??:??')
    bytes_val = item.get('bytes', 0)
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

    archive_badge = '<span class="badge archive">📁</span>' if is_archive else ''
    cat_emoji = _get_category_emoji(cat)
    size_str = _format_size(bytes_val=bytes_val)

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
                <button class="btn-small danger" onclick="confirmDelete('{nzo_id}', '{_escape_js(display_name)}')">🗑️</button>
            </div>
        '''
    elif nzo_id:
        actions = f'''
            <div class="package-actions right-only">
                <button class="btn-small danger" onclick="confirmDelete('{nzo_id}', '{_escape_js(display_name)}')">🗑️</button>
            </div>
        '''
    else:
        actions = ''

    return f'''
        <div class="package-card">
            <div class="package-header">
                <span class="status-emoji">{status_emoji}</span>
                <span class="package-name">{display_name}</span>
            </div>
            <div class="package-progress">
                {progress_html}
                <span class="progress-percent">{percentage}%</span>
            </div>
            <div class="package-details">
                <span>⏱️ {timeleft}</span>
                <span>💾 {size_str}</span>
                <span>{cat_emoji}</span>
                {archive_badge}
            </div>
            {actions}
        </div>
    '''


def _render_history_item(item):
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

    cat_emoji = _get_category_emoji(category)
    size_str = _format_size(bytes_val=bytes_val)

    archive_badge = ''
    if is_archive:
        if extraction_status == 'SUCCESSFUL':
            archive_badge = '<span class="badge extracted">✅</span>'
        elif extraction_status == 'RUNNING':
            archive_badge = '<span class="badge pending">⏳</span>'
        else:
            archive_badge = '<span class="badge archive">📁</span>'

    status_emoji = '❌' if is_error else '✅'
    error_html = f'<div class="package-error">⚠️ {fail_message}</div>' if fail_message else ''

    # Delete button for history items
    if nzo_id:
        actions = f'''
            <div class="package-actions right-only">
                <button class="btn-small danger" onclick="confirmDelete('{nzo_id}', '{_escape_js(name)}')">🗑️</button>
            </div>
        '''
    else:
        actions = ''

    return f'''
        <div class="{card_class}">
            <div class="package-header">
                <span class="status-emoji">{status_emoji}</span>
                <span class="package-name">{name}</span>
            </div>
            <div class="package-details">
                <span>💾 {size_str}</span>
                <span>{cat_emoji}</span>
                {archive_badge}
            </div>
            {error_html}
            {actions}
        </div>
    '''


def _render_packages_content():
    """Render just the packages content (used for both full page and AJAX refresh)."""
    downloads = get_packages(shared_state)
    queue = downloads.get('queue', [])
    history = downloads.get('history', [])

    # Separate Quasarr packages from others
    quasarr_queue = [p for p in queue if p.get('cat') != 'not_quasarr']
    other_queue = [p for p in queue if p.get('cat') == 'not_quasarr']
    quasarr_history = [p for p in history if p.get('category') != 'not_quasarr']
    other_history = [p for p in history if p.get('category') == 'not_quasarr']

    # Check if there's anything at all
    has_quasarr_content = quasarr_queue or quasarr_history
    has_other_content = other_queue or other_history
    has_any_content = has_quasarr_content or has_other_content

    # Build queue section (only if has items)
    queue_html = ''
    if quasarr_queue:
        queue_items = ''.join(_render_queue_item(item) for item in quasarr_queue)
        queue_html = f'''
            <div class="section">
                <h3>⬇️ Downloading</h3>
                <div class="packages-list">{queue_items}</div>
            </div>
        '''

    # Build history section (only if has items)
    history_html = ''
    if quasarr_history:
        history_items = ''.join(_render_history_item(item) for item in quasarr_history[:10])
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
            other_items += ''.join(_render_queue_item(item) for item in other_queue)
        if other_history:
            other_items += f'<h4>History ({len(other_history)})</h4>'
            other_items += ''.join(_render_history_item(item) for item in other_history[:5])

        plural = 's' if other_count != 1 else ''
        # Only add separator class if there's Quasarr content above
        section_class = 'other-packages-section' if has_quasarr_content else 'other-packages-section no-separator'
        other_html = f'''
            <div class="{section_class}">
                <details id="otherPackagesDetails">
                    <summary id="otherPackagesSummary">Show {other_count} other package{plural}</summary>
                    <div class="other-packages-content">{other_items}</div>
                </details>
            </div>
        '''

    # Only show "no downloads" if there's literally nothing
    empty_html = ''
    if not has_any_content:
        empty_html = '<p class="empty-message">No packages</p>'

    return f'''
        <div class="packages-container">
            {queue_html}
            {history_html}
            {other_html}
            {empty_html}
        </div>
    '''


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

    @app.get('/api/packages/content')
    def packages_content_api():
        """AJAX endpoint - returns just the packages content HTML for background refresh."""
        try:
            device = shared_state.values["device"]
        except KeyError:
            device = None

        if not device:
            return '<p class="empty-message">JDownloader connection not established.</p>'

        return _render_packages_content()

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

        # Get rendered packages content using shared helper
        packages_content = _render_packages_content()

        back_btn = render_button("Back", "secondary", {"onclick": "location.href='/'"})

        packages_html = f'''
            <h1><img src="{images.logo}" type="image/png" alt="Quasarr logo" class="logo"/>Quasarr</h1>
            <h2>Packages</h2>

            {status_message}

            <div id="slow-warning" class="slow-warning" style="display:none;">⚠️ Slow connection detected</div>

            <div id="packages-content">
                {packages_content}
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

                .slow-warning {{
                    text-align: center;
                    font-size: 0.85em;
                    color: #856404;
                    background: #fff3cd;
                    border: 1px solid #ffc107;
                    padding: 8px 12px;
                    border-radius: 6px;
                    margin-bottom: 15px;
                }}
                @media (prefers-color-scheme: dark) {{
                    .slow-warning {{
                        color: #ffc107;
                        background: #3d3510;
                        border-color: #665c00;
                    }}
                }}

                .other-packages-section {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--border-color, #ddd); }}
                .other-packages-section.no-separator {{ margin-top: 0; padding-top: 0; border-top: none; }}
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
                // Background refresh - fetches content via AJAX, waits 5s between refresh cycles
                let refreshPaused = false;
                let slowConnection = false;

                async function refreshContent() {{
                    if (refreshPaused) return;

                    const startTime = Date.now();
                    const warningEl = document.getElementById('slow-warning');

                    // Save scroll position before refresh
                    const scrollY = window.scrollY;

                    // Show warning after 5s if still loading
                    const slowTimer = setTimeout(() => {{
                        slowConnection = true;
                        if (warningEl) warningEl.style.display = 'block';
                    }}, 5000);

                    try {{
                        const response = await fetch('/api/packages/content');
                        const elapsed = Date.now() - startTime;

                        clearTimeout(slowTimer);

                        // Update slow connection state
                        if (elapsed < 5000) {{
                            slowConnection = false;
                            if (warningEl) warningEl.style.display = 'none';
                        }} else {{
                            slowConnection = true;
                            if (warningEl) warningEl.style.display = 'block';
                        }}

                        if (response.ok) {{
                            const html = await response.text();
                            const container = document.getElementById('packages-content');
                            if (container && html) {{
                                container.innerHTML = html;
                                restoreCollapseState();
                                // Restore scroll position after content update
                                window.scrollTo(0, scrollY);
                            }}
                        }}
                    }} catch (e) {{
                        clearTimeout(slowTimer);
                    }}
                    setTimeout(refreshContent, 5000);
                }}

                function restoreCollapseState() {{
                    const otherDetails = document.getElementById('otherPackagesDetails');
                    const otherSummary = document.getElementById('otherPackagesSummary');
                    if (otherDetails && otherSummary) {{
                        const count = otherSummary.textContent.match(/\\d+/)?.[0] || '0';
                        const plural = count !== '1' ? 's' : '';
                        if (localStorage.getItem('otherPackagesOpen') === 'true') {{
                            otherDetails.open = true;
                            otherSummary.textContent = 'Hide ' + count + ' other package' + plural;
                        }}
                        // Re-attach event listener
                        otherDetails.onclick = null;
                        otherDetails.addEventListener('toggle', function() {{
                            localStorage.setItem('otherPackagesOpen', this.open);
                            const summaryEl = document.getElementById('otherPackagesSummary');
                            if (summaryEl) {{
                                summaryEl.textContent = (this.open ? 'Hide ' : 'Show ') + count + ' other package' + plural;
                            }}
                        }});
                    }}
                }}

                // Initial collapse state setup
                restoreCollapseState();

                // Clear status message from URL after display and auto-hide after 5s
                if (window.location.search.includes('deleted=')) {{
                    const url = new URL(window.location);
                    url.searchParams.delete('deleted');
                    window.history.replaceState({{}}, '', url);

                    // Hide the status message after 5 seconds
                    const statusMsg = document.querySelector('.status-message');
                    if (statusMsg) {{
                        setTimeout(() => {{
                            statusMsg.style.transition = 'opacity 0.3s';
                            statusMsg.style.opacity = '0';
                            setTimeout(() => statusMsg.remove(), 300);
                        }}, 5000);
                    }}

                    // Reset refresh - start fresh 5s countdown after delete
                    setTimeout(refreshContent, 5000);
                }} else {{
                    // Normal start - 5s delay
                    setTimeout(refreshContent, 5000);
                }}

                // Delete modal
                let deletePackageId = null;
                function confirmDelete(packageId, packageName) {{
                    deletePackageId = packageId;
                    document.getElementById('modalPackageName').textContent = packageName;
                    document.getElementById('deleteModal').classList.add('show');
                    refreshPaused = true;  // Pause background refresh while modal is open
                }}
                function closeModal() {{
                    document.getElementById('deleteModal').classList.remove('show');
                    deletePackageId = null;
                    refreshPaused = false;  // Resume background refresh
                }}
                document.getElementById('confirmDeleteBtn').onclick = function() {{
                    if (deletePackageId) location.href = '/packages/delete/' + encodeURIComponent(deletePackageId);
                }};
                document.getElementById('deleteModal').onclick = function(e) {{ if (e.target === this) closeModal(); }};
                document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeModal(); }});
            </script>
        '''

        return render_centered_html(packages_html)
