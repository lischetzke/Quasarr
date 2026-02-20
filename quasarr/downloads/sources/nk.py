# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import requests
from bs4 import BeautifulSoup

from quasarr.downloads.sources.helpers.abstract_source import AbstractSource
from quasarr.providers.hostname_issues import mark_hostname_issue
from quasarr.providers.log import info

hostname = "nk"


class Source(AbstractSource):
    initials = hostname

    def get_download_links(self, shared_state, url, mirrors, title, password):
        return _get_nk_download_links(shared_state, url, mirrors, title, password)


supported_mirrors = ["rapidgator", "ddownload"]


def _get_nk_download_links(shared_state, url, mirrors, title, password):
    """
    KEEP THE SIGNATURE EVEN IF SOME PARAMETERS ARE UNUSED!

    NK source handler - fetches protected download links from NK pages.
    """

    host = shared_state.values["config"]("Hostnames").get(hostname)
    headers = {
        "User-Agent": shared_state.values["user_agent"],
    }

    session = requests.Session()

    try:
        r = session.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        info(f"Could not fetch release page for {title}: {e}")
        mark_hostname_issue(
            hostname, "download", str(e) if "e" in dir() else "Download error"
        )
        return {"links": []}

    anchors = soup.select("a.btn-orange")
    candidates = []
    for a in anchors:
        mirror = a.text.strip().lower()
        if mirror == "ddl.to":
            mirror = "ddownload"

        if mirror not in supported_mirrors:
            continue

        href = a.get("href", "").strip()
        if not href.lower().startswith(("http://", "https://")):
            href = "https://" + host + href

        try:
            r = requests.head(href, headers=headers, allow_redirects=True, timeout=10)
            r.raise_for_status()
            href = r.url
        except Exception as e:
            info(f"Could not resolve download link for {title}: {e}")
            mark_hostname_issue(
                hostname, "download", str(e) if "e" in dir() else "Download error"
            )
            continue

        candidates.append([href, mirror])

    if not candidates:
        info(f"No external download links found for {title}")

    return {"links": candidates}
