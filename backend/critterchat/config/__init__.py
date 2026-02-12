import yaml

from .config import Config


__all__ = ["Config", "load_config"]


def load_config(filename: str, config: Config) -> None:
    from ..data import Data

    config.update(yaml.safe_load(open(filename)))
    config.set_filename(filename)
    config["database"]["engine"] = Data.create_engine(config)
    config["filename"] = filename
