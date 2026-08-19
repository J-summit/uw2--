"""Migrate available bond holdings from UnitTrust MSSQL to local PostgreSQL.

The migration copies the complete source table and uses the legacy composite
primary key for idempotent upserts.
"""

from __future__ import annotations

import argparse
import configparser
import os
from typing import Optional, Sequence, Tuple

import pg8000.dbapi
import pyodbc


DEFAULT_BATCH_SIZE = 1000
DEFAULT_CONFIG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "db.ini")
)
SOURCE_TABLE = "dbo.TrnClientAvailableBondHolding"
TARGET_TABLE = "transaction_service.trn_client_available_bond_holding"
COLUMNS: Tuple[str, ...] = (
    "parcel_id", "client_code", "branch", "fund_id", "purchased_at",
    "dividend_instruction", "payment_mode_code", "portfolio_code", "unit",
    "average_nav", "m_average_nav", "total_inv_unit", "total_mrkt_amount",
    "m_total_mrkt_amount", "total_inv_amount", "m_total_inv_amount",
    "fund_sub_acc", "created_by", "created_at", "created_ip", "updated_by",
    "updated_at", "updated_ip",
)
KEY_COLUMNS: Tuple[str, ...] = (
    "parcel_id", "client_code", "branch", "fund_id", "payment_mode_code",
    "dividend_instruction", "portfolio_code", "fund_sub_acc",
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate UnitTrust available bond holdings"
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    return args


def _read_config(path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if os.path.exists(path):
        config.read(path, encoding="utf-8")
    return config


def _setting(config: configparser.ConfigParser, env_name: str, section: str,
             key: str, default: str = "") -> str:
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        return env_value
    if config.has_option(section, key):
        return config.get(section, key).strip()
    return default


def connect_mssql(config: configparser.ConfigParser):
    driver = _setting(config, "MSSQL_DRIVER", "mssql", "driver", "SQL Server")
    parts = [
        "DRIVER={%s}" % driver,
        "SERVER=%s" % _setting(config, "MSSQL_SERVER", "mssql", "server"),
        "DATABASE=%s" % _setting(config, "MSSQL_DATABASE", "mssql", "database"),
        "UID=%s" % _setting(config, "MSSQL_USER", "mssql", "user"),
        "PWD=%s" % _setting(config, "MSSQL_PASSWORD", "mssql", "password"),
    ]
    if driver.startswith("ODBC Driver"):
        parts.extend((
            "Encrypt=%s" % _setting(
                config, "MSSQL_ENCRYPT", "mssql", "encrypt", "yes"
            ),
            "TrustServerCertificate=%s" % _setting(
                config,
                "MSSQL_TRUST_SERVER_CERTIFICATE",
                "mssql",
                "trust_server_certificate",
                "yes",
            ),
        ))
    return pyodbc.connect(";".join(parts) + ";")


def connect_postgres(config: configparser.ConfigParser):
    return pg8000.dbapi.connect(
        host=_setting(config, "PG_HOST", "postgresql", "host"),
        port=int(_setting(config, "PG_PORT", "postgresql", "port", "5432")),
        database=_setting(config, "PG_DATABASE", "postgresql", "database"),
        user=_setting(config, "PG_USER", "postgresql", "user"),
        password=_setting(config, "PG_PASSWORD", "postgresql", "password"),
    )


def _source_sql() -> str:
    return "SELECT %s FROM %s" % (
        ", ".join("[%s]" % column for column in COLUMNS),
        SOURCE_TABLE,
    )


def _upsert_sql(row_count: int) -> str:
    one_row = "(" + ", ".join(["%s"] * len(COLUMNS)) + ")"
    values = ", ".join([one_row] * row_count)
    updates = ", ".join(
        "%s = EXCLUDED.%s" % (column, column)
        for column in COLUMNS
        if column not in KEY_COLUMNS
    )
    return (
        "INSERT INTO %s (%s) VALUES %s "
        "ON CONFLICT (%s) DO UPDATE SET %s"
    ) % (
        TARGET_TABLE,
        ", ".join(COLUMNS),
        values,
        ", ".join(KEY_COLUMNS),
        updates,
    )


def count_source_rows(source_connection) -> int:
    cursor = source_connection.cursor()
    cursor.execute("SELECT COUNT_BIG(1) FROM %s" % SOURCE_TABLE)
    count = int(cursor.fetchone()[0])
    cursor.close()
    return count


def transfer(source_connection, target_connection, batch_size: int) -> int:
    source_cursor = source_connection.cursor()
    target_cursor = target_connection.cursor()
    source_cursor.execute(_source_sql())
    total = 0
    try:
        while True:
            rows = source_cursor.fetchmany(batch_size)
            if not rows:
                break
            target_cursor.execute(
                _upsert_sql(len(rows)),
                [value for row in rows for value in row],
            )
            target_connection.commit()
            total += len(rows)
            print(f"  {TARGET_TABLE}: {total:,} rows", flush=True)
    except Exception:
        target_connection.rollback()
        raise
    finally:
        source_cursor.close()
        target_cursor.close()
    return total


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    config = _read_config(args.config)
    source_connection = connect_mssql(config)
    target_connection = None
    try:
        if args.count_only:
            print(f"{SOURCE_TABLE}: {count_source_rows(source_connection):,} rows")
            return

        target_connection = connect_postgres(config)
        print("Migrating %s -> %s" % (SOURCE_TABLE, TARGET_TABLE))
        total = transfer(source_connection, target_connection, args.batch_size)
        print(f"Completed {TARGET_TABLE}: {total:,} rows")
    finally:
        if target_connection is not None:
            target_connection.close()
        source_connection.close()


if __name__ == "__main__":
    main()
