# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

from quasarr.providers.html_templates import render_button
from quasarr.storage.config import Config


def get_jdownloader_status(shared_state):
    """Get JDownloader connection status and device name."""
    try:
        device = shared_state.values.get("device")
        jd_connected = device is not None and device is not False
    except:
        jd_connected = False

    jd_config = Config("JDownloader")
    jd_device = jd_config.get("device") or ""

    dev_name = jd_device if jd_device else "JDownloader"
    dev_name_safe = (
        dev_name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    if jd_connected:
        status_text = f"✅ {dev_name_safe} connected"
        status_class = "success"
    elif jd_device:
        status_text = f"❌ {dev_name_safe} disconnected"
        status_class = "error"
    else:
        status_text = "❌ JDownloader disconnected"
        status_class = "error"

    return {
        "connected": jd_connected,
        "device_name": jd_device,
        "status_text": status_text,
        "status_class": status_class,
    }


def get_jdownloader_modal_script():
    """Return the JavaScript for the JDownloader configuration modal."""
    jd_config = Config("JDownloader")
    jd_user = jd_config.get("user") or ""
    jd_pass = jd_config.get("password") or ""
    jd_device = jd_config.get("device") or ""

    jd_user_js = jd_user.replace("\\", "\\\\").replace("'", "\\'")
    jd_pass_js = jd_pass.replace("\\", "\\\\").replace("'", "\\'")
    jd_device_js = jd_device.replace("\\", "\\\\").replace("'", "\\'")

    return f"""
    <script>
    function openJDownloaderModal() {{
        var currentUser = '{jd_user_js}';
        var currentPass = '{jd_pass_js}';
        var currentDevice = '{jd_device_js}';
        
        var content = `
            <div id="jd-step-1">
                <input type="hidden" id="jd-current-device" value="${{currentDevice}}">
                <p><strong>JDownloader must be running and connected to My JDownloader!</strong></p>
                <div style="margin-bottom: 1rem;">
                    <label style="display:block; font-size: 0.875rem;">E-Mail</label>
                    <input type="text" id="jd-user" value="${{currentUser}}" placeholder="user@example.org" style="width: 100%; padding: 0.375rem 0.75rem; border: 1px solid #ced4da; border-radius: 0.25rem;">
                </div>
                <div style="margin-bottom: 1rem;">
                    <label style="display:block; font-size: 0.875rem;">Password</label>
                    <input type="password" id="jd-pass" value="${{currentPass}}" placeholder="Password" style="width: 100%; padding: 0.375rem 0.75rem; border: 1px solid #ced4da; border-radius: 0.25rem;">
                </div>
                <div id="jd-status" style="margin-bottom: 0.5rem; font-size: 0.875rem; min-height: 1.25em;"></div>
                <button class="btn-primary" onclick="verifyJDCredentials()">Verify Credentials</button>
            </div>
            
            <div id="jd-step-2" style="display:none;">
                <p>Select your JDownloader instance:</p>
                <div style="margin-bottom: 1rem;">
                    <select id="jd-device" style="width: 100%; padding: 0.375rem 0.75rem; border: 1px solid #ced4da; border-radius: 0.25rem;"></select>
                </div>
                <div id="jd-save-status" style="margin-bottom: 0.5rem; font-size: 0.875rem; min-height: 1.25em;"></div>
                <button class="btn-primary" onclick="saveJDSettings()">Save</button>
            </div>
        `;
        
        showModal('Configure JDownloader', content, '<button class="btn-secondary" onclick="closeModal()">Close</button>');
    }}

    function verifyJDCredentials() {{
        var user = document.getElementById('jd-user').value;
        var pass = document.getElementById('jd-pass').value;
        var statusDiv = document.getElementById('jd-status');
        
        statusDiv.innerHTML = 'Verifying...';
        statusDiv.style.color = 'var(--secondary, #6c757d)';
        
        fetch('/api/jdownloader/verify', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ user: user, pass: pass }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                var select = document.getElementById('jd-device');
                select.innerHTML = '';
                var currentDevice = document.getElementById('jd-current-device').value;
                data.devices.forEach(device => {{
                    var opt = document.createElement('option');
                    opt.value = device;
                    opt.innerHTML = device;
                    if (device === currentDevice) {{
                        opt.selected = true;
                    }}
                    select.appendChild(opt);
                }});
                
                document.getElementById('jd-step-1').style.display = 'none';
                document.getElementById('jd-step-2').style.display = 'block';
            }} else {{
                statusDiv.innerHTML = '❌ ' + (data.message || 'Verification failed');
                statusDiv.style.color = '#dc3545';
            }}
        }})
        .catch(error => {{
            statusDiv.innerHTML = '❌ Error: ' + error.message;
            statusDiv.style.color = '#dc3545';
        }});
    }}

    function saveJDSettings() {{
        var user = document.getElementById('jd-user').value;
        var pass = document.getElementById('jd-pass').value;
        var device = document.getElementById('jd-device').value;
        var statusDiv = document.getElementById('jd-save-status');
        
        statusDiv.innerHTML = 'Saving...';
        statusDiv.style.color = 'var(--secondary, #6c757d)';
        
        fetch('/api/jdownloader/save', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ user: user, pass: pass, device: device }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                statusDiv.innerHTML = '✅ ' + data.message;
                statusDiv.style.color = '#198754';
                setTimeout(function() {{
                    window.location.reload();
                }}, 1000);
            }} else {{
                statusDiv.innerHTML = '❌ ' + data.message;
                statusDiv.style.color = '#dc3545';
            }}
        }})
        .catch(error => {{
            statusDiv.innerHTML = '❌ Error: ' + error.message;
            statusDiv.style.color = '#dc3545';
        }});
    }}
    </script>
    """


def get_jdownloader_status_pill(shared_state):
    """Return the HTML for the JDownloader status pill."""
    status = get_jdownloader_status(shared_state)

    return f"""
        <span class="status-pill {status["status_class"]}" 
              onclick="openJDownloaderModal()" 
              style="cursor: pointer;"
              title="Click to configure JDownloader">
            {status["status_text"]}
        </span>
    """


def get_jdownloader_disconnected_page(shared_state, back_url="/"):
    """Return a full error page when JDownloader is disconnected."""
    import quasarr.providers.html_images as images
    from quasarr.providers.html_templates import render_centered_html

    status_pill = get_jdownloader_status_pill(shared_state)
    modal_script = get_jdownloader_modal_script()

    back_btn = render_button(
        "Back", "secondary", {"onclick": f"location.href='{back_url}'"}
    )

    content = f'''
        <h1><img src="{images.logo}" type="image/png" alt="Quasarr logo" class="logo"/>Quasarr</h1>
        <div class="status-bar">
            {status_pill}
        </div>
        <p>{back_btn}</p>
        <style>
            .status-pill {{
                font-size: 0.9em;
                padding: 8px 16px;
                border-radius: 0.5rem;
                font-weight: 500;
                transition: transform 0.1s ease;
            }}
            .status-pill:hover {{
                transform: scale(1.05);
            }}
            .status-pill.success {{
                background: var(--status-success-bg, #e8f5e9);
                color: var(--status-success-color, #2e7d32);
                border: 1px solid var(--status-success-border, #a5d6a7);
            }}
            .status-pill.error {{
                background: var(--status-error-bg, #ffebee);
                color: var(--status-error-color, #c62828);
                border: 1px solid var(--status-error-border, #ef9a9a);
            }}
            /* Dark mode */
            @media (prefers-color-scheme: dark) {{
                :root {{
                    --status-success-bg: #1c4532;
                    --status-success-color: #68d391;
                    --status-success-border: #276749;
                    --status-error-bg: #3d2d2d;
                    --status-error-color: #fc8181;
                    --status-error-border: #c53030;
                }}
            }}
        </style>
        {modal_script}
    '''

    return render_centered_html(content)
