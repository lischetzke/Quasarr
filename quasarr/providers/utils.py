# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re
import socket
import sys
from urllib.parse import urlparse

import requests


class Unbuffered(object):
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)


def is_valid_url(url):
    """Validate if a URL is properly formatted."""
    if "/raw/eX4Mpl3" in url:
        print("Example URL detected. Please provide a valid URL found on pastebin or any other public site!")
        return False

    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def extract_allowed_keys(config, section):
    """
    Extracts allowed keys from the specified section in the configuration.

    :param config: The configuration dictionary.
    :param section: The section from which to extract keys.
    :return: A list of allowed keys.
    """
    if section not in config:
        raise ValueError(f"Section '{section}' not found in configuration.")
    return [key for key, *_ in config[section]]


def extract_kv_pairs(input_text, allowed_keys):
    """
    Extracts key-value pairs from the given text where keys match allowed_keys.

    :param input_text: The input text containing key-value pairs.
    :param allowed_keys: A list of allowed two-letter shorthand keys.
    :return: A dictionary of extracted key-value pairs.
    """
    kv_pattern = re.compile(rf"^({'|'.join(map(re.escape, allowed_keys))})\s*=\s*(.*)$")
    kv_pairs = {}

    for line in input_text.splitlines():
        match = kv_pattern.match(line.strip())
        if match:
            key, value = match.groups()
            kv_pairs[key] = value
        elif "[Hostnames]" in line:
            pass
        else:
            print(f"Skipping line because it does not contain any supported hostname: {line}")

    return kv_pairs


def check_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 0))
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def check_flaresolverr(shared_state, flaresolverr_url):
    # Ensure it ends with /v<digit+>
    if not re.search(r"/v\d+$", flaresolverr_url):
        print(f"FlareSolverr URL does not end with /v#: {flaresolverr_url}")
        return False

    # Try sending a simple test request
    headers = {"Content-Type": "application/json"}
    data = {
        "cmd": "request.get",
        "url": "http://www.google.com/",
        "maxTimeout": 10000
    }

    try:
        response = requests.post(flaresolverr_url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        json_data = response.json()

        # Check if the structure looks like a valid FlareSolverr response
        if "status" in json_data and json_data["status"] == "ok":
            solution = json_data["solution"]
            solution_ua = solution.get("userAgent", None)
            if solution_ua:
                shared_state.update("user_agent", solution_ua)
            return True
        else:
            print(f"Unexpected FlareSolverr response: {json_data}")
            return False

    except Exception as e:
        print(f"Failed to connect to FlareSolverr: {e}")
        return False


def validate_address(address, name):
    if not address.startswith("http"):
        sys.exit(f"Error: {name} '{address}' is invalid. It must start with 'http'.")

    colon_count = address.count(":")
    if colon_count < 1 or colon_count > 2:
        sys.exit(
            f"Error: {name} '{address}' is invalid. It must contain 1 or 2 colons, but it has {colon_count}.")


def is_site_usable(shared_state, shorthand):
    """
    Check if a site is fully configured and usable.

    For sites that don't require login, just checks if hostname is set.
    For login-required sites (al, dd, dl, nx), also checks that login wasn't skipped
    and that credentials exist.

    Args:
        shared_state: Shared state object
        shorthand: Site shorthand (e.g., 'al', 'dd', etc.)

    Returns:
        bool: True if site is usable, False otherwise
    """
    shorthand = shorthand.lower()

    # Check if hostname is set
    hostname = shared_state.values["config"]('Hostnames').get(shorthand)
    if not hostname:
        return False

    login_required_sites = ['al', 'dd', 'dl', 'nx']
    if shorthand not in login_required_sites:
        return True  # No login needed, hostname is enough

    # Check if login was skipped
    if shared_state.values["database"]("skip_login").retrieve(shorthand):
        return False  # Hostname set but login was skipped

    # Check for credentials
    config = shared_state.values["config"](shorthand.upper())
    user = config.get('user')
    password = config.get('password')

    return bool(user and password)
