import logging
import sys
from configparser import ConfigParser
from distutils.command.config import config

from alaya.events import Producer
from flask import Flask, jsonify, request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

app = Flask(__name__)
tenant_config = None


class EngineFactory(dict):
    def __missing__(self, key):
        self[key] = create_engine(key)
        return self[key]


engine_factory = EngineFactory()


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
    global tenant_config
    tenant_config = load_tenant_config("./tenant-config.ini")


@app.post("/emit/<string:tenant>/<string:db>/<string:event>")
def emit(tenant: str, db: str, event: str):
    global tenant_config
    global engine_factory

    if not tenant_config.has_section(tenant):
        return jsonify(tenant=tenant, message="Tenant not found."), 404
    dsn = f"databases.{db}.dsn"
    if not tenant_config.has_option(tenant, dsn):
        return jsonify(message="Invalid database type."), 400

    engine = engine_factory[tenant_config[tenant][dsn]]
    with Session(engine) as session:
        p = Producer(session, tenant)
        p.emmit(event=event, payload=request.json)
        session.commit()
    return jsonify({"tenant": tenant, "event": event})
