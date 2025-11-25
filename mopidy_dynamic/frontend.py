import operator
from typing import TYPE_CHECKING, cast

import pykka
from mopidy.core.listener import CoreListener
from mopidy.internal import path
from mopidy.models import Ref
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from . import Extension, logger, translator

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from datetime import date
    from re import Pattern

    from mopidy.core.actor import Core
    from mopidy.ext import Config
    from mopidy.models import Album, Artist, Playlist, SearchResult, Track
    from watchdog.events import (
        DirCreatedEvent,
        DirDeletedEvent,
        DirModifiedEvent,
        DirMovedEvent,
    )

    from .types import DynamicConfig, FilterOperator, Operator


class DynamicFrontend(pykka.ThreadingActor, CoreListener, FileSystemEventHandler):
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

        self._playlists_uri = ext_config["playlists_uri"]

        self._playlists: dict[str, str] = {}
        self._ignore_changed: set[str] = set()

        self._observer = Observer()

    def on_start(self) -> None:
        if self.core.playlists is None or self._playlists_dir is None:
            return

        self._observer.schedule(
            self,
            str(self._playlists_dir),
            event_filter=[
                FileCreatedEvent,
                FileDeletedEvent,
                FileModifiedEvent,
                FileMovedEvent,
            ],
        )
        self._observer.start()

        for pl_path in self._playlists_dir.iterdir():
            name = translator.path_to_name(pl_path)

            if name is None:
                continue

            playlist = self._name_to_playlist(name)

            if playlist is None:
                continue

            self._update_playlist(playlist)

    def on_stop(self) -> None:
        self._observer.stop()
        self._observer.join()

    def playlist_changed(self, playlist: "Playlist") -> None:
        name = cast("str", playlist.name)
        if self._playlists[name] != playlist.uri or name in self._ignore_changed:
            return

        self._ignore_changed.discard(name)
        self._update_playlist(playlist)

    def playlist_deleted(self, uri: str) -> None:
        for name, old_uri in self._playlists.items():
            if old_uri != uri:
                continue

            playlist = self._name_to_playlist(name)

            if playlist is not None:
                self._update_playlist(playlist)

            return

    def on_created(self, event: "DirCreatedEvent | FileCreatedEvent") -> None:
        pl_path = path.expand_path(event.src_path)

        if pl_path is None:
            return

        name = translator.path_to_name(pl_path)

        if name is None:
            return

        playlist = self._name_to_playlist(name)

        if playlist is None:
            return

        self._update_playlist(playlist)

    def on_deleted(self, event: "DirDeletedEvent | FileDeletedEvent") -> None:
        pl_path = path.expand_path(event.src_path)

        if pl_path is None:
            return

        name = translator.path_to_name(pl_path)

        if name is None:
            return

        if self.core.playlists is not None and name in self._playlists:
            uri = self._playlists.pop(name)
            cast("pykka.Future", self.core.playlists.delete(uri)).get()

    def on_modified(self, event: "DirModifiedEvent | FileModifiedEvent") -> None:
        pl_path = path.expand_path(event.src_path)

        if pl_path is None:
            return

        name = translator.path_to_name(pl_path)

        if name is None:
            return

        playlist = self._name_to_playlist(name)

        if playlist is None:
            return

        self._update_playlist(playlist)

    def on_moved(self, event: "DirMovedEvent | FileMovedEvent") -> None:
        old_path = path.expand_path(event.src_path)

        if old_path is None:
            return

        old_name = translator.path_to_name(old_path)

        if old_name is None:
            return

        if self.core.playlists is not None and old_name in self._playlists:
            uri = self._playlists.pop(old_name)
            cast("pykka.Future", self.core.playlists.delete(uri)).get()

        new_path = path.expand_path(event.dest_path)

        if new_path is None:
            return

        name = translator.path_to_name(new_path)

        if name is None:
            return

        playlist = self._name_to_playlist(name)

        if playlist is None:
            return

        self._update_playlist(playlist)

    def _name_to_playlist(self, name: str) -> "Playlist | None":
        if self.core.playlists is None:
            return None

        playlist = None
        if name in self._playlists:
            playlist = cast(
                "pykka.Future[Playlist | None]",
                self.core.playlists.lookup(self._playlists[name]),
            ).get()

        if playlist is None:
            playlist = cast(
                "pykka.Future[Playlist | None]",
                self.core.playlists.create(name, self._playlists_uri),
            ).get()

        if playlist is not None:
            self._playlists[name] = cast("str", playlist.uri)

        return playlist

    def _update_playlist(self, playlist: "Playlist") -> None:
        if self.core.playlists is None or self._playlists_dir is None:
            return

        playlist_path = self._playlists_dir / translator.name_to_path(
            cast("str", playlist.name)
        )

        with playlist_path.open() as fp:
            operators = translator.load_operators(fp)

        playlist = playlist.replace(tracks=self._apply_operators(operators))

        cast("pykka.Future", self.core.playlists.save(playlist)).get()
        self._ignore_changed.add(cast("str", playlist.name))

    def _apply_operators(self, operators: "Iterable[Operator]") -> "list[Track]":
        result: list[Track] = []

        if self.core.library is None:
            return result

        logger.debug("Started operations")
        for op in operators:
            match op["operator_type"]:
                case "library":
                    logger.debug("Started library lookup")
                    refs = cast(
                        "pykka.Future[list[Ref] | None]",
                        self.core.library.browse(op["uri"]),
                    ).get()

                    if refs is None:
                        continue

                    results = cast(
                        "pykka.Future[dict[str, list[Track]]]",
                        self.core.library.lookup(
                            [r.uri for r in refs if r.type == Ref.TRACK]
                        ),
                    ).get()
                    logger.debug("Finished library lookup %s", len(refs))
                    for tracks in results.values():
                        result.extend(tracks)

                case "search":
                    logger.debug("Started search")
                    results = cast(
                        "pykka.Future[list[SearchResult]]",
                        self.core.library.search({"uri": op["uris"]}, list(op["uris"])),
                    ).get()
                    logger.debug("Finished search %s", len(results))
                    for r in results:
                        if r is not None and r.tracks is not None:
                            result.extend(cast("list[Track]", r.tracks))

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
            album = cast("Album", t.album)

            for prop, wanted in op.items():
                match prop:
                    case "uri" | "name" | "genre":
                        result &= _search(cast("Pattern", wanted), getattr(t, prop))
                    case "artist" | "composer" | "performer":
                        result &= any(
                            _search(cast("Pattern", wanted), v)
                            for v in _names(getattr(t, prop + "s"))
                        )
                    case "any_artist":
                        result &= any(
                            _search(cast("Pattern", wanted), v)
                            for v in _names(
                                (
                                    *cast("Iterable[Artist]", t.artists),
                                    *cast("Iterable[Artist]", t.composers),
                                    *cast("Iterable[Artist]", t.performers),
                                )
                            )
                        )
                    case "album_name":
                        result &= _search(
                            cast("Pattern", wanted), cast("str", album.name)
                        )
                    case "album_artist":
                        result &= any(
                            _search(cast("Pattern", wanted), v)
                            for v in _names(cast("Iterable[Artist]", album.artists))
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
                        d, p = prop.split("_", 1)
                        result &= (operator.ge if d == "min" else operator.le)(
                            getattr(t, p), cast("date | int", wanted)
                        )
                    case "min_album_date":
                        result &= cast("date", album.date) >= cast("date", wanted)
                    case "max_album_date":
                        result &= cast("date", album.date) <= cast("date", wanted)

            return result if op["operator_type"] == "include" else not result

        return _filter
