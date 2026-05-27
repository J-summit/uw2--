"""
Migrate legacy IFA and Branch master data from UnitTrust MSSQL to V2 PostgreSQL.

Default source:
  MSSQL 10.1.6.177:1433 / UnitTrust / sa / Tongyu@123456

Default target:
  PostgreSQL localhost:15432 / uw / wealth / wealth123 / auth_service
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pyodbc
except ImportError:  # pragma: no cover - exercised only when export is used
    pyodbc = None

try:
    import pg8000
except ImportError:  # pragma: no cover - exercised only when import is used
    pg8000 = None


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_ROOT = os.path.join(SCRIPT_DIR, "json_export")


MSSQL_DEFAULTS = {
    "server": "10.1.6.177,1433",
    "database": "UnitTrust",
    "username": "sa",
    "password": "Tongyu@123456",
    "driver": "SQL Server",
    "encrypt": "no",
    "trust_server_certificate": "yes",
}


PG_DEFAULTS = {
    "host": "localhost",
    "port": 15432,
    "database": "uw",
    "user": "wealth",
    "password": "wealth123",
    "schema": "auth_service",
}


INTERACTIVE_COMMANDS = {
    "1": "migrate",
    "2": "export",
    "3": "import",
    "4": "verify",
    "migrate": "migrate",
    "export": "export",
    "import": "import",
    "verify": "verify",
}


IFA_SOURCE_COLUMNS = [
    "ifa_code",
    "ifa_name",
    "company_no",
    "addr1",
    "addr2",
    "addr3",
    "addr4",
    "addr5",
    "postcode",
    "state",
    "country",
    "tel",
    "email",
    "logo_path",
    "website",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
    "is_backoffice",
]


BRANCH_SOURCE_COLUMNS = [
    "Code",
    "ifa_code",
    "Name",
    "OldName",
    "Addr1",
    "Addr2",
    "Addr3",
    "Addr4",
    "Addr5",
    "PostCode",
    "Territory",
    "Country",
    "Tel1",
    "Tel2",
    "Fax",
    "Email",
    "Virtual",
    "VirCode",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
]


IFA_ORG_COLUMNS = [
    "name",
    "code",
    "type",
    "parent_id",
    "company_no",
    "addr1",
    "addr2",
    "addr3",
    "addr4",
    "addr5",
    "postcode",
    "state",
    "country",
    "tel",
    "email",
    "logo_path",
    "website",
    "is_backoffice",
    "source",
    "source_id",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
]


BRANCH_ORG_COLUMNS = [
    "name",
    "code",
    "type",
    "parent_id",
    "root_id",
    "path",
    "source",
    "source_id",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
]


BASE_BRANCH_COLUMNS = [
    "code",
    "ifa_code",
    "organization_id",
    "name",
    "old_name",
    "addr1",
    "addr2",
    "addr3",
    "addr4",
    "addr5",
    "post_code",
    "territory",
    "country",
    "tel1",
    "tel2",
    "fax",
    "email",
    "virtual",
    "vir_code",
    "created_by",
    "created_at",
    "created_ip",
    "updated_by",
    "updated_at",
    "updated_ip",
]


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="milliseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def normalize_row(columns: Sequence[str], row: Sequence[Any]) -> Dict[str, Any]:
    return {column: serialize_value(value) for column, value in zip(columns, row)}


def as_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def audit_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    created_by = clean_text(row.get("created_by")) or "migration"
    created_at = row.get("created_at") or datetime.now().isoformat(timespec="milliseconds")
    created_ip = clean_text(row.get("created_ip")) or "migration"
    return {
        "created_by": created_by,
        "created_at": created_at,
        "created_ip": created_ip,
        "updated_by": clean_text(row.get("updated_by")) or created_by,
        "updated_at": row.get("updated_at") or created_at,
        "updated_ip": clean_text(row.get("updated_ip")) or created_ip,
    }


def map_ifa(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    code = clean_text(row.get("ifa_code"))
    name = clean_text(row.get("ifa_name"))
    if not code or not name:
        return None
    mapped = {
        "code": code,
        "name": name,
        "type": "IFA",
        "company_no": clean_text(row.get("company_no")),
        "addr1": clean_text(row.get("addr1")),
        "addr2": clean_text(row.get("addr2")),
        "addr3": clean_text(row.get("addr3")),
        "addr4": clean_text(row.get("addr4")),
        "addr5": clean_text(row.get("addr5")),
        "postcode": clean_text(row.get("postcode")),
        "state": clean_text(row.get("state")),
        "country": clean_text(row.get("country")),
        "tel": clean_text(row.get("tel")),
        "email": clean_text(row.get("email")),
        "logo_path": clean_text(row.get("logo_path")),
        "website": clean_text(row.get("website")),
        "is_backoffice": as_bool(row.get("is_backoffice")),
        "source": "LEGACY_MSTIFA",
        "source_id": f"MstIFA:{code}",
    }
    mapped.update(audit_fields(row))
    return mapped


def map_branch_organization(row: Dict[str, Any], ifa_codes: Iterable[str]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    ifa_code = clean_text(row.get("ifa_code"))
    code = clean_text(row.get("Code"))
    name = clean_text(row.get("Name"))
    if not code or not name:
        return None, {"reason": "required_field_missing", "branch_code": code, "ifa_code": ifa_code}
    if not ifa_code or ifa_code not in set(ifa_codes):
        return None, {"reason": "ifa_not_found", "branch_code": code, "ifa_code": ifa_code}
    mapped = {
        "code": code,
        "name": name,
        "type": "BRANCH",
        "parent_code": ifa_code,
        "source": "LEGACY_MSTBRANCH",
        "source_id": f"MstBranch:{code}",
    }
    mapped.update(audit_fields(row))
    return mapped, None


def map_base_branch(row: Dict[str, Any]) -> Dict[str, Any]:
    mapped = {
        "code": clean_text(row.get("Code")),
        "ifa_code": clean_text(row.get("ifa_code")),
        "name": clean_text(row.get("Name")),
        "old_name": clean_text(row.get("OldName")),
        "addr1": clean_text(row.get("Addr1")),
        "addr2": clean_text(row.get("Addr2")),
        "addr3": clean_text(row.get("Addr3")),
        "addr4": clean_text(row.get("Addr4")),
        "addr5": clean_text(row.get("Addr5")),
        "post_code": clean_text(row.get("PostCode")),
        "territory": clean_text(row.get("Territory")),
        "country": clean_text(row.get("Country")),
        "tel1": clean_text(row.get("Tel1")),
        "tel2": clean_text(row.get("Tel2")),
        "fax": clean_text(row.get("Fax")),
        "email": clean_text(row.get("Email")),
        "virtual": as_bool(row.get("Virtual")),
        "vir_code": clean_text(row.get("VirCode")),
    }
    mapped.update(audit_fields(row))
    return mapped


def build_export_payload(
    ifas: Sequence[Dict[str, Any]],
    branches: Sequence[Dict[str, Any]],
    batch_id: str,
) -> Dict[str, Any]:
    ifa_organizations: List[Dict[str, Any]] = []
    branch_organizations: List[Dict[str, Any]] = []
    base_branches: List[Dict[str, Any]] = []
    rejects: List[Dict[str, Any]] = []

    for row in ifas:
        mapped = map_ifa(row)
        if mapped is None:
            rejects.append(
                {
                    "reason": "ifa_required_field_missing",
                    "ifa_code": clean_text(row.get("ifa_code")),
                    "ifa_name": clean_text(row.get("ifa_name")),
                }
            )
            continue
        ifa_organizations.append(mapped)

    ifa_codes = {row["code"] for row in ifa_organizations}
    for row in branches:
        branch_org, reject = map_branch_organization(row, ifa_codes)
        if reject is not None:
            rejects.append(reject)
            continue
        branch_organizations.append(branch_org)
        base_branches.append(map_base_branch(row))

    manifest = {
        "batch_id": batch_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_ifas": len(ifas),
        "source_branches": len(branches),
        "valid_ifas": len(ifa_organizations),
        "valid_branches": len(base_branches),
        "rejected_ifas": sum(1 for item in rejects if "branch_code" not in item),
        "rejected_branches": sum(1 for item in rejects if "branch_code" in item),
    }
    return {
        "manifest": manifest,
        "ifa_organizations": ifa_organizations,
        "branch_organizations": branch_organizations,
        "base_branches": base_branches,
        "rejects": rejects,
    }


def mssql_connection(args: argparse.Namespace):
    if pyodbc is None:
        raise RuntimeError("pyodbc is required. Install with: pip install pyodbc")
    conn_str = (
        f"DRIVER={{{args.mssql_driver}}};"
        f"SERVER={args.mssql_server};"
        f"DATABASE={args.mssql_database};"
        f"UID={args.mssql_user};"
        f"PWD={args.mssql_password};"
        f"Encrypt={args.mssql_encrypt};"
        f"TrustServerCertificate={args.mssql_trust_server_certificate};"
    )
    return pyodbc.connect(conn_str)


def pg_connection(args: argparse.Namespace):
    if pg8000 is None:
        raise RuntimeError("pg8000 is required. Install with: pip install pg8000")
    return pg8000.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )


def fetch_legacy_ifas(conn) -> List[Dict[str, Any]]:
    sql = """
    SELECT
        ifa_code,
        ifa_name,
        company_no,
        addr1,
        addr2,
        addr3,
        addr4,
        addr5,
        postcode,
        state,
        country,
        tel,
        email,
        logo_path,
        website,
        created_by,
        created_at,
        created_ip,
        updated_by,
        updated_at,
        updated_ip,
        is_backoffice
    FROM dbo.MstIFA
    ORDER BY ifa_code
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = [normalize_row(IFA_SOURCE_COLUMNS, row) for row in cursor.fetchall()]
    cursor.close()
    return rows


