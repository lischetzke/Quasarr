# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

from quasarr.downloads.sources.helpers.abstract_source import AbstractSource


class Source(AbstractSource):
    initials = "sj"

    def get_download_links(self, shared_state, url, mirrors, title, password):
        return _get_sj_download_links(shared_state, url, mirrors, title, password)


def _get_sj_download_links(shared_state, url, mirrors, title, password):
    """
    KEEP THE SIGNATURE EVEN IF SOME PARAMETERS ARE UNUSED!

    SJ source handler - the site itself acts as a protected crypter.
    Returns the URL for CAPTCHA solving via userscript.
    """

    return {"links": [[url, "junkies"]]}
