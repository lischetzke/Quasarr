# -*- coding: utf-8 -*-
# Quasarr
# Project by https://github.com/rix1337

from abc import ABC, abstractmethod


class AbstractSource(ABC):
    @property
    @abstractmethod
    def initials(self) -> str:
        pass

    @abstractmethod
    def get_download_links(
        self,
        shared_state,
        url: str,
        mirrors: list[str],
        title: str,
        password: str,
    ) -> dict:
        pass
