from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, cast

from mopidy.internal.validation import SEARCH_FIELDS

from .types import FilterOperator, LibraryOperator, SearchOperator, SortOperator

if TYPE_CHECKING:
    from typing import IO

    from mopidy.backend import SearchField

    from .types import Operator


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


def load_operators(fp: IO[str]) -> list[Operator]:
    result: list[Operator] = []
    current_operator: Operator | None = None

    for line in fp.readlines():
        stripped_line = line.strip()

        if stripped_line == "" or stripped_line.startswith("#"):
            continue

        if line.startswith(" ") and current_operator is not None:
            # Parameters
            match current_operator["operator_type"]:
                case "library":
                    current_operator["uri"] = stripped_line

                case "search":
                    key, value = stripped_line.split("=", 1)

                    if key not in cast("set[SearchField]", SEARCH_FIELDS):
                        continue

                    if key not in current_operator["query"]:
                        current_operator["query"][key] = []

                    current_operator["query"][key].append(value)

                case "sort":
                    current_operator["properties"] = current_operator["properties"] + (
                        stripped_line,
                    )

                case "include" | "exclude":
                    key, value = stripped_line.split("=", 1)

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
                            current_operator[key] = re.compile(value)
                        case (
                            "min_date"
                            | "max_date"
                            | "min_album_date"
                            | "max_album_date"
                        ):
                            current_operator[key] = date.fromisoformat(value)
                        case (
                            "min_track_no"
                            | "max_track_no"
                            | "min_disc_no"
                            | "max_disc_no"
                        ):
                            current_operator[key] = int(value)

        else:
            # Definition
            if current_operator is not None:
                result.append(current_operator)

            match stripped_line:
                case "library":
                    current_operator = LibraryOperator(operator_type="library", uri="")
                case "search":
                    current_operator = SearchOperator(operator_type="search", query={})
                case "sort":
                    current_operator = SortOperator(operator_type="sort", properties=())
                case "include" | "exclude":
                    current_operator = FilterOperator(operator_type=stripped_line)
                case _:
                    current_operator = None

    if current_operator is not None:
        result.append(current_operator)

    return result
