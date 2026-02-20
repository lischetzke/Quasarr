from typing import TypedDict


class ReleaseDetails(TypedDict):
    title: str
    hostname: str
    imdb_id: str
    link: str
    size: int
    date: str
    source: str


class Release(TypedDict):
    details: ReleaseDetails
    type: str
