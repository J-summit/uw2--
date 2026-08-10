"""Migrate MstFundIncomeDistributionHistory from UnitTrust MSSQL to PostgreSQL.

The target table is created by wealth-fund-service Flyway migration V1.51.
This script only transfers data and can be safely re-run: source composite keys
are upserted into fund_upstream.mst_fund_income_distribution_history.

Examples:
    python migrate_mst_fund_income_distribution_history.py --count-only
    python migrate_mst_fund_income_distribution_history.py --batch-size 500
"""

from __future__ import annotations

import argparse
import configparser
import os
from typing import Optional, Sequence, Tuple

import pg8000.dbapi
import pyodbc


DEFAULT_BATCH_SIZE = 500
DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "db.ini")
SOURCE_TABLE = "dbo.MstFundIncomeDistributionHistory"
TARGET_SCHEMA = "fund_upstream"
TARGET_TABLE = "mst_fund_income_distribution_history"
TARGET_QUALIFIED_TABLE = f"{TARGET_SCHEMA}.{TARGET_TABLE}"
COLUMNS: Tuple[str, ...] = (
    "fund_id",
    "distribution_type",
    "excluding_date",
    "reinvestment_date",
    "gross_income_dis_rate",
    "net_income_dis_rate",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
)
KEY_COLUMNS: Tuple[str, ...] = (
    "fund_id",
    "distribution_type",
    "excluding_date",
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate UnitTrust MstFundIncomeDistributionHistory to PostgreSQL"
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="only count source rows; do not connect to PostgreSQL or write data",
    )
    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    return args


def read_config(path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if not config.read(path, encoding="utf-8"):
        raise FileNotFoundError(f"database config file was not found: {path}")
    return config


def setting(
    config: configparser.ConfigParser,
    env_name: str,
    section: str,
    key: str,
    default: str = "",
) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    if config.has_option(section, key):
        return config.get(section, key).strip()
    return default


def connect_mssql(config: configparser.ConfigParser):
    driver = setting(config, "MSSQL_DRIVER", "mssql", "driver", "SQL Server")
    parts = (
        f"DRIVER={{{driver}}}",
        f"SERVER={setting(config, 'MSSQL_SERVER', 'mssql', 'server')}",
        f"DATABASE={setting(config, 'MSSQL_DATABASE', 'mssql', 'database')}",
        f"UID={setting(config, 'MSSQL_USER', 'mssql', 'user')}",
        f"PWD={setting(config, 'MSSQL_PASSWORD', 'mssql', 'password')}",
        f"Encrypt={setting(config, 'MSSQL_ENCRYPT', 'mssql', 'encrypt', 'yes')}",
        "TrustServerCertificate="
        + setting(
            config,
            "MSSQL_TRUST_SERVER_CERTIFICATE",
            "mssql",
            "trust_server_certificate",
            "yes",
        ),
    )
    return pyodbc.connect(";".join(parts) + ";")


def connect_postgres(config: configparser.ConfigParser):
    return pg8000.dbapi.connect(
        host=setting(config, "PG_HOST", "postgresql", "host"),
        port=int(setting(config, "PG_PORT", "postgresql", "port", "5432")),
        database=setting(config, "PG_DATABASE", "postgresql", "database"),
        user=setting(config, "PG_USER", "postgresql", "user"),
        password=setting(config, "PG_PASSWORD", "postgresql", "password"),
    )


def source_sql() -> str:
    return "SELECT %s FROM %s" % (
        ", ".join(f"[{column}]" for column in COLUMNS),
        SOURCE_TABLE,
    )


def upsert_sql(row_count: int) -> str:
    if row_count <= 0:
        raise ValueError("row_count must be positive")

    placeholders = "(" + ", ".join(["%s"] * len(COLUMNS)) + ")"
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in COLUMNS
        if column not in KEY_COLUMNS
    )
    return (
        f"INSERT INTO {TARGET_QUALIFIED_TABLE} ({', '.join(COLUMNS)}) "
        f"VALUES {', '.join([placeholders] * row_count)} "
        f"ON CONFLICT ({', '.join(KEY_COLUMNS)}) DO UPDATE SET {updates}"
    )


def verify_target_table(connection) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (TARGET_SCHEMA, TARGET_TABLE),
        )
        if cursor.fetchone() is None:
            raise RuntimeError(
                f"Target table {TARGET_QUALIFIED_TABLE} does not exist. "
                "Apply wealth-fund-service Flyway migration V1.51 first."
            )

        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (TARGET_SCHEMA, TARGET_TABLE),
        )
        target_columns = {row[0] for row in cursor.fetchall()}
        missing = [column for column in COLUMNS if column not in target_columns]
        if missing:
            raise RuntimeError(
                f"Target table {TARGET_QUALIFIED_TABLE} is missing columns: "
                + ", ".join(missing)
            )
    finally:
        cursor.close()


def count_source_rows(connection) -> int:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT COUNT_BIG(1) FROM {SOURCE_TABLE}")
        return int(cursor.fetchone()[0])
    finally:
        cursor.close()


def transfer(source_connection, target_connection, batch_size: int) -> int:
    source_cursor = source_connection.cursor()
    target_cursor = target_connection.cursor()
    total = 0
    try:
        source_cursor.execute(source_sql())
        while True:
            rows = source_cursor.fetchmany(batch_size)
            if not rows:
                break
            target_cursor.execute(
                upsert_sql(len(rows)),
                [value for row in rows for value in row],
            )
            target_connection.commit()
            total += len(rows)
            print(f"  {TARGET_QUALIFIED_TABLE}: {total:,} rows", flush=True)
    except Exception:
        target_connection.rollback()
        raise
    finally:
        target_cursor.close()
        source_cursor.close()
    return total


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    config = read_config(args.config)
    source_connection = connect_mssql(config)
    target_connection = None
    try:
        if args.count_only:
            print(f"{SOURCE_TABLE}: {count_source_rows(source_connection):,} rows")
            return

        target_connection = connect_postgres(config)
        verify_target_table(target_connection)
        print(f"Migrating {SOURCE_TABLE} -> {TARGET_QUALIFIED_TABLE}")
        migrated = transfer(source_connection, target_connection, args.batch_size)
        print(f"Completed {TARGET_QUALIFIED_TABLE}: {migrated:,} source rows processed")
    finally:
        if target_connection is not None:
            target_connection.close()
        source_connection.close()


if __name__ == "__main__":
    main()