def fetch_legacy_branches(conn) -> List[Dict[str, Any]]:
    sql = """
    SELECT
        Code,
        ifa_code,
        Name,
        OldName,
        Addr1,
        Addr2,
        Addr3,
        Addr4,
        Addr5,
        PostCode,
        Territory,
        Country,
        Tel1,
        Tel2,
        Fax,
        Email,
        Virtual,
        VirCode,
        created_by,
        created_at,
        created_ip,
        updated_by,
        updated_at,
        updated_ip
    FROM dbo.MstBranch
    ORDER BY Code
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = [normalize_row(BRANCH_SOURCE_COLUMNS, row) for row in cursor.fetchall()]
    cursor.close()
    return rows


def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def export_command(args: argparse.Namespace) -> str:
    batch_id = args.batch_id or datetime.now().strftime("ifa_%Y%m%d_%H%M%S")
    output_dir = args.output_dir or os.path.join(DEFAULT_OUTPUT_ROOT, batch_id)
    print(f"Connecting MSSQL {args.mssql_server}/{args.mssql_database} ...")
    conn = mssql_connection(args)
    try:
        print("Reading MstIFA ...")
        ifas = fetch_legacy_ifas(conn)
        print(f"  ifas: {len(ifas)}")
        print("Reading MstBranch ...")
        branches = fetch_legacy_branches(conn)
        print(f"  branches: {len(branches)}")
    finally:
        conn.close()

    payload = build_export_payload(ifas, branches, batch_id)
    save_json(os.path.join(output_dir, "manifest.json"), payload["manifest"])
    save_json(os.path.join(output_dir, "base_organization_ifa.json"), payload["ifa_organizations"])
    save_json(os.path.join(output_dir, "base_organization_branch.json"), payload["branch_organizations"])
    save_json(os.path.join(output_dir, "base_branch.json"), payload["base_branches"])
    save_json(os.path.join(output_dir, "rejects.json"), payload["rejects"])
    print(f"Exported batch to {output_dir}")
    print(json.dumps(payload["manifest"], ensure_ascii=False, indent=2))
    return output_dir


def quote_ident(identifier: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return f'"{identifier}"'


def table_name(schema: str, table: str) -> str:
    return f"{quote_ident(schema)}.{quote_ident(table)}"


def select_one(cur, sql: str, values: Sequence[Any]) -> Optional[Tuple[Any, ...]]:
    cur.execute(sql, values)
    return cur.fetchone()


def upsert_ifa_organizations(cur, schema: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    org_table = table_name(schema, "base_organization")
    ids: Dict[str, int] = {}
    for row in rows:
        existing = select_one(
            cur,
            f"SELECT id FROM {org_table} WHERE type = %s AND code = %s LIMIT 1",
            ("IFA", row["code"]),
        )
        values = [
            row["name"],
            row["code"],
            row["type"],
            None,
            row.get("company_no"),
            row.get("addr1"),
            row.get("addr2"),
            row.get("addr3"),
            row.get("addr4"),
            row.get("addr5"),
            row.get("postcode"),
            row.get("state"),
            row.get("country"),
            row.get("tel"),
            row.get("email"),
            row.get("logo_path"),
            row.get("website"),
            row.get("is_backoffice"),
            row.get("source"),
            row.get("source_id"),
            row.get("created_by"),
            row.get("created_at"),
            row.get("created_ip"),
            row.get("updated_by"),
            row.get("updated_at"),
            row.get("updated_ip"),
        ]
        if existing:
            assignments = ", ".join(f"{quote_ident(column)} = %s" for column in IFA_ORG_COLUMNS)
            cur.execute(f"UPDATE {org_table} SET {assignments} WHERE id = %s", values + [existing[0]])
            org_id = existing[0]
        else:
            columns = ", ".join(quote_ident(column) for column in IFA_ORG_COLUMNS)
            placeholders = ", ".join(["%s"] * len(IFA_ORG_COLUMNS))
            cur.execute(
                f"INSERT INTO {org_table} ({columns}) VALUES ({placeholders}) RETURNING id",
                values,
            )
            org_id = cur.fetchone()[0]
        cur.execute(
            f"""
            UPDATE {org_table}
               SET root_id = id,
                   path = '/' || id::text
             WHERE id = %s
            """,
            (org_id,),
        )
        ids[row["code"]] = org_id
    return ids


def fetch_org_lineage(cur, schema: str, org_id: int) -> Tuple[int, str]:
    org_table = table_name(schema, "base_organization")
    cur.execute(f"SELECT COALESCE(root_id, id), COALESCE(NULLIF(path, ''), '/' || id::text) FROM {org_table} WHERE id = %s", (org_id,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Organization id not found: {org_id}")
    return row[0], row[1]


def upsert_branch_organizations(
    cur,
    schema: str,
    rows: Sequence[Dict[str, Any]],
    ifa_ids: Dict[str, int],
) -> Dict[str, int]:
    org_table = table_name(schema, "base_organization")
    ids: Dict[str, int] = {}
    for row in rows:
        parent_code = row["parent_code"]
        parent_id = ifa_ids.get(parent_code)
        if parent_id is None:
            raise RuntimeError(f"Missing imported IFA organization for {parent_code}")
        parent_root_id, parent_path = fetch_org_lineage(cur, schema, parent_id)
        existing = select_one(
            cur,
            f"SELECT id FROM {org_table} WHERE type = %s AND code = %s AND parent_id = %s LIMIT 1",
            ("BRANCH", row["code"], parent_id),
        )
        values = [
            row["name"],
            row["code"],
            row["type"],
            parent_id,
            parent_root_id,
            None,
            row.get("source"),
            row.get("source_id"),
            row.get("created_by"),
            row.get("created_at"),
            row.get("created_ip"),
            row.get("updated_by"),
            row.get("updated_at"),
            row.get("updated_ip"),
        ]
        if existing:
            org_id = existing[0]
            values[5] = f"{parent_path}/{org_id}"
            assignments = ", ".join(f"{quote_ident(column)} = %s" for column in BRANCH_ORG_COLUMNS)
            cur.execute(f"UPDATE {org_table} SET {assignments} WHERE id = %s", values + [org_id])
        else:
            columns = ", ".join(quote_ident(column) for column in BRANCH_ORG_COLUMNS)
            placeholders = ", ".join(["%s"] * len(BRANCH_ORG_COLUMNS))
            values[5] = ""
            cur.execute(
                f"INSERT INTO {org_table} ({columns}) VALUES ({placeholders}) RETURNING id",
                values,
            )
            org_id = cur.fetchone()[0]
            cur.execute(
                f"UPDATE {org_table} SET path = %s WHERE id = %s",
                (f"{parent_path}/{org_id}", org_id),
            )
        ids[row["code"]] = org_id
    return ids


def upsert_base_branches(
    cur,
    schema: str,
    rows: Sequence[Dict[str, Any]],
    branch_org_ids: Dict[str, int],
) -> int:
    branch_table = table_name(schema, "base_branch")
    columns = ", ".join(quote_ident(column) for column in BASE_BRANCH_COLUMNS)
    placeholders = ", ".join(["%s"] * len(BASE_BRANCH_COLUMNS))
    update_columns = [column for column in BASE_BRANCH_COLUMNS if column != "code"]
    assignments = ", ".join(f"{quote_ident(column)} = EXCLUDED.{quote_ident(column)}" for column in update_columns)
    sql = f"""
    INSERT INTO {branch_table} ({columns})
    VALUES ({placeholders})
    ON CONFLICT (code) DO UPDATE SET {assignments}
    """
    for row in rows:
        organization_id = branch_org_ids.get(row["code"])
        if organization_id is None:
            raise RuntimeError(f"Missing branch organization for {row['code']}")
        values = [row.get(column) for column in BASE_BRANCH_COLUMNS]
        values[BASE_BRANCH_COLUMNS.index("organization_id")] = organization_id
        cur.execute(sql, values)
    return len(rows)


def import_command(args: argparse.Namespace) -> None:
    input_dir = args.input_dir
    if not input_dir:
        raise ValueError("--input-dir is required for import")

    ifa_organizations = load_json(os.path.join(input_dir, "base_organization_ifa.json"))
    branch_organizations = load_json(os.path.join(input_dir, "base_organization_branch.json"))
    base_branches = load_json(os.path.join(input_dir, "base_branch.json"))
    manifest = load_json(os.path.join(input_dir, "manifest.json"))

    print(f"Connecting PostgreSQL {args.pg_host}:{args.pg_port}/{args.pg_database} ...")
    conn = pg_connection(args)
    schema = args.pg_schema
    try:
        cur = conn.cursor()
        print("Upserting IFA organizations ...")
        ifa_ids = upsert_ifa_organizations(cur, schema, ifa_organizations)
        print("Upserting Branch organizations ...")
        branch_org_ids = upsert_branch_organizations(cur, schema, branch_organizations, ifa_ids)
        print("Upserting base_branch ...")
        inserted_branches = upsert_base_branches(cur, schema, base_branches, branch_org_ids)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "batch_id": manifest.get("batch_id"),
                "upserted_ifas": len(ifa_ids),
                "upserted_branch_organizations": len(branch_org_ids),
                "upserted_base_branches": inserted_branches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def placeholders(values: Sequence[Any]) -> str:
    return ", ".join(["%s"] * len(values))


def verify_command(args: argparse.Namespace) -> None:
    expected_ifa_codes: List[str] = []
    expected_branch_codes: List[str] = []
    if args.input_dir:
        ifa_organizations = load_json(os.path.join(args.input_dir, "base_organization_ifa.json"))
        base_branches = load_json(os.path.join(args.input_dir, "base_branch.json"))
        expected_ifa_codes = [row["code"] for row in ifa_organizations]
        expected_branch_codes = [row["code"] for row in base_branches]

    conn = pg_connection(args)
    schema = args.pg_schema
    org_table = table_name(schema, "base_organization")
    branch_table = table_name(schema, "base_branch")
    try:
        cur = conn.cursor()
        checks: Dict[str, Any] = {}
        if expected_ifa_codes:
            cur.execute(
                f"SELECT COUNT(*) FROM {org_table} WHERE type = 'IFA' AND code IN ({placeholders(expected_ifa_codes)})",
                expected_ifa_codes,
            )
            checks["expected_ifas_present"] = cur.fetchone()[0]
            checks["expected_ifas"] = len(expected_ifa_codes)
        if expected_branch_codes:
            cur.execute(
                f"SELECT COUNT(*) FROM {branch_table} WHERE code IN ({placeholders(expected_branch_codes)})",
                expected_branch_codes,
            )
            checks["expected_branches_present"] = cur.fetchone()[0]
            checks["expected_branches"] = len(expected_branch_codes)

        link_filter = ""
        values: List[Any] = []
        if expected_branch_codes:
            link_filter = f"AND b.code IN ({placeholders(expected_branch_codes)})"
            values.extend(expected_branch_codes)
        cur.execute(
            f"""
            SELECT COUNT(*)
              FROM {branch_table} b
              LEFT JOIN {org_table} branch_org
                ON branch_org.id = b.organization_id
               AND branch_org.type = 'BRANCH'
              LEFT JOIN {org_table} ifa_org
                ON ifa_org.id = branch_org.parent_id
               AND ifa_org.type = 'IFA'
               AND ifa_org.code = b.ifa_code
             WHERE (branch_org.id IS NULL OR ifa_org.id IS NULL)
               {link_filter}
            """,
            values,
        )
        checks["branches_without_valid_organization"] = cur.fetchone()[0]
    finally:
        conn.close()

    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if checks.get("expected_ifas_present") != checks.get("expected_ifas", checks.get("expected_ifas_present")):
        raise RuntimeError("Verification failed: not all expected IFA organizations are present")
    if checks.get("expected_branches_present") != checks.get("expected_branches", checks.get("expected_branches_present")):
        raise RuntimeError("Verification failed: not all expected branches are present")
    if checks["branches_without_valid_organization"]:
        raise RuntimeError("Verification failed: branch organization links are incomplete")


def migrate_command(args: argparse.Namespace) -> None:
    output_dir = export_command(args)
    args.input_dir = output_dir
    import_command(args)
    verify_command(args)


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--batch-id")
    parser.add_argument("--output-dir")
    parser.add_argument("--input-dir")
    parser.add_argument("--mssql-server", default=MSSQL_DEFAULTS["server"])
    parser.add_argument("--mssql-database", default=MSSQL_DEFAULTS["database"])
    parser.add_argument("--mssql-user", default=MSSQL_DEFAULTS["username"])
    parser.add_argument("--mssql-password", default=MSSQL_DEFAULTS["password"])
    parser.add_argument("--mssql-driver", default=MSSQL_DEFAULTS["driver"])
    parser.add_argument("--mssql-encrypt", default=MSSQL_DEFAULTS["encrypt"])
    parser.add_argument(
        "--mssql-trust-server-certificate",
        default=MSSQL_DEFAULTS["trust_server_certificate"],
    )
    parser.add_argument("--pg-host", default=PG_DEFAULTS["host"])
    parser.add_argument("--pg-port", type=int, default=PG_DEFAULTS["port"])
    parser.add_argument("--pg-database", default=PG_DEFAULTS["database"])
    parser.add_argument("--pg-user", default=PG_DEFAULTS["user"])
    parser.add_argument("--pg-password", default=PG_DEFAULTS["password"])
    parser.add_argument("--pg-schema", default=PG_DEFAULTS["schema"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate legacy IFA and Branch master data.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "import", "verify", "migrate"):
        sub = subparsers.add_parser(name)
        add_common_args(sub)
    return parser


def prompt_yes_no(message: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{message} {suffix}: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def print_interactive_summary(args: argparse.Namespace) -> None:
    print("")
    print(f"Command: {args.command}")
    if args.command in {"export", "migrate"}:
        print(f"MSSQL: {args.mssql_server}/{args.mssql_database} user={args.mssql_user}")
    if args.command in {"import", "verify", "migrate"}:
        print(
            f"PostgreSQL: {args.pg_host}:{args.pg_port}/{args.pg_database} "
            f"schema={args.pg_schema} user={args.pg_user}"
        )
    if args.output_dir:
        print(f"Output dir: {args.output_dir}")
    if args.input_dir:
        print(f"Input dir: {args.input_dir}")
    print("")


def parse_command_args(command: str, extra_args: Sequence[str]) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args([command] + list(extra_args))


def interactive_main() -> int:
    print("Choose command:")
    print("1) migrate  Export from MSSQL, import to PostgreSQL, then verify")
    print("2) export   Export MSSQL data to JSON only")
    print("3) import   Import JSON export into PostgreSQL")
    print("4) verify   Verify imported data")
    print("q) quit")
    choice = input("Select [1]: ").strip().lower() or "1"
    if choice in {"q", "quit", "exit"}:
        print("Bye.")
        return 0

    command = INTERACTIVE_COMMANDS.get(choice)
    if not command:
        print(f"Unknown choice: {choice}")
        return 2

    extra_args: List[str] = []
    if command in {"export", "migrate"}:
        output_dir = input("Output dir [auto]: ").strip()
        if output_dir:
            extra_args.extend(["--output-dir", output_dir])

    if command in {"import", "verify"}:
        input_dir = input("Input dir: ").strip()
        if not input_dir:
            print("Input dir is required for this command.")
            return 2
        extra_args.extend(["--input-dir", input_dir])

    args = parse_command_args(command, extra_args)
    print_interactive_summary(args)
    if not prompt_yes_no("Continue", default=False):
        print("Cancelled.")
        return 0

    run_command(args)
    return 0


def run_command(args: argparse.Namespace) -> None:
    if args.command == "export":
        export_command(args)
    elif args.command == "import":
        import_command(args)
    elif args.command == "verify":
        verify_command(args)
    elif args.command == "migrate":
        migrate_command(args)
    else:  # pragma: no cover
        raise ValueError(f"Unknown command: {args.command}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return interactive_main()
    parser = build_parser()
    args = parser.parse_args(argv)
    run_command(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
