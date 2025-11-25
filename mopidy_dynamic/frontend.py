import operator
from typing import TYPE_CHECKING, cast

import pykka
from mopidy.core.listener import CoreListener
from mopidy.internal import path
from mopidy.models import Ref

from . import Extension, logger, translator

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from re import Pattern

    from mopidy.core.actor import Core
    from mopidy.ext import Config
    from mopidy.models import Artist, Track

    from .types import DynamicConfig, FilterOperator, Operator


class DynamicFrontend(pykka.ThreadingActor, CoreListener):
    def __init__(self, config: "Config", core: "Core") -> None:
        super().__init__()

        self.config = config
        self.core = core

        ext_config = cast("DynamicConfig", config[Extension.ext_name])

        self._playlists_dir = (
            path.expand_path(ext_config["playlists_dir"])
            if ext_config["playlists_dir"]
            else Extension.get_data_dir(config)
        )

    def on_start(self) -> None:
        if self.core.playlists is None:
            return

        for pl_path in self._playlists_dir.iterdir():
            name = translator.path_to_name(pl_path)

            playlist = self.core.playlists.create(name, "m3u").get()

            if playlist is None:
                playlist = self.core.playlists.lookup(f"m3u:{name}.m3u8").get()

            if playlist is None:
                continue

            with pl_path.open() as fp:
                operators = translator.load_operators(fp)

            playlist = playlist.replace(tracks=self._apply_operators(operators))

            self.core.playlists.save(playlist)

    def _apply_operators(self, operators: "Iterable[Operator]") -> "list[Track]":
        result: list[Track] = []

        if self.core.library is None:
            return result

        logger.debug("Started operations")
        for op in operators:
            match op["operator_type"]:
                case "library":
                    logger.debug("Started library lookup")
                    refs = self.core.library.browse(op["uri"]).get()
                    results = self.core.library.lookup(
                        [r.uri for r in refs if r.type == Ref.TRACK]
                    ).get()
                    logger.debug("Finished library lookup %s", len(refs))
                    for tracks in results.values():
                        result.extend(tracks)

                case "search":
                    logger.debug("Started search")
                    results = self.core.library.search(
                        {"uri": op["uris"]}, list(op["uris"])
                    ).get()
                    logger.debug("Finished search %s", len(results))
                    for r in results:
                        if r is not None:
                            result.extend(r.tracks)

                case "sort":
                    logger.debug("Started sort")
                    result.sort(key=operator.attrgetter(*op["properties"]))
                    logger.debug("Finished sort")

                case "include" | "exclude":
                    logger.debug("Started filtering")
                    result = list(filter(self._filter_fn(op), result))
                    logger.debug("Finished filtering")

        logger.debug("Finished operations")

        return result

    def _filter_fn(self, op: "FilterOperator") -> "Callable[[Track], bool]":
        def _search(p: "Pattern", v: str) -> bool:
            return p.search(v) is not None

        def _names(l: "Iterable[Artist]") -> "Iterable[str]":
            return map(operator.attrgetter("name"), l)

        def _filter(t: "Track") -> bool:
            result = True

            for k in op:
                match k:
                    case "uri" | "name" | "genre":
                        result &= _search(op[k], getattr(t, k))
                    case "artist" | "composer" | "performer":
                        result &= any(
                            _search(op[k], v) for v in _names(getattr(t, k + "s"))
                        )
                    case "any_artist":
                        result &= any(
                            _search(op[k], v)
                            for v in _names((*t.artists, *t.composers, *t.performers))
                        )
                    case "album_name":
                        result &= _search(op[k], t.album.name)
                    case "album_artist":
                        result &= any(
                            _search(op[k], v) for v in _names(t.album.artists)
                        )
                    case (
                        "min_date"
                        | "max_date"
                        | "min_track_no"
                        | "max_track_no"
                        | "min_disc_no"
                        | "max_disc_no"
                        | "min_length"
                        | "max_length"
                    ):
                        d, p = k.split("_", 1)
                        result &= (operator.ge if d == "min" else operator.le)(
                            getattr(t, p), op[k]
                        )
                    case "min_album_date":
                        result &= t.album.date >= op[k]
                    case "max_album_date":
                        result &= t.album.date <= op[k]

            return result if op["operator_type"] == "include" else not result

        return _filter
