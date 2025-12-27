# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from quasarr.providers.log import info


def derive_mirror_from_url(url):
    """Extract hoster name from URL hostname."""
    try:
        hostname = urlparse(url).netloc.lower()
        if hostname.startswith('www.'):
            hostname = hostname[4:]
        parts = hostname.split('.')
        if len(parts) >= 2:
            return parts[-2]
        return hostname
    except:
        return "unknown"


def get_dt_download_links(shared_state, url, mirror, title, password):
    """
    KEEP THE SIGNATURE EVEN IF SOME PARAMETERS ARE UNUSED!

    DT source handler - returns plain download links.
    """

    headers = {"User-Agent": shared_state.values["user_agent"]}
    session = requests.Session()

    try:
        resp = session.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        article = soup.find("article")
        if not article:
            info(f"Could not find article block on DT page for {title}")
            return None

        body = article.find("div", class_="card-body")
        if not body:
            info(f"Could not find download section for {title}")
            return None

        anchors = body.find_all("a", href=True)

    except Exception as e:
        info(f"DT site has been updated. Grabbing download links for {title} not possible! ({e})")
        return None

    filtered = []
    for a in anchors:
        href = a["href"].strip()

        if not href.lower().startswith(("http://", "https://")):
            continue
        lower = href.lower()
        if "imdb.com" in lower or "?ref=" in lower:
            continue
        if mirror and mirror not in href:
            continue

        mirror_name = derive_mirror_from_url(href)
        filtered.append([href, mirror_name])

    # regex fallback if still empty
    if not filtered:
        text = body.get_text(separator="\n")
        urls = re.findall(r'https?://[^\s<>"\']+', text)
        seen = set()
        for u in urls:
            u = u.strip()
            if u not in seen:
                seen.add(u)
                low = u.lower()
                if low.startswith(("http://", "https://")) and "imdb.com" not in low and "?ref=" not in low:
                    if not mirror or mirror in u:
                        mirror_name = derive_mirror_from_url(u)
                        filtered.append([u, mirror_name])

    return {"links": filtered} if filtered else None
