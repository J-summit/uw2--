"""Directly migrate V1 MstEmailControl rows into V2 msg_email_control.

The script follows the existing uw2-migration/unittrust convention but keeps the
source read and target write in one process.  It is deliberately dry-run by
default.  Use --apply only after the source validation report is clean.

Dependencies:
    pip install -r requirements.txt

Usage:
    python migrate_mst_email_control.py --dry-run
    python migrate_mst_email_control.py --apply
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import pg8000
import pyodbc


# Keep the deployment-specific connection values in this block, matching the
# existing migration scripts in this project.  Do not copy production data or
# credentials into source control when this file is distributed.
SOURCE_DB_CONFIG = {
    "server": "10.1.6.177",
    "database": "UnitTrust",
    "username": "sa",
    "password": "Tongyu@123456",
    "driver": "SQL Server",
    "encrypt": "no",
    "trust_server_certificate": "yes",
}

TARGET_PG_CONFIG = {
    "host": "10.1.6.193",
    "port": 15432,
    "database": "wm",
    "user": "wealth",
    "password": "wealth@123",
}

TARGET_SCHEMA = "common_service"
TARGET_TABLE = "msg_email_control"
BATCH_SIZE = 500

SOURCE_COLUMNS: Tuple[str, ...] = (
    "account",
    "account_email",
    "account_type_FM",
    "account_type_UT",
    "statement",
    "structured_prod",
    "wrap_fee",
    "contract_ut",
    "contract_bond",
    "deposit_withdraw",
    "dividend_ut",
    "unitsplit_ut",
    "coupon_bond",
    "advisor",
    "advisor_email",
    "advisor_statement",
    "advisor_structured_prod",
    "advisor_wrap_fee",
    "advisor_contract_ut",
    "advisor_contract_bond",
    "advisor_deposit_withdraw",
    "advisor_dividend_ut",
    "advisor_unitsplit_ut",
    "advisor_coupon_bond",
    "status",
    "attactment_status",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
)

TARGET_COLUMNS: Tuple[str, ...] = (
    "account",
    "account_email",
    "account_type_fm",
    "account_type_ut",
    "statement",
    "structured_prod",
    "wrap_fee",
    "contract_ut",
    "contract_bond",
    "deposit_withdraw",
    "dividend_ut",
    "unitsplit_ut",
    "coupon_bond",
    "advisor",
    "advisor_email",
    "advisor_statement",
    "advisor_structured_prod",
    "advisor_wrap_fee",
    "advisor_contract_ut",
    "advisor_contract_bond",
    "advisor_deposit_withdraw",
    "advisor_dividend_ut",
    "advisor_unitsplit_ut",
    "advisor_coupon_bond",
    "status",
    "attachment_status",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
)

FLAG_COLUMNS = tuple(column for column in TARGET_COLUMNS if column not in {
    "account",
    "account_email",
    "advisor",
    "advisor_email",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
})

SOURCE_TO_TARGET = dict(zip(SOURCE_COLUMNS, TARGET_COLUMNS))


def get_source_connection() -> pyodbc.Connection:
    config = SOURCE_DB_CONFIG
    conn_str = (
        f"DRIVER={{{config['driver']}}};"
        f"SERVER={config['server']};"
        f"DATABASE={config['database']};"
        f"UID={config['username']};"
        f"PWD={config['password']};"
        f"Encrypt={config['encrypt']};"
        f"TrustServerCertificate={config['trust_server_certificate']};"
    )
    return pyodbc.connect(conn_str, timeout=30)


def get_target_connection() -> pg8000.dbapi.Connection:
    config = TARGET_PG_CONFIG
    return pg8000.connect(
        host=config["host"],
        port=config["port"],
        database=config["database"],
        user=config["user"],
        password=config["password"],
        timeout=30,
    )


def fetch_source_rows(conn: pyodbc.Connection) -> List[Dict[str, Any]]:
    selected = ", ".join(f"[{column}]" for column in SOURCE_COLUMNS)
    sql = f"SELECT {selected} FROM [dbo].[MstEmailControl] ORDER BY [account], [advisor]"
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        rows = []
        for values in cursor.fetchall():
            rows.append(dict(zip(SOURCE_COLUMNS, values)))
        return rows
    finally:
        cursor.close()


def _flag_value(value: Any, column: str) -> Any:
    if value is None:
        if column == "status":
            raise ValueError("status cannot be NULL")
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Decimal):
        value = int(value)
    if isinstance(value, int):
        if value in (0, 1):
            return value
        raise ValueError(f"{column} must be 0 or 1, got {value!r}")
    text = str(value).strip().lower()
    if column == "status" and text in {"inactive", "disabled", "0"}:
        return 0
    if column == "status" and text in {"active", "enabled", "auto", "1"}:
        return 1
    if text in {"0", "1"}:
        return int(text)
    raise ValueError(f"{column} must be 0 or 1, got {value!r}")


def transform_row(source: Mapping[str, Any]) -> Dict[str, Any]:
    target: Dict[str, Any] = {}
    for source_column, target_column in SOURCE_TO_TARGET.items():
        value = source.get(source_column)
        if target_column in FLAG_COLUMNS:
            value = _flag_value(value, target_column)
        target[target_column] = value
    return target


def validate_rows(source_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    errors: List[str] = []
    exact_keys: Dict[Tuple[Any, Any], int] = defaultdict(int)
    normalized_keys: Dict[Tuple[str, Any], set] = defaultdict(set)
    transformed: List[Dict[str, Any]] = []

    for index, source_row in enumerate(source_rows, start=1):
        account = source_row.get("account")
        advisor = source_row.get("advisor")
        account_text = "" if account is None else str(account)
        advisor_text = "" if advisor is None else str(advisor)
        if not account_text.strip() or not advisor_text.strip():
            errors.append(f"row {index}: account/advisor cannot be blank")
        exact_keys[(account, advisor)] += 1
        normalized_keys[(account_text.strip(), advisor)].add(account_text)
        try:
            transformed.append(transform_row(source_row))
        except ValueError as exc:
            errors.append(f"row {index}: {exc}")

    for key, count in exact_keys.items():
        if count > 1:
            errors.append(f"duplicate exact key account={key[0]!r}, advisor={key[1]!r}: {count}")
    for (normalized_account, advisor), variants in normalized_keys.items():
        if len(variants) > 1:
            errors.append(
                f"trimmed account collision account={normalized_account!r}, "
                f"advisor={advisor!r}, variants={sorted(variants)!r}"
            )

    if errors:
        preview = "\n".join(f"  - {error}" for error in errors[:20])
        more = f"\n  ... and {len(errors) - 20} more" if len(errors) > 20 else ""
        raise ValueError(f"source validation failed ({len(errors)} issue(s)):\n{preview}{more}")
    return transformed


def ensure_target_table(cur: Any) -> None:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        [TARGET_SCHEMA, TARGET_TABLE],
    )
    if cur.fetchone() is None:
        raise RuntimeError(
            f"target table {TARGET_SCHEMA}.{TARGET_TABLE} does not exist; "
            "run the V2 schema migration first"
        )


def upsert_rows(cur: Any, rows: Sequence[Mapping[str, Any]]) -> Tuple[int, int]:
    columns = ", ".join(f'"{column}"' for column in TARGET_COLUMNS)
    placeholders = ", ".join(["%s"] * len(TARGET_COLUMNS))
    update_columns = [column for column in TARGET_COLUMNS if column not in {"account", "advisor", "created_at", "created_by", "created_ip"}]
    updates = ", ".join(f'"{column}" = EXCLUDED."{column}"' for column in update_columns)
    sql = (
        f'INSERT INTO "{TARGET_SCHEMA}"."{TARGET_TABLE}" ({columns}) '
        f"VALUES ({placeholders}) "
        f'ON CONFLICT ("account", "advisor") DO UPDATE SET {updates} '
        "RETURNING (xmax = 0) AS inserted"
    )
    inserted = 0
    updated = 0
    for row in rows:
        cur.execute(sql, [row[column] for column in TARGET_COLUMNS])
        result = cur.fetchone()
        if result and result[0]:
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def reconcile_flags(cur: Any, rows: Sequence[Mapping[str, Any]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    found = 0
    mismatches = 0
    for offset in range(0, len(rows), BATCH_SIZE):
        batch = rows[offset : offset + BATCH_SIZE]
        predicates = ", ".join(["(%s, %s)"] * len(batch))
        params: List[Any] = []
        for row in batch:
            params.extend([row["account"], row["advisor"]])
        cur.execute(
            f'SELECT "account", "advisor", "status", "attachment_status" '
            f'FROM "{TARGET_SCHEMA}"."{TARGET_TABLE}" '
            f"WHERE (\"account\", \"advisor\") IN ({predicates})",
            params,
        )
        actual = {(r[0], r[1]): (r[2], r[3]) for r in cur.fetchall()}
        for row in batch:
            key = (row["account"], row["advisor"])
            if key not in actual:
                continue
            found += 1
            if actual[key] != (row["status"], row["attachment_status"]):
                mismatches += 1
    return found, mismatches


def run(apply: bool) -> None:
    source_conn = None
    target_conn = None
    try:
        print("Reading UnitTrust.dbo.MstEmailControl ...")
        source_conn = get_source_connection()
        source_rows = fetch_source_rows(source_conn)
        print(f"Source rows: {len(source_rows)}")
        rows = validate_rows(source_rows)
        print(f"Validation passed: {len(rows)} rows")
        if not apply:
            print("Dry-run complete; no PostgreSQL write was performed.")
            return

        print(f"Writing {TARGET_SCHEMA}.{TARGET_TABLE} ...")
        target_conn = get_target_connection()
        with target_conn.cursor() as cur:
            ensure_target_table(cur)
            inserted, updated = upsert_rows(cur, rows)
            found, mismatches = reconcile_flags(cur, rows)
            if found != len(rows) or mismatches:
                raise RuntimeError(
                    f"reconciliation failed: source={len(rows)}, target_keys={found}, "
                    f"status_or_attachment_mismatches={mismatches}"
                )
        target_conn.commit()
        print(f"Migration complete: inserted={inserted}, updated={updated}, reconciled={found}")
    except Exception:
        if target_conn is not None:
            target_conn.rollback()
        raise
    finally:
        if source_conn is not None:
            source_conn.close()
        if target_conn is not None:
            target_conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate V1 MstEmailControl to V2 msg_email_control")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="read and validate only (default)")
    mode.add_argument("--apply", action="store_true", help="upsert into PostgreSQL")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run(apply=args.apply)
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
