import logging
import sys
from configparser import ConfigParser


def load_tenant_config(config_path: str) -> ConfigParser:
    """Load tenant configuration file."""
    try:
        with open(config_path, "rt", encoding="utf-8") as cf:
            config = ConfigParser(delimiters="=")
            config.read_file(cf)
            return config
    except Exception:
        logging.error(f"{config_path}: Unable to load tenant config.")
        sys.exit(1)
