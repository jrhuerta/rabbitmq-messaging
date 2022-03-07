import asyncio
import json
import logging
import sys
from itertools import cycle

import aio_pika
import asyncclick as click
from alaya.nabu import load_tenant_config
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from .db import Event
from .utils import gather_with_concurrency


def prepare_connection_strings(dsn_key: str, config_file: str):
    dsn_key = "databases.postgres.dsn"
    config = load_tenant_config(config_file)
    conn_strings = {}
    for org in config.sections():
        try:
            dsn = config[org][dsn_key]
        except KeyError as ex:
            logging.warning(f"{org}: skipping, {dsn_key} not configured.")
            continue
        try:
            url = make_url(dsn)
            async_drivername = {
                "mysql": "mysql+aiomysql",
                "postgresql": "postgresql+asyncpg",
            }.get(url.drivername.split("+", 1)[0])
            if not async_drivername:
                logging.warning(f"{org}: skipping, {url.drivername} not supported.")
                continue
            conn_strings[org] = str(url.set(drivername=async_drivername))
        except Exception:
            logging.warning(f"{org}: skipping, unable to connect to outbox.")
            continue
    return conn_strings


async def process_outbox(
    org: str,
    engine: str,
    channel: aio_pika.abc.AbstractChannel,
    exchange_name: str,
):
    logging.info(f"{org}: pulling from outbox...")
    try:
        exchange = None
        async with AsyncSession(engine) as session:
            result = await session.execute(
                select(Event).order_by("id").limit(10).with_for_update()
            )
            for event in result.scalars():
                if not exchange:
                    exchange = await channel.declare_exchange(
                        exchange_name, aio_pika.ExchangeType.TOPIC
                    )
                msg = aio_pika.Message(
                    json.dumps(event.as_dict(), default=str).encode("utf-8"),
                    content_type="application/json",
                    content_encoding="utf-8",
                    headers={"org": event.org},
                )
                resp = await exchange.publish(msg, routing_key=event.event)
                # logging.info(event)
    except ConnectionRefusedError:
        logging.warning(f"{org}: {repr(engine.url)} connection refused, skipping")
    except ProgrammingError as ex:
        logging.warning(f"{org}: {repr(ex)}, skipping")


@click.command()
@click.option(
    "-t",
    "--tenant-config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    envvar="NABU_CONFIG",
    show_envvar=True,
    default="./tenant-config.ini",
    show_default=True,
    required=True,
    help="Tenant configuration file.",
)
@click.option(
    "--dsn-key",
    type=click.STRING,
    default="databases.postgres.dsn",
    show_default=True,
    required=True,
    help="Configuration key used to fetch database connection string.",
)
@click.option(
    "-b",
    "--broker",
    type=click.STRING,
    envvar="BROKER",
    default="amqp://guest:guest@rabbitmq/",
    show_default=True,
    required=True,
    help="RabbitMQ message broker connection string",
)
@click.option(
    "-e",
    "--exchange",
    type=click.STRING,
    envvar="Exchange",
    required=True,
    help="Service exchange name.",
)
@click.option(
    "-i",
    "--interval",
    type=click.FLOAT,
    default=5,
    show_default=True,
    required=True,
    help="Message pooling interval.",
)
async def outbox(
    tenant_config: str, dsn_key: str, broker: str, exchange: str, interval: int
):
    conn_strings = prepare_connection_strings(
        dsn_key=dsn_key, config_file=tenant_config
    )
    if not conn_strings:
        logging.info("Empty connection string pool, calling it a day!")
        sys.exit(1)
    sql_connections = {
        k: create_async_engine(v, pool_pre_ping=True, pool_recycle=600)
        for k, v in conn_strings.items()
    }

    try:
        mq_connection = await aio_pika.connect_robust(broker)
    except ConnectionError as ex:
        logging.error("Unable to connect to broker, calling it a day!")
        sys.exit(2)

    channels = {o: await mq_connection.channel() for o in sql_connections.keys()}

    while True:
        await gather_with_concurrency(
            10,
            *map(
                process_outbox,
                sql_connections.keys(),
                sql_connections.values(),
                channels.values(),
                cycle([exchange]),
            ),
        )
        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    outbox()
