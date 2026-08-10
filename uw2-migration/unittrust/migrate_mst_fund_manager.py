#!/usr/bin/env python3
"""Synchronise non-PRS fund managers from MSSQL into PostgreSQL.

The legacy ``MstFundManagerDetails`` table is rebuilt as a current snapshot by
the source system. The corresponding PostgreSQL table is therefore replaced in
one transaction on every synchronisation. PRS manager tables are intentionally
out of scope for this script.
"""

from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path
from typing import Iterable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "db.ini"
MANAGER_SOURCE_TABLE = "dbo.MstFundManager"
DETAILS_SOURCE_TABLE = "dbo.MstFundManagerDetails"
POSTGRES_MANAGER_TABLE = "fund_upstream.mst_fund_manager"
POSTGRES_DETAILS_TABLE = "fund_upstream.mst_fund_manager_details"

MANAGER_COLUMNS = (
    "datafeed_manager_id",
    "fund_manager_id",
    "fund_manager_name",
    "fund_manager_biography",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
)
DETAILS_COLUMNS = (
    "fund_id",
    "fund_manager_id",
    "fund_manager_start_date",
    "fund_manager_tenure",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync MSSQL MstFundManager data into PostgreSQL."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--count-only", action="store_true")
    return parser.parse_args()


def read_config(config_path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if not config.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    return config


def config_value(
    config: configparser.ConfigParser,
    env_name: str,
    section: str,
    key: str,
    default: str = "",
) -> str:
    return os.environ.get(env_name, "").strip() or config.get(
        section, key, fallback=default
    ).strip()


def connect_mssql(config: configparser.ConfigParser):
    import pyodbc

    driver = config_value(config, "MSSQL_DRIVER", "mssql", "driver", "SQL Server")
    connection_string = ";".join(
        (
            f"DRIVER={{{driver}}}",
            f"SERVER={config_value(config, 'MSSQL_SERVER', 'mssql', 'server')}",
            f"DATABASE={config_value(config, 'MSSQL_DATABASE', 'mssql', 'database')}",
            f"UID={config_value(config, 'MSSQL_USER', 'mssql', 'user')}",
            f"PWD={config_value(config, 'MSSQL_PASSWORD', 'mssql', 'password')}",
            f"Encrypt={config_value(config, 'MSSQL_ENCRYPT', 'mssql', 'encrypt', 'yes')}",
            "TrustServerCertificate="
            + config_value(
                config,
                "MSSQL_TRUST_SERVER_CERTIFICATE",
                "mssql",
                "trust_server_certificate",
                "yes",
            ),
        )
    )
    return pyodbc.connect(connection_string + ";")


def connect_postgres(config: configparser.ConfigParser):
    import pg8000.dbapi

    return pg8000.dbapi.connect(
        host=config_value(config, "PG_HOST", "postgresql", "host"),
        port=int(config_value(config, "PG_PORT", "postgresql", "port", "5432")),
        database=config_value(config, "PG_DATABASE", "postgresql", "database"),
        user=config_value(config, "PG_USER", "postgresql", "user"),
        password=config_value(config, "PG_PASSWORD", "postgresql", "password"),
    )


def source_sql(table_name: str, columns: Sequence[str]) -> str:
    selected_columns = ", ".join(f"[{column}]" for column in columns)
    return f"SELECT {selected_columns} FROM {table_name}"


def placeholders(row_count: int, column_count: int) -> str:
    row = "(" + ", ".join(["%s"] * column_count) + ")"
    return ", ".join([row] * row_count)


def manager_upsert_sql(row_count: int) -> str:
    columns = ", ".join(MANAGER_COLUMNS)
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in MANAGER_COLUMNS
        if column != "fund_manager_id"
    )
    return (
        f"INSERT INTO {POSTGRES_MANAGER_TABLE} ({columns}) "
        f"VALUES {placeholders(row_count, len(MANAGER_COLUMNS))} "
        "ON CONFLICT (fund_manager_id) DO UPDATE SET "
        f"{updates}"
    )


def details_insert_sql(row_count: int) -> str:
    columns = ", ".join(DETAILS_COLUMNS)
    return (
        f"INSERT INTO {POSTGRES_DETAILS_TABLE} ({columns}) "
        f"VALUES {placeholders(row_count, len(DETAILS_COLUMNS))}"
    )


def fetch_rows(source_connection, table_name: str, columns: Sequence[str]):
    cursor = source_connection.cursor()
    try:
        cursor.execute(source_sql(table_name, columns))
        return cursor.fetchall()
    finally:
        cursor.close()


def count_source_rows(source_connection, table_name: str) -> int:
    cursor = source_connection.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return int(cursor.fetchone()[0])
    finally:
        cursor.close()


def batched(rows: Sequence[Sequence], batch_size: int) -> Iterable[Sequence[Sequence]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def flattened(rows: Sequence[Sequence]) -> list:
    return [value for row in rows for value in row]


def upsert_managers(source_connection, target_connection, batch_size: int) -> int:
    rows = fetch_rows(source_connection, MANAGER_SOURCE_TABLE, MANAGER_COLUMNS)
    target_cursor = target_connection.cursor()
    try:
        for batch in batched(rows, batch_size):
            target_cursor.execute(manager_upsert_sql(len(batch)), flattened(batch))
        target_connection.commit()
        return len(rows)
    except Exception:
        target_connection.rollback()
        raise
    finally:
        target_cursor.close()


def refresh_details(source_connection, target_connection, batch_size: int) -> int:
    rows = fetch_rows(source_connection, DETAILS_SOURCE_TABLE, DETAILS_COLUMNS)
    target_cursor = target_connection.cursor()
    try:
        target_cursor.execute(f"DELETE FROM {POSTGRES_DETAILS_TABLE}")
        for batch in batched(rows, batch_size):
            target_cursor.execute(details_insert_sql(len(batch)), flattened(batch))
        target_connection.commit()
        return len(rows)
    except Exception:
        target_connection.rollback()
        raise
    finally:
        target_cursor.close()


def verify_target_tables(target_connection) -> None:
    cursor = target_connection.cursor()
    try:
        cursor.execute(
            "SELECT to_regclass(%s), to_regclass(%s)",
            (POSTGRES_MANAGER_TABLE, POSTGRES_DETAILS_TABLE),
        )
        manager_table, details_table = cursor.fetchone()
    finally:
        cursor.close()
    if not manager_table or not details_table:
        raise RuntimeError(
            "Fund manager target tables are missing. Apply Flyway migration "
            "V1.53__fund_manager_upstream.sql before synchronising."
        )


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than zero")
    config = read_config(args.config)

    source_connection = connect_mssql(config)
    try:
        if args.count_only:
            print(f"MstFundManager: {count_source_rows(source_connection, MANAGER_SOURCE_TABLE)}")
            print(
                "MstFundManagerDetails: "
                f"{count_source_rows(source_connection, DETAILS_SOURCE_TABLE)}"
            )
            return

        target_connection = connect_postgres(config)
        try:
            verify_target_tables(target_connection)
            manager_count = upsert_managers(
                source_connection, target_connection, args.batch_size
            )
            details_count = refresh_details(
                source_connection, target_connection, args.batch_size
            )
        finally:
            target_connection.close()
    finally:
        source_connection.close()

    print(f"Synchronised {manager_count} fund managers.")
    print(f"Synchronised {details_count} fund-manager associations.")


if __name__ == "__main__":
    main()
