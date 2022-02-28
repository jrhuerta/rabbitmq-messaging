import logging
import sys
from configparser import ConfigParser
from distutils.command.config import config

from flask import Flask, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)
tenant_config = None


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


@app.before_first_request
def init_app():
    global config
    config = load_tenant_config("./tenant-config.ini")


@app.post("/emit/<string:tenant>/<string:event>")
def emit(tenant: str, event: str):
    return jsonify({"tenant": tenant, "event": event})
