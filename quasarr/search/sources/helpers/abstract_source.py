from abc import ABC, abstractmethod

from quasarr.providers import shared_state
from quasarr.search.sources.helpers.release import Release


class AbstractSource(ABC):
    @property
    @abstractmethod
    def initials(self) -> str:
        pass

    @property
    @abstractmethod
    def supports_imdb(self) -> bool:
        pass

    @property
    @abstractmethod
    def supports_phrase(self) -> bool:
        pass

    @property
    @abstractmethod
    def supported_categories(self) -> list[int]:
        pass

    @property
    def requires_login(self) -> bool:
        return False

    @abstractmethod
    def search(
        self,
        shared_state: shared_state,
        start_time: float,
        search_category: str,
        search_string: str = "",
        season: int = None,
        episode: int = None,
    ) -> list[Release]:
        pass

    @abstractmethod
    def feed(
        self,
        shared_state: shared_state,
        start_time: float,
        search_category: str,
    ) -> list[Release]:
        pass
