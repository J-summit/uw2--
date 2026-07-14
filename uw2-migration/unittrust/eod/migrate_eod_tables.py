"""Stream UnitTrust EOD snapshots from SQL Server to PostgreSQL.

The default lower bound is 2025-01-01. Each committed batch can be safely
replayed because the target write uses the legacy composite primary key.
"""

from __future__ import annotations

import argparse
import configparser
import datetime as dt
import os
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import pg8000.dbapi
import pyodbc


DEFAULT_FROM_DATE = dt.date(2025, 1, 1)
DEFAULT_BATCH_SIZE = 1000
DEFAULT_CONFIG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "db.ini")
)
LEGACY_COLUMN_NAMES = {
    "bfe_code": "BFECode",
    "bfe_sub_code": "BFESubCode",
}


@dataclass(frozen=True)
class TableSpec:
    source_table: str
    target_table: str
    date_column: str
    columns: Tuple[str, ...]
    key_columns: Tuple[str, ...]


HOLDING_EOD = TableSpec(
    source_table="dbo.TrnClientHoldingEOD",
    target_table="eod_service.trn_client_holding_eod",
    date_column="holding_date",
    columns=(
        "holding_no", "holding_date", "client_code", "branch", "bfe_code",
        "bfe_sub_code", "fund_id", "dividend_instruction", "payment_mode_code",
        "portfolio_code", "fund_sub_acc", "unit", "entitled_unit", "average_nav",
        "m_average_nav", "total_inv_unit", "total_inv_amount", "m_total_inv_amount",
        "created_by", "created_at", "created_ip", "updated_by", "updated_at", "updated_ip",
    ),
    key_columns=("holding_no", "holding_date"),
)

TRUST_EOD = TableSpec(
    source_table="dbo.TrnTrustEOD",
    target_table="eod_service.trn_trust_eod",
    date_column="trust_date",
    columns=(
        "trust_eod_no", "trust_date", "trust_no", "client_code", "branch", "bfe_code",
        "bfe_sub_code", "gross_amount", "os_gross_amount", "nett_amount", "os_nett_amount",
        "m_gross_amount", "m_os_gross_amount", "m_nett_amount", "m_os_nett_amount",
        "currency", "created_by", "created_at", "created_ip", "updated_by", "updated_at",
        "updated_ip",
    ),
    key_columns=("trust_eod_no", "trust_date"),
)


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate UnitTrust EOD snapshot tables")
    parser.add_argument("--from-date", type=parse_date, default=DEFAULT_FROM_DATE)
    parser.add_argument("--to-date", type=parse_date, default=None,
                        help="exclusive upper bound, YYYY-MM-DD")
    parser.add_argument("--table", choices=("all", "holding", "trust"), default="all")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.to_date is not None and args.to_date <= args.from_date:
        parser.error("--to-date must be later than --from-date")
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
            "Encrypt=%s" % _setting(config, "MSSQL_ENCRYPT", "mssql", "encrypt", "yes"),
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


def selected_tables(name: str) -> Iterable[TableSpec]:
    if name == "holding":
        return (HOLDING_EOD,)
    if name == "trust":
        return (TRUST_EOD,)
    return (HOLDING_EOD, TRUST_EOD)


def _source_sql(table: TableSpec, to_date: Optional[dt.date]) -> str:
    columns = ", ".join(
        "[%s] AS [%s]" % (LEGACY_COLUMN_NAMES[column], column)
        if column in LEGACY_COLUMN_NAMES else "[%s]" % column
        for column in table.columns
    )
    where = "[%s] >= ?" % table.date_column
    if to_date is not None:
        where += " AND [%s] < ?" % table.date_column
    return "SELECT %s FROM %s WHERE %s" % (
        columns,
        table.source_table,
        where,
    )


def _upsert_sql(table: TableSpec, row_count: int) -> str:
    one_row = "(" + ", ".join(["%s"] * len(table.columns)) + ")"
    values = ", ".join([one_row] * row_count)
    updates = ", ".join(
        "%s = EXCLUDED.%s" % (column, column)
        for column in table.columns
        if column not in table.key_columns
    )
    return (
        "INSERT INTO %s (%s) VALUES %s "
        "ON CONFLICT (%s) DO UPDATE SET %s"
    ) % (
        table.target_table,
        ", ".join(table.columns),
        values,
        ", ".join(table.key_columns),
        updates,
    )


def _mssql_datetime(value: dt.date) -> dt.datetime:
    return dt.datetime.combine(value, dt.time.min)


def transfer_table(source_connection, target_connection, table: TableSpec,
                   from_date: dt.date, to_date: Optional[dt.date], batch_size: int) -> int:
    source_cursor = source_connection.cursor()
    target_cursor = target_connection.cursor()
    params = [_mssql_datetime(from_date)]
    if to_date is not None:
        params.append(_mssql_datetime(to_date))
    source_cursor.execute(_source_sql(table, to_date), params)

    total = 0
    try:
        while True:
            rows = source_cursor.fetchmany(batch_size)
            if not rows:
                break
            target_cursor.execute(
                _upsert_sql(table, len(rows)),
                [value for row in rows for value in row],
            )
            target_connection.commit()
            total += len(rows)
            print(f"  {table.target_table}: {total:,} rows", flush=True)
    except Exception:
        target_connection.rollback()
        raise
    finally:
        source_cursor.close()
        target_cursor.close()
    return total


def count_source_rows(source_connection, table: TableSpec,
                      from_date: dt.date, to_date: Optional[dt.date]) -> int:
    cursor = source_connection.cursor()
    where = "[%s] >= ?" % table.date_column
    params = [_mssql_datetime(from_date)]
    if to_date is not None:
        where += " AND [%s] < ?" % table.date_column
        params.append(_mssql_datetime(to_date))
    cursor.execute("SELECT COUNT_BIG(1) FROM %s WHERE %s" % (table.source_table, where), params)
    count = int(cursor.fetchone()[0])
    cursor.close()
    return count


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    config = _read_config(args.config)
    tables = tuple(selected_tables(args.table))
    source_connection = connect_mssql(config)
    target_connection = None
    try:
        if args.count_only:
            for table in tables:
                count = count_source_rows(source_connection, table, args.from_date, args.to_date)
                print(f"{table.source_table}: {count:,} rows")
            return

        target_connection = connect_postgres(config)
        for table in tables:
            print("Migrating %s -> %s" % (table.source_table, table.target_table))
            total = transfer_table(
                source_connection,
                target_connection,
                table,
                args.from_date,
                args.to_date,
                args.batch_size,
            )
            print(f"Completed {table.target_table}: {total:,} rows")
    finally:
        if target_connection is not None:
            target_connection.close()
        source_connection.close()


if __name__ == "__main__":
    main()
