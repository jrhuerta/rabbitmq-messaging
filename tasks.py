import os
import time
from itertools import cycle
from configparser import ConfigParser

from invoke import UnexpectedExit, task
from alaya.events.db import Base
from sqlalchemy import create_engine


def create_outbox_table(dsn):
    engine = create_engine(dsn)
    Base.metadata.create_all(engine)
    engine.dispose()


def create_mysql_database(c, admin_user, admin_password, database, user, password):
    c.run(
        f"docker-compose exec -T mariadb mysql -u {admin_user} --password={admin_password} "
        '-e "'
        f"create database if not exists {database};"
        f"grant all on {database}.* to '{user}'@'%' identified by '{password}';"
        '"',
        echo=True,
    )
    dsn = f"mysql://{user}:{password}@mariadb/{database}"
    create_outbox_table(dsn.replace("@mariadb/", "@127.0.0.1:3306/"))
    return dsn


def create_postgres_database(
    c, admin_user, admin_password, database, user, password, schemas=False
):
    try:
        r = c.run(
            f'docker-compose exec -T pg psql -U {admin_user} -c "create database {database}"',
            echo=True,
        )
    except UnexpectedExit as ex:
        if "already exists" not in ex.result.stderr:
            raise
    try:
        c.run(
            f"docker-compose exec -T pg psql -U {admin_user} "
            '-c "'
            f"create user {user} with password '{password}'; "
            f"grant all privileges on database {database} to {user}; "
            '"',
            echo=True,
        )
    except UnexpectedExit as ex:
        if "already exists" not in ex.result.stderr:
            raise
    dsn = f"postgresql+psycopg2://{user}:{password}@pg/{database}"
    create_outbox_table(dsn.replace("@pg/", "@127.0.0.1:5432/"))
    return dsn


@task
def db(
    c,
    count=1,
    mysql_admin_user="root",
    mysql_admin_password="root",
    postgres_admin_user="postgres",
    postgres_admin_password="root",
    db_name_prefix="db",
    db_user_prefix="user",
    db_password="password",
    org_prefix="tenant",
    config_file="tenant-config.ini",
):
    c.run("docker-compose up -d mariadb pg", echo=True)
    print("sleeping 5s...")
    time.sleep(5)
    config = ConfigParser()
    try:
        with open(config_file, "rt") as f:
            config.read_file(f)
        print(f"{config_file}: read config file.")
    except FileNotFoundError as ex:
        pass

    for i in range(count):
        org = f"{org_prefix}{i}"
        database = f"{db_name_prefix}{i}"
        user = f"{db_user_prefix}{i}"

        if not config.has_section(org):
            config[org] = {}

        config[org]["databases.mysql.dsn"] = create_mysql_database(
            c, mysql_admin_user, mysql_admin_password, database, user, db_password
        )
        config[org]["databases.postgres.dsn"] = create_postgres_database(
            c, postgres_admin_user, postgres_admin_password, database, user, db_password
        )

    with open(config_file, "wt") as f:
        config.write(f)
        print(f"{config_file}: updated config file.")


@task
def clean(c):
    volumes = map(
        lambda p, v: f"{p}_{v}",
        cycle([os.path.basename(os.getcwd())]),
        ["mariadb_dv", "pg_dv"],
    )
    c.run("docker-compose rm -fs mariadb pg", echo=True)
    c.run(f"docker volume rm {' '.join(volumes)}", echo=True)
    c.run("docker-compose up -d mariadb pg", echo=True)


@task
def adminer_pg(c):
    c.run("gopen 'http://localhost:8080/?pgsql=pg&username=postgres'")


@task
def adminer_mysql(c):
    c.run("gopen 'http://localhost:8080/?server=mariadb&username=root'")


@task
def rabbitmq(c):
    c.run("gopen 'http://localhost:15672'")
