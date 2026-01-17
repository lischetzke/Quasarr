# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

from bottle import Bottle

import quasarr.providers.html_images as images
from quasarr.api.arr import setup_arr_routes
from quasarr.api.captcha import setup_captcha_routes
from quasarr.api.config import setup_config
from quasarr.api.packages import setup_packages_routes
from quasarr.api.sponsors_helper import setup_sponsors_helper_routes
from quasarr.api.statistics import setup_statistics
from quasarr.providers import shared_state
from quasarr.providers.html_templates import render_button, render_centered_html
from quasarr.providers.web_server import Server
from quasarr.storage.config import Config


def get_api(shared_state_dict, shared_state_lock):
    shared_state.set_state(shared_state_dict, shared_state_lock)

    app = Bottle()

    setup_arr_routes(app)
    setup_captcha_routes(app)
    setup_config(app, shared_state)
    setup_statistics(app, shared_state)
    setup_sponsors_helper_routes(app)
    setup_packages_routes(app)

    @app.get('/')
    def index():
        protected = shared_state.get_db("protected").retrieve_all_titles()
        api_key = Config('API').get('key')

        # Get quick status summary
        try:
            device = shared_state.values.get("device")
            jd_connected = device is not None
        except:
            jd_connected = False

        # CAPTCHA banner
        captcha_hint = ""
        if protected:
            plural = 's' if len(protected) > 1 else ''
            captcha_hint = f"""
            <div class="alert alert-warning">
                <span class="alert-icon">🔒</span>
                <div class="alert-content">
                    <strong>{len(protected)} link{plural} waiting for CAPTCHA</strong>
                    {"" if shared_state.values.get("helper_active") else '<br><a href="https://github.com/rix1337/Quasarr?tab=readme-ov-file#sponsorshelper" target="_blank">Sponsors get automated CAPTCHA solutions!</a>'}
                </div>
                <div class="alert-action">
                    {render_button(f"Solve CAPTCHA{plural}", 'primary', {'onclick': "location.href='/captcha'"})}
                </div>
            </div>
            """

        # JDownloader status
        jd_status = f"""
            <div class="status-bar">
                <span class="status-item {'status-ok' if jd_connected else 'status-error'}">
                    {'✅' if jd_connected else '❌'} JDownloader {'Connected' if jd_connected else 'Disconnected'}
                </span>
            </div>
        """

        info = f"""
        <h1><img src="{images.logo}" type="image/png" alt="Quasarr logo" class="logo"/>Quasarr</h1>

        {jd_status}
        {captcha_hint}

        <div class="quick-actions">
            <a href="/packages" class="action-card">
                <span class="action-icon">📦</span>
                <span class="action-label">Packages</span>
            </a>
            <a href="/statistics" class="action-card">
                <span class="action-icon">📊</span>
                <span class="action-label">Statistics</span>
            </a>
            <a href="/hostnames" class="action-card">
                <span class="action-icon">🌐</span>
                <span class="action-label">Hostnames</span>
            </a>
            <a href="/flaresolverr" class="action-card">
                <span class="action-icon">🛡️</span>
                <span class="action-label">FlareSolverr</span>
            </a>
        </div>

        <div class="section">
            <details id="apiDetails">
                <summary id="apiSummary">⚙️ API Configuration</summary>
                <div class="api-settings">
                    <p class="api-hint">Use these settings for <strong>Newznab Indexer</strong> and <strong>SABnzbd Download Client</strong> in Radarr/Sonarr</p>

                    <div class="input-group">
                        <label>URL</label>
                        <div class="input-row">
                            <input id="urlInput" type="text" readonly value="{shared_state.values['internal_address']}" />
                            <button id="copyUrl" type="button">Copy</button>
                        </div>
                    </div>

                    <div class="input-group">
                        <label>API Key</label>
                        <div class="input-row">
                            <input id="apiKeyInput" type="password" readonly value="{api_key}" />
                            <button id="toggleKey" type="button">Show</button>
                            <button id="copyKey" type="button">Copy</button>
                        </div>
                    </div>

                    <p style="margin-top: 15px;">
                        {render_button("Regenerate API key", "secondary", {"onclick": "if(confirm('Regenerate API key?')) location.href='/regenerate-api-key';"})}
                    </p>
                </div>
            </details>
        </div>

        <div class="section help-link">
            <a href="https://github.com/rix1337/Quasarr?tab=readme-ov-file#instructions" target="_blank">
                📖 Setup Instructions & Documentation
            </a>
        </div>

        <style>
            .status-bar {{
                display: flex;
                justify-content: center;
                gap: 20px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }}
            .status-item {{
                font-size: 0.9em;
                padding: 6px 12px;
                border-radius: 20px;
                background: var(--status-bg, #f5f5f5);
            }}
            .status-ok {{ color: var(--status-ok, #2e7d32); }}
            .status-error {{ color: var(--status-error, #c62828); }}

            .alert {{
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                gap: 12px;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 25px;
            }}
            .alert-warning {{
                background: var(--alert-warning-bg, #fff3e0);
                border: 1px solid var(--alert-warning-border, #ffb74d);
            }}
            .alert-icon {{ font-size: 1.5em; }}
            .alert-content {{ }}
            .alert-content a {{ color: var(--link-color, #0066cc); }}
            .alert-action {{ margin-top: 5px; }}

            .quick-actions {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 12px;
                max-width: 500px;
                margin: 0 auto 30px auto;
            }}
            @media (max-width: 500px) {{
                .quick-actions {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}
            .action-card {{
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 15px 10px;
                background: var(--card-bg, #f8f9fa);
                border: 1px solid var(--card-border, #dee2e6);
                border-radius: 10px;
                text-decoration: none;
                color: inherit;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .action-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px var(--card-shadow, rgba(0,0,0,0.1));
                border-color: var(--card-hover-border, #007bff);
            }}
            .action-icon {{ font-size: 1.8em; margin-bottom: 5px; }}
            .action-label {{ font-size: 0.85em; font-weight: 500; }}

            .section {{ margin: 20px 0; max-width: 500px; margin-left: auto; margin-right: auto; }}
            details {{ background: var(--card-bg, #f8f9fa); border: 1px solid var(--card-border, #dee2e6); border-radius: 8px; }}
            summary {{
                cursor: pointer;
                padding: 12px 15px;
                font-weight: 500;
                list-style: none;
            }}
            summary::-webkit-details-marker {{ display: none; }}
            summary::before {{ content: '▶ '; font-size: 0.8em; }}
            details[open] summary::before {{ content: '▼ '; }}
            summary:hover {{ color: var(--link-color, #0066cc); }}

            .api-settings {{ padding: 15px; border-top: 1px solid var(--card-border, #dee2e6); }}
            .api-hint {{ font-size: 0.9em; color: var(--text-muted, #666); margin-bottom: 15px; }}
            .input-group {{ margin-bottom: 15px; }}
            .input-group label {{ display: block; font-weight: 500; margin-bottom: 6px; font-size: 0.95em; text-align: left; }}
            .input-row {{
                display: flex;
                gap: 8px;
                align-items: stretch;
            }}
            .input-row input {{
                flex: 1;
                padding: 8px 12px;
                border: 1px solid var(--input-border, #ced4da);
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.9em;
                background: var(--input-bg, #e9ecef);
                color: var(--fg-color, #212529);
                min-width: 0;
                margin: 0;
            }}
            .input-row button {{
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.9em;
                font-weight: 500;
                transition: background 0.2s;
                white-space: nowrap;
                margin: 0;
                flex-shrink: 0;
            }}
            #copyUrl, #copyKey {{
                background: var(--btn-primary-bg, #007bff);
                color: white;
            }}
            #copyUrl:hover, #copyKey:hover {{
                background: var(--btn-primary-hover, #0056b3);
            }}
            #toggleKey {{
                background: var(--btn-secondary-bg, #6c757d);
                color: white;
            }}
            #toggleKey:hover {{
                background: var(--btn-secondary-hover, #545b62);
            }}

            .help-link {{
                text-align: center;
                padding: 15px;
                background: var(--card-bg, #f8f9fa);
                border: 1px solid var(--card-border, #dee2e6);
                border-radius: 8px;
            }}
            .help-link a {{
                color: var(--link-color, #0066cc);
                text-decoration: none;
                font-weight: 500;
            }}
            .help-link a:hover {{ text-decoration: underline; }}

            /* Dark mode */
            @media (prefers-color-scheme: dark) {{
                :root {{
                    --status-bg: #2d3748;
                    --status-ok: #68d391;
                    --status-error: #fc8181;
                    --alert-warning-bg: #3d3520;
                    --alert-warning-border: #d69e2e;
                    --card-bg: #2d3748;
                    --card-border: #4a5568;
                    --card-shadow: rgba(0,0,0,0.3);
                    --card-hover-border: #63b3ed;
                    --text-muted: #a0aec0;
                    --link-color: #63b3ed;
                    --input-bg: #1a202c;
                    --input-border: #4a5568;
                    --btn-primary-bg: #3182ce;
                    --btn-primary-hover: #2c5282;
                    --btn-secondary-bg: #4a5568;
                    --btn-secondary-hover: #2d3748;
                }}
            }}
        </style>

        <script>
            (function() {{
                var urlInput = document.getElementById('urlInput');
                var copyUrlBtn = document.getElementById('copyUrl');
                var apiInput = document.getElementById('apiKeyInput');
                var toggleBtn = document.getElementById('toggleKey');
                var copyKeyBtn = document.getElementById('copyKey');

                function copyToClipboard(text, button, callback) {{
                    if (navigator.clipboard && navigator.clipboard.writeText) {{
                        navigator.clipboard.writeText(text).then(function() {{
                            var originalText = button.innerText;
                            button.innerText = 'Copied!';
                            setTimeout(function() {{
                                button.innerText = originalText;
                                if (callback) callback();
                            }}, 1500);
                        }}).catch(function() {{
                            fallbackCopy(text, button, callback);
                        }});
                    }} else {{
                        fallbackCopy(text, button, callback);
                    }}
                }}

                function fallbackCopy(text, button, callback) {{
                    var textarea = document.createElement('textarea');
                    textarea.value = text;
                    textarea.style.position = 'fixed';
                    textarea.style.opacity = '0';
                    document.body.appendChild(textarea);
                    textarea.select();
                    try {{
                        document.execCommand('copy');
                        var originalText = button.innerText;
                        button.innerText = 'Copied!';
                        setTimeout(function() {{
                            button.innerText = originalText;
                            if (callback) callback();
                        }}, 1500);
                    }} catch (e) {{
                        alert('Copy failed. Please copy manually.');
                    }}
                    document.body.removeChild(textarea);
                }}

                if (copyUrlBtn) {{
                    copyUrlBtn.onclick = function() {{
                        copyToClipboard(urlInput.value, copyUrlBtn);
                    }};
                }}

                if (copyKeyBtn) {{
                    copyKeyBtn.onclick = function() {{
                        copyToClipboard(apiInput.value, copyKeyBtn, function() {{
                            // Re-hide the API key after copying
                            apiInput.type = 'password';
                            toggleBtn.innerText = 'Show';
                        }});
                    }};
                }}

                if (toggleBtn) {{
                    toggleBtn.onclick = function() {{
                        if (apiInput.type === 'password') {{
                            apiInput.type = 'text';
                            toggleBtn.innerText = 'Hide';
                        }} else {{
                            apiInput.type = 'password';
                            toggleBtn.innerText = 'Show';
                        }}
                    }};
                }}
            }})();
        </script>
        """
        return render_centered_html(info)

    @app.get('/regenerate-api-key')
    def regenerate_api_key():
        api_key = shared_state.generate_api_key()
        return f"""
        <script>
          alert('API key replaced with: {api_key}');
          window.location.href = '/';
        </script>
        """

    Server(app, listen='0.0.0.0', port=shared_state.values["port"]).serve_forever()
