# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

import re
import uuid
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from quasarr.providers.cloudflare import (
    flaresolverr_create_session,
    flaresolverr_destroy_session,
    flaresolverr_get,
    is_cloudflare_challenge,
)
from quasarr.providers.hostname_issues import mark_hostname_issue
from quasarr.providers.log import debug, info
from quasarr.providers.utils import is_flaresolverr_available

hostname = "wd"


def resolve_wd_redirect(shared_state, url, session_id=None):
    """
    Follow redirects for a WD mirror URL and return the final destination.
    """
    try:
        # Use FlareSolverr to follow redirects as well, since the redirector might be protected
        r = flaresolverr_get(shared_state, url, session_id=session_id)

        # FlareSolverr follows redirects automatically and returns the final URL
        if r.status_code == 200:
            # Check if we landed on a 404 page (soft 404)
            if r.url.endswith("/404.html"):
                return None
            return r.url
        else:
            info(f"WD blocked attempt to resolve {url}. Status: {r.status_code}")
    except Exception as e:
        info(f"Error fetching redirected URL for {url}: {e}")
        mark_hostname_issue(
            hostname, "download", str(e) if "e" in dir() else "Download error"
        )
    return None


def get_wd_download_links(shared_state, url, mirror, title, password):
    """
    KEEP THE SIGNATURE EVEN IF SOME PARAMETERS ARE UNUSED!

    WD source handler - resolves redirects and returns protected download links.
    """

    wd = shared_state.values["config"]("Hostnames").get("wd")

    if not is_flaresolverr_available(shared_state):
        info(
            "WD is protected by Cloudflare but FlareSolverr is not configured. "
            "Please configure FlareSolverr in the web UI to access this site."
        )
        mark_hostname_issue(hostname, "download", "FlareSolverr required but missing.")
        return {"links": [], "imdb_id": None}

    # Create a temporary FlareSolverr session for this download attempt
    session_id = str(uuid.uuid4())
    created_session = flaresolverr_create_session(shared_state, session_id)
    if not created_session:
        info("Could not create FlareSolverr session. Proceeding without session...")
        session_id = None
    else:
        debug(f"Created FlareSolverr session: {session_id}")

    try:
        r = flaresolverr_get(shared_state, url, session_id=session_id)
        if r.status_code == 403 or is_cloudflare_challenge(r.text):
            info("Could not bypass Cloudflare protection with FlareSolverr!")
            mark_hostname_issue(hostname, "download", "Cloudflare challenge failed")
            return {"links": [], "imdb_id": None}

        if r.status_code >= 400:
            mark_hostname_issue(
                hostname, "download", f"Download error: {str(r.status_code)}"
            )

        soup = BeautifulSoup(r.text, "html.parser")

        # extract IMDb id if present
        imdb_id = None
        a_imdb = soup.find("a", href=re.compile(r"imdb\.com/title/tt\d+"))
        if a_imdb:
            m = re.search(r"(tt\d+)", a_imdb["href"])
            if m:
                imdb_id = m.group(1)
                debug(f"Found IMDb id: {imdb_id}")

        # find Downloads card
        header = soup.find(
            "div",
            class_="card-header",
            string=re.compile(r"^\s*Downloads\s*$", re.IGNORECASE),
        )
        if not header:
            info(
                f"WD Downloads section not found. Grabbing download links for {title} not possible!"
            )
            return {"links": [], "imdb_id": None}

        card = header.find_parent("div", class_="card")
        body = card.find("div", class_="card-body")
        link_tags = body.find_all(
            "a", href=True, class_=lambda c: c and "background-" in c
        )

        results = []
        try:
            for a in link_tags:
                raw_href = a["href"]
                full_link = urljoin(f"https://{wd}", raw_href)

                # resolve any redirects using the same session
                resolved = resolve_wd_redirect(
                    shared_state, full_link, session_id=session_id
                )

                if resolved:
                    if resolved.endswith("/404.html"):
                        info(f"Link {resolved} is dead!")
                        continue

                    # determine hoster
                    hoster = a.get_text(strip=True) or None
                    if not hoster:
                        for cls in a.get("class", []):
                            if cls.startswith("background-"):
                                hoster = cls.split("-", 1)[1]
                                break

                    if mirror and mirror.lower() not in hoster.lower():
                        debug(
                            f'Skipping link from "{hoster}" (not the desired mirror "{mirror}")!'
                        )
                        continue

                    results.append([resolved, hoster])
        except Exception as e:
            info(
                f"WD site has been updated. Parsing download links for {title} not possible! Error: {e}"
            )

        return {
            "links": results,
            "imdb_id": imdb_id,
        }

    except RuntimeError as e:
        # Catch FlareSolverr not configured error
        info(f"WD access failed: {e}")
        return {"links": [], "imdb_id": None}
    except Exception as e:
        info(
            f"WD site has been updated. Grabbing download links for {title} not possible! Error: {e}"
        )
        return {"links": [], "imdb_id": None}
    finally:
        # Always destroy the session
        if session_id:
            debug(f"Destroying FlareSolverr session: {session_id}")
            flaresolverr_destroy_session(shared_state, session_id)
