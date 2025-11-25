from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path
    from re import Pattern
    from typing import Literal, Required

    from mopidy.backend import Uri


class DynamicConfig(TypedDict):
    playlists_dir: "Path | None"
    playlists_uri: str


class LibraryOperator(TypedDict):
    operator_type: "Required[Literal['library']]"

    uri: "Uri"


class SearchOperator(TypedDict):
    operator_type: "Required[Literal['search']]"

    uris: tuple[str, ...]


class FilterOperator(TypedDict, total=False):
    operator_type: "Required[Literal['include', 'exclude']]"

    uri: "Pattern"
    name: "Pattern"
    genre: "Pattern"

    min_track_no: int
    max_track_no: int
    min_disc_no: int
    max_disc_no: int
    min_date: "date"
    max_date: "date"
    min_length: int
    max_length: int

    any_artist: "Pattern"
    artist: "Pattern"
    composer: "Pattern"
    performer: "Pattern"

    album_name: "Pattern"
    album_artist: "Pattern"

    min_album_date: "date"
    max_album_date: "date"


class SortOperator(TypedDict):
    operator_type: "Literal['sort']"

    properties: tuple[str, ...]


Operator = LibraryOperator | SearchOperator | FilterOperator | SortOperator
