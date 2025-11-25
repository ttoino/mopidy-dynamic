from __future__ import annotations

import os
import re
import urllib.parse
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from mopidy.internal import path
from mopidy.models import Playlist, Ref, Track

from . import Extension
from .types import FilterOperator, LibraryOperator, SearchOperator, SortOperator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import IO

    from mopidy.backend import Uri

    from .types import Operator


def path_to_uri(
    path: Path,
    scheme: str = Extension.ext_name,
) -> Uri:
    """Convert file path to URI."""
    bytes_path = os.path.normpath(bytes(path))
    uripath = urllib.parse.quote_from_bytes(bytes_path)
    return urllib.parse.urlunsplit((scheme, None, uripath, None, None))


def uri_to_path(uri: Uri) -> Path:
    """Convert URI to file path."""
    return path.uri_to_path(uri)


def path_to_name(path: Path) -> str | None:
    """Extract name from file path."""
    name = bytes(Path(path.stem))
    try:
        return name.decode(errors="replace")
    except UnicodeError:
        return None


def name_to_path(
    name: str,
    ext: str | None = ".dpl",
    sep: str = "|",
) -> Path:
    """Convert name with optional extension to file path."""
    name = name.replace(os.sep, sep) + ext if ext else name.replace(os.sep, sep)
    return Path(name)


def operator_to_uri(operator: Operator, scheme: str = Extension.ext_name) -> Uri:
    match operator["operator_type"]:
        case "sort":
            properties_str = "/".join(map(urllib.parse.quote, operator["properties"]))

        case _:
            properties: list[str] = []

            for prop, value in operator.items():
                if value is not None:
                    val = (
                        value.pattern if isinstance(value, re.Pattern) else repr(value)
                    )
                    val = urllib.parse.quote(val)
                    properties.append(f"{prop}/{val}")

            properties_str = ":".join(properties)

    return f"{scheme}:{operator['operator_type']}:{properties_str}"


def uri_to_operator(uri: Uri) -> Operator | None:
    parts = uri.split(":")

    if len(parts) < 3:
        return None

    match parts[1]:
        case "library" if len(parts) == 3:
            return LibraryOperator(
                operator_type="library", uri=urllib.parse.unquote(parts[2])
            )

        case "search":
            return SearchOperator(
                operator_type="search",
                uris=tuple(map(urllib.parse.unquote, parts[2].split("/"))),
            )

        case "sort" if len(parts) == 3:
            return SortOperator(
                operator_type="sort",
                properties=tuple(map(urllib.parse.unquote, parts[2].split("/"))),
            )

        case "include" | "exclude":
            result = FilterOperator(operator_type=parts[1])

            for prop in parts[2:]:
                key, val = prop.split("/")
                val = urllib.parse.unquote(val)

                match key:
                    case (
                        "uri"
                        | "name"
                        | "genre"
                        | "any_artist"
                        | "artist"
                        | "composer"
                        | "performer"
                        | "album_name"
                        | "album_artist"
                    ):
                        result[key] = re.compile(val)
                    case "min_date" | "max_date" | "min_album_date" | "max_album_date":
                        result[key] = date.fromisoformat(val)
                    case (
                        "min_track_no" | "max_track_no" | "min_disc_no" | "max_disc_no"
                    ):
                        result[key] = int(val)

            return result


def load_operators(fp: IO[str]) -> list[Operator]:
    return list(filter(None, (uri_to_operator(line.strip()) for line in fp)))


def playlist(
    path: Path,
    items: Iterable[Ref | Track] | None = None,
    mtime: float | None = None,
) -> Playlist:
    if items is None:
        items = []
    return Playlist(
        uri=path_to_uri(path),
        name=path_to_name(path),
        tracks=tuple(Track(uri=item.uri, name=item.name) for item in items),
        last_modified=(int(mtime * 1000) if mtime else None),
    )
