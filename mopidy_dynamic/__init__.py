import logging
import pathlib
from importlib.metadata import version
from typing import TYPE_CHECKING

from mopidy import config, ext
from mopidy.config import types

if TYPE_CHECKING:
    from mopidy.config.schemas import ConfigSchema
    from mopidy.ext import Registry

__dist_name__ = "Mopidy-Dynamic"
__version__ = version(__dist_name__)
__folder__ = pathlib.Path(__file__).parent

logger = logging.getLogger(__name__)


class Extension(ext.Extension):
    dist_name = __dist_name__
    ext_name = "dynamic"
    version = __version__

    def get_default_config(self) -> str:
        return config.read(__folder__ / "ext.conf")

    def get_config_schema(self) -> "ConfigSchema":
        schema = super().get_config_schema()
        schema["playlists_dir"] = types.Path(optional=True)
        return schema

    def setup(self, registry: "Registry") -> None:
        from .frontend import DynamicFrontend  # noqa: PLC0415

        registry.add("frontend", DynamicFrontend)
