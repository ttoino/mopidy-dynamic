# Mopidy Dynamic

[![Latest PyPI version](https://img.shields.io/pypi/v/mopidy-dynamic)](https://pypi.org/p/mopidy-dynamic)
[![CI build status](https://img.shields.io/github/actions/workflow/status/ttoino/mopidy-dynamic/ci.yml)](https://github.com/ttoino/mopidy-dynamic/actions/workflows/ci.yml)

Mopidy extension to generate playlists dynamically.

## Installation

Install by running:

```sh
python3 -m pip install mopidy-dynamic
```

See [this extension's page](https://mopidy.com/ext/dynamic/) for alternative installation methods.

## Configuration

Before starting Mopidy, you must add configuration for mopidy-dynamic to your Mopidy configuration file:

```ini
[dynamic]
enabled = true

# Path to directory with the DPL files.
# Defaults to the extension's data dir.
playlists_dir =

# Backend used to save the playlists.
# Defaults to the bundled M3U backend.
playlists_uri = m3u
```

### DPL files

All dynamic playlists are defined in `.dpl` files.
These files have the following structure:

```dpl
# Lines starting with # are considered comments and ignored
# Empty lines are also ignored

# Non-indented lines define a new operation
operation
    # Indented lines define options in the current operation
    option
# Unknown operations are ignored

# The library operation adds all tracks at a specified URI
library
    # Add all tracks from the local backend
    local:directory?type=track

# The search operation adds all tracks found by a search operation
# Note: backends usually have a limit on the amount of results
search
    # Search all tracks with 'sound' or 'music' in the name
    track_name=sound
    track_name=music
    # All properties supported by PlaybackController.search are supported
    # https://docs.mopidy.com/stable/api/core/#mopidy.core.LibraryController.search

# The exclude operation removes all tracks that satisfy the given constraints
exclude
    # Remove tracks before 2015 and with any artist starting with B
    max_date=2014-12-31
    any_artist=^B

# The include operation keeps all tracks that satisfy the given constraints
include
    # Keep tracks in the first disc, and that end in a
    max_disc_no=1
    name=a$

# Include and exclude support the following options:
# regular expression: uri, name, genre, artist, composer, performer,
#   any_artist (artist, composer, or performer),
#   album_name, album_artist
# date: min_date, max_date, min_album_date, max_album_date
# integer: min_track_no, max_track_no, min_disc_no, max_disc_no,
#   min_length, max_length

# The sort operation sorts all tracks
sort
    # Sort by name
    name
    # If tracks have the same name, sort by album release date
    album.date
```

## Project resources

- [Source code](https://github.com/ttoino/mopidy-dynamic)
- [Issues](https://github.com/ttoino/mopidy-dynamic/issues)
- [Releases](https://github.com/ttoino/mopidy-dynamic/releases)

## Credits

- Original author: [João Pereira](https://github.com/ttoino)
- Current maintainer: [João Pereira](https://github.com/ttoino)
- [Contributors](https://github.com/ttoino/mopidy-dynamic/graphs/contributors)
