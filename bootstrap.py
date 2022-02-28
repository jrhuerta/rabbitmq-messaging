#!/usr/bin/env python
import sys
import os
from configparser import ConfigParser


def create_mysql_database(index: int):
    os.popen("docker-compose exec mariadb mysql --password=root -e 'create database tenant{index};'")
    return f"mysql://tenant{index}:password@mariadb/tenant{index}"


def create_postgres_database(index: int, schema=False):
    return f"postgresql+psycopg2://tenant{index}:password@pg/tenant{index}"


def main():
    try:
        tenants = int(sys.argv[1])
    except Exception:
        print("Expecting number of tenants as a single integer argument")
        sys.exit(1)

    config = ConfigParser()
    for i in range(tenants):
        tenant = {
            "databases.mysql.dsn": create_mysql_database(i),
            "databases.pgsql.dsn": create_postgres_database(i),
        }
        config[f"tenant{i}"] = tenant
    with open("tenant-config.ini", "wt") as config_file:
        config.write(config_file)


if __name__ == "__main__":
    main()
