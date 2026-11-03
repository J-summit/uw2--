#!/usr/bin/env python3
"""补迁 UnitTrust 登录账号及其缺失的 V2 业务依赖。

默认仅执行 SELECT 并打印预检。只有显式传入 --apply 和 --confirm-target
才会在一个 PostgreSQL 事务中补数及修正允许的字段。不会覆盖 V2 现有密码。
"""

from __future__ import annotations

import argparse
import configparser
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "db.ini"
SOURCE_BUSINESS = (
    ("MstClient", "base_client", ("code",)),
    ("MstBFEUser", "base_advisor", ("code", "branch")),
    ("MstClntPrd2", "base_client_prd", ("code", "acct_no")),
    ("MstClntPrd3", "base_client_prd", ("code", "acct_no")),
    ("MstJointAcct", "rel_joint_acct", ("joint_client_code", "client_code")),
)
BUSINESS_TARGETS = ("base_client", "base_advisor", "base_client_prd", "rel_joint_acct")
ALIASES = {"dispatch_1": "dispatch1"}
MIGRATION_SOURCE = "V1_UNITTRUST"
DEFAULT_INITIAL_PASSWORD = "123456a."
RESULT_COLUMNS = {
    "account_service.base_client": ("code", "client_name"),
    "account_service.base_advisor": ("code", "branch", "name"),
    "account_service.base_client_prd": ("code", "acct_no", "client_code", "bfe_code"),
    "account_service.rel_joint_acct": ("joint_client_code", "client_code"),
    "auth_service.sys_user": ("id", "username", "code", "user_type"),
    "auth_service.ref_user_role": ("user_id", "user_code", "role_id", "account_origin"),
}


class MigrationConflict(ValueError):
    """源数据或目标数据存在不能自动解决的身份冲突。"""


def clean_key(value):
    return value.strip() if isinstance(value, str) else value


def lookup_key(value):
    return (clean_key(value) or "").casefold()


def snake_case(name: str) -> str:
    first = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first).lower()


def map_business_row(source_table, row, target_columns, bit_columns):
    """只保留目标列；已存在 V1/V2 命名差异显式转换。"""
    mapped = {}
    for name, value in row.items():
        column = ALIASES.get(snake_case(name), snake_case(name))
        if column not in target_columns:
            continue
        if column in bit_columns and value is not None:
            if isinstance(value, (bytes, bytearray)):
                enabled = int.from_bytes(value, "little") != 0
            elif isinstance(value, str):
                enabled = value.strip().lower() in {"1", "true", "t"}
            else:
                enabled = bool(value)
            value = "1" if enabled else "0"
        if column in {"code", "acct_no", "client_code", "joint_client_code", "branch"}:
            value = clean_key(value)
        mapped[column] = value
    return mapped


def resolve_identity(login_id, client_links, advisor_links, subadvisor_links):
    """返回 (V2 user_type, 稳定业务 code)；遵循 V1 BFE/BFE4/Client 优先级。"""
    advisor_codes = {clean_key(code) for code in advisor_links if code}
    if advisor_codes:
        if len(advisor_codes) != 1:
            raise MigrationConflict("advisor has multiple business codes")
        return "ADVISOR", next(iter(advisor_codes))
    if subadvisor_links:
        raise MigrationConflict("MstBFEUser4 has no confirmed V2 business mapping")
    individuals = {clean_key(code) for code, kind in client_links if kind != "02"}
    joints = {clean_key(code) for code, kind in client_links if kind == "02"}
    if len(individuals) == 1:
        return "CLIENT", next(iter(individuals))
    if len(individuals) > 1 or len(joints) > 1:
        raise MigrationConflict("login ID maps to multiple clients")
    if len(joints) == 1:
        return "CLIENT", next(iter(joints))
    raise MigrationConflict("login ID has no client/advisor business identity")


def user_conflict(username, code, users_by_name, users_by_code):
    existing = users_by_name.get(username)
    if existing and clean_key(existing[1]) != code:
        return "username belongs to another business code"
    code_owner = users_by_code.get(code)
    if code_owner and code_owner[0] != username:
        return "code belongs to another username"
    return None


def load_config(path):
    config = configparser.ConfigParser()
    if not config.read(path, encoding="utf-8"):
        raise FileNotFoundError(f"配置文件不存在: {path}")
    for section, fields in {"mssql": ("database", "user", "password"),
                            "postgresql": ("host", "port", "database", "user", "password")}.items():
        for field in fields:
            if not config.get(section, field, fallback=""):
                raise ValueError(f"配置缺少 [{section}] {field}")
    if config.get("mssql", "host", fallback=""):
        if not config.get("mssql", "port", fallback=""):
            raise ValueError("配置缺少 [mssql] port")
        config.getint("mssql", "port")
    elif not config.get("mssql", "server", fallback=""):
        raise ValueError("配置缺少 [mssql] host/port 或 server")
    return config


def mssql_endpoint(config):
    host = config.get("mssql", "host", fallback="").strip()
    if host:
        return host, config.getint("mssql", "port")
    server = config.get("mssql", "server")
    host, separator, port = server.replace(",", ":").partition(":")
    return host, int(port) if separator else 1433


def connect_source(config):
    import pytds

    host, port = mssql_endpoint(config)
    return pytds.connect(
        server=host, port=port,
        database=config.get("mssql", "database"),
        user=config.get("mssql", "user"), password=config.get("mssql", "password"),
        autocommit=False, login_timeout=15, timeout=90,
    )


def connect_target(config):
    import pg8000.dbapi
    import socket

    # Retry only socket establishment, never a statement/transaction with an uncertain outcome.
    endpoint = (config.get('postgresql', 'host'), config.getint('postgresql', 'port'))
    for attempt in range(3):
        try:
            sock = socket.create_connection(endpoint, timeout=10)
            break
        except (TimeoutError, ConnectionRefusedError):
            if attempt == 2:
                raise
            print(f'PostgreSQL connection unavailable; retry {attempt + 2}/3', flush=True)
    sock.settimeout(60)
    try:
        return pg8000.dbapi.connect(
            host=endpoint[0], port=endpoint[1], sock=sock,
            database=config.get("postgresql", "database"),
            user=config.get("postgresql", "user"), password=config.get("postgresql", "password"), timeout=60,
        )
    except Exception:
        sock.close()
        raise


def query_rows(connection, sql, params=()):
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def source_data(connection):
    business = {table: query_rows(connection, f"SELECT * FROM dbo.[{table}]")
                for table, _, _ in SOURCE_BUSINESS}
    logins = query_rows(connection,
        "SELECT login_id, group_code, expiry_date, login_attemp, force_change_date, "
        "CASE WHEN force_change_date <= CONVERT(date, GETDATE()) THEN "
        "CASE WHEN LEFT(current_password, 7) = '$argon2' THEN 'FORCED_WITH_ARGON2_REVIEW' "
        "ELSE 'FORCED_LEGACY_COMPARE' END ELSE 'PASSWORD_VERIFY' END AS password_branch "
        "FROM dbo.MstLogin")
    groups = {row["group_code"] for row in query_rows(connection,
        "SELECT group_code FROM dbo.MstGroup")}
    links = {}
    for name, table, columns in (
        ("client", "MstClient", "c.code, c.clnt_type"),
        ("advisor", "MstBFEUser", "c.Code"),
        ("subadvisor", "MstBFEUser4", "c.Code"),
    ):
        links[name] = query_rows(connection,
            f"SELECT DISTINCT l.login_id, {columns} FROM dbo.MstLogin l "
            f"JOIN dbo.[{table}] c ON c.login_id = l.login_id")
    user_login = query_rows(connection, "SELECT login_id, code FROM dbo.MstUserLogin")
    return business, logins, groups, links, user_login


def target_columns(connection, table):
    rows = query_rows(connection,
        "SELECT column_name, data_type, is_nullable, character_maximum_length "
        "FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s", ("account_service", table))
    if not rows:
        raise ValueError(f"目标表不存在: account_service.{table}")
    return ({row["column_name"] for row in rows},
            {row["column_name"] for row in rows if row["data_type"] in ("bit", "bit varying")},
            {row["column_name"] for row in rows if row["is_nullable"] == "NO"},
            {row["column_name"]: row["character_maximum_length"] for row in rows
             if row["character_maximum_length"] is not None})


def target_data(connection):
    business = {table: query_rows(connection, f"SELECT * FROM account_service.{table}")
                for table in BUSINESS_TARGETS}
    users = query_rows(connection,
        "SELECT id, username, code, user_type, biz_code, login_id, enabled, locked, "
        "failed_count, source, password_hash_type FROM auth_service.sys_user")
    roles = query_rows(connection,
        "SELECT id, code FROM auth_service.sys_role WHERE code IN ('CLIENT', 'ADVISOR')")
    user_roles = query_rows(connection,
        "SELECT user_id, role_id FROM auth_service.ref_user_role")
    return business, users, roles, user_roles


def add_exception(exceptions, category, key, reason):
    exceptions.append({"category": category, "key": str(key), "reason": reason})


def business_plan(source_business, target_business, column_info):
    """按目标主键只补不存在的行；不覆盖 V2 现有数据。"""
    actions = {table: [] for table in BUSINESS_TARGETS}
    exceptions = []
    existing = {}
    for _, target, keys in SOURCE_BUSINESS:
        existing[target] = {
            tuple(clean_key(row.get(key)) for key in keys)
            for row in target_business[target]
        }

    staged = {table: set(keys) for table, keys in existing.items()}
    for source, target, keys in SOURCE_BUSINESS:
        columns, bits, required, text_limits = column_info[target]
        product_codes = None
        if target == "rel_joint_acct":
            product_codes = {
                clean_key(product["client_code"])
                for product in target_business["base_client_prd"] + actions["base_client_prd"]
            }
        for raw in source_business[source]:
            row = map_business_row(source, raw, columns, bits)
            key = tuple(clean_key(row.get(field)) for field in keys)
            label = "/".join(str(part) for part in key)
            if any(part is None or part == "" for part in key):
                add_exception(exceptions, source, label, "source primary key is empty")
                continue
            if key in existing[target]:
                continue
            if key in staged[target]:
                add_exception(exceptions, source, label, "duplicate source key after mapping")
                continue
            overlong = sorted((field, limit) for field, limit in text_limits.items()
                              if isinstance(row.get(field), str) and len(row[field]) > limit)
            if overlong:
                field, limit = overlong[0]
                add_exception(exceptions, source, label,
                              f"target column {field} exceeds {limit} characters")
                continue
            missing_required = sorted(field for field in required if row.get(field) is None)
            if missing_required:
                add_exception(exceptions, source, label,
                              "required target fields missing: " + ",".join(missing_required))
                continue
            if target == "base_client_prd" and (row["code"],) not in staged["base_client"]:
                add_exception(exceptions, source, label, "parent base_client missing")
                continue
            if target == "rel_joint_acct":
                if row["joint_client_code"] not in product_codes or row["client_code"] not in product_codes:
                    add_exception(exceptions, source, label, "joint/member product account missing")
                    continue
            actions[target].append(row)
            staged[target].add(key)
    return actions, exceptions


def make_link_maps(links):
    clients = defaultdict(list)
    advisors = defaultdict(list)
    subadvisors = defaultdict(list)
    for row in links["client"]:
        clients[row["login_id"]].append((row["code"], clean_key(row["clnt_type"])))
    for row in links["advisor"]:
        advisors[row["login_id"]].append(row["Code"])
    for row in links["subadvisor"]:
        subadvisors[row["login_id"]].append(row["Code"])
    return clients, advisors, subadvisors


def account_plan(logins, groups, links, target_business, business_actions,
                 existing_users, roles, existing_user_roles, now=None):
    clients, advisors, subadvisors = make_link_maps(links)
    users_by_name = {row["username"]: (row["id"], row["code"], row["user_type"])
                     for row in existing_users}
    users_by_code = {clean_key(row["code"]): (row["username"], row["id"])
                     for row in existing_users if row["code"]}
    role_ids = {row["code"]: row["id"] for row in roles}
    if not {"CLIENT", "ADVISOR"}.issubset(role_ids):
        raise ValueError("V2 缺少 CLIENT 或 ADVISOR 角色")
    current_roles = {(row["user_id"], row["role_id"]) for row in existing_user_roles}
    clients_by_code = {clean_key(row["code"]): row for row in target_business["base_client"]
                       + business_actions["base_client"]}
    advisors_by_code = defaultdict(list)
    for row in target_business["base_advisor"] + business_actions["base_advisor"]:
        advisors_by_code[clean_key(row["code"])].append(row)

    new_users = []
    missing_roles = []
    exceptions = []
    now = now or datetime.now()
    for login in logins:
        username = login["login_id"]
        if not username or username != username.strip():
            add_exception(exceptions, "MstLogin", username, "login ID contains edge whitespace")
            continue
        if login["group_code"] not in groups:
            add_exception(exceptions, "MstLogin", username, "MstGroup missing")
            continue
        try:
            user_type, code = resolve_identity(username, clients[username],
                                                advisors[username], subadvisors[username])
        except MigrationConflict as error:
            current = users_by_name.get(username)
            advisor_codes = {clean_key(value) for value in advisors[username]}
            if current and current[2] == 'ADVISOR' and clean_key(current[1]) in advisor_codes:
                user_type, code = 'ADVISOR', clean_key(current[1])
                add_exception(exceptions, 'MstLogin', username,
                              'preserved existing V2 advisor identity among multiple V1 business codes')
            else:
                add_exception(exceptions, "MstLogin", username, str(error))
                continue
        # Preserve a V2-renamed login for the same identity instead of creating a second user.
        # The full preflight validates code uniqueness before this one-to-one lookup.
        owner = users_by_code.get(code)
        if username not in users_by_name and owner and owner[1] is not None:
            existing_name = owner[0]
            existing = users_by_name[existing_name]
            if existing[2] == user_type:
                role_id = role_ids[user_type]
                if (existing[0], role_id) not in current_roles:
                    missing_roles.append((existing[0], code, role_id))
                    current_roles.add((existing[0], role_id))
                add_exception(exceptions, "MstLogin", username, "preserved existing V2 username: " + existing_name)
                continue
        conflict = user_conflict(username, code, users_by_name, users_by_code)
        if conflict:
            add_exception(exceptions, "MstLogin", username, conflict)
            continue
        role_id = role_ids[user_type]
        existing = users_by_name.get(username)
        if existing:
            if existing[2] != user_type:
                add_exception(exceptions, "MstLogin", username, "existing V2 user_type differs")
            elif (existing[0], role_id) not in current_roles:
                missing_roles.append((existing[0], code, role_id))
                current_roles.add((existing[0], role_id))
            continue

        expiry = login["expiry_date"]
        if expiry and expiry > now:
            add_exception(exceptions, "MstLogin", username,
                          "future account expiry cannot be enforced by current V2")
            continue
        if user_type == "CLIENT":
            business = clients_by_code.get(code)
        else:
            advisor_rows = advisors_by_code.get(code, [])
            business = next(iter(advisor_rows), None)
        if business is None:
            add_exception(exceptions, "MstLogin", username, "V2 business identity missing")
            continue
        phone_key = "mobile" if user_type == "CLIENT" else "tel1"
        name_key = "client_name" if user_type == "CLIENT" else "name"
        new_users.append({
            "username": username,
            "code": code,
            "login_id": username,
            "biz_code": code,
            "user_type": user_type,
            "nick_name": (business.get(name_key) or "")[:100],
            "email": business.get("email"),
            "phone_number": business.get(phone_key),
            "enabled": expiry is None or expiry > now,
            "locked": int(login.get("login_attemp") or 0) >= 3,
            "failed_count": int(login.get("login_attemp") or 0),
            "source": MIGRATION_SOURCE,
            "source_id": username,
            "role_id": role_id,
        })
        users_by_name[username] = (None, code, user_type)
        users_by_code[code] = (username, None)
    return new_users, missing_roles, exceptions


def insert_row(cursor, table, row, returning=None):
    columns = sorted(row)
    fields = ", ".join('"' + column + '"' for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    suffix = " RETURNING " + returning if returning else ""
    cursor.execute(
        f"INSERT INTO {table} ({fields}) VALUES ({placeholders}) "
        f"ON CONFLICT DO NOTHING{suffix}",
        [row[column] for column in columns],
    )
    if cursor.rowcount != 1:
        raise MigrationConflict(f"concurrent conflict while inserting into {table}")
    return cursor.fetchone()[0] if returning else None


def validate_business_inserts(connection, business_actions):
    """在短事务里试插业务行并始终回滚，先发现外键与字段约束错误。"""
    cursor = connection.cursor()
    try:
        for table in BUSINESS_TARGETS:
            full_table = "account_service." + table
            for row in business_actions[table]:
                try:
                    insert_row(cursor, full_table, row)
                except Exception as error:
                    key = row.get("code") or row.get("joint_client_code")
                    raise MigrationConflict(
                        f"business insert validation failed: {full_table}/{key}"
                    ) from error
    finally:
        connection.rollback()
        cursor.close()


def apply_plan(connection, business_actions, new_users, missing_roles, *, updates=(), verify=None,
               before_commit=None, prepare_transaction=None):
    """所有插入在同一 PostgreSQL 事务；任一步失败则整体回滚。"""
    import bcrypt

    results = {table: [] for table in RESULT_COLUMNS}
    # 每个新账号单独生成 BCrypt 盐；哈希计算不占用数据库事务时间。
    prepared_users = [
        (user, bcrypt.hashpw(
            DEFAULT_INITIAL_PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=10)
        ).decode("ascii"))
        for user in new_users
    ]
    cursor = connection.cursor()
    role_actions = [(user_id, code, role_id, "existing V2")
                    for user_id, code, role_id in missing_roles]
    commit_attempted = False
    try:
        if prepare_transaction is not None:
            prepare_transaction(connection)
        if updates:
            from login_users.reconciliation import apply_updates
            apply_updates(cursor, updates)
        for table in BUSINESS_TARGETS:
            for row in business_actions[table]:
                full_table = "account_service." + table
                insert_row(cursor, full_table, row)
                results[full_table].append({key: row.get(key) for key in RESULT_COLUMNS[full_table]})
        for user, password in prepared_users:
            fields = {key: value for key, value in user.items() if key != "role_id"}
            fields.update(password=password, password_hash_type="BCRYPT",
                          created_by=MIGRATION_SOURCE, created_ip="0.0.0.0")
            user_id = insert_row(cursor, "auth_service.sys_user", fields, "id")
            results["auth_service.sys_user"].append({
                "id": user_id, "username": user["username"], "code": user["code"],
                "user_type": user.get("user_type"),
            })
            role_actions.append((user_id, user["code"], user["role_id"], "new"))
        for user_id, code, role_id, account_origin in role_actions:
            insert_row(cursor, "auth_service.ref_user_role", {
                "user_id": user_id, "user_code": code, "role_id": role_id,
                "scope_type": "GLOBAL", "scope_id": 0,
                "created_by": MIGRATION_SOURCE, "created_ip": "0.0.0.0",
            })
            results["auth_service.ref_user_role"].append({
                "user_id": user_id, "user_code": code, "role_id": role_id,
                "account_origin": account_origin,
            })
        if verify is not None:
            verify(connection)
        if before_commit is not None:
            before_commit(results)
        commit_attempted = True
        connection.commit()
    except Exception as error:
        try:
            connection.rollback()
        except Exception:
            pass  # Keep the original failure when the connection is already lost.
        if commit_attempted:
            raise MigrationConflict('commit outcome unknown; inspect the pending receipt and database before retrying') from error
        raise
    finally:
        cursor.close()
    return results


def export_result_xlsx(path, results, source, target, exceptions, *, details=None, metadata=None):
    """仅导出本次成功插入的核对字段，不包含密码或密码哈希。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    path = Path(path)
    if path.suffix.lower() != ".xlsx":
        raise ValueError("结果文件必须是 .xlsx")
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    summary.append(["V1 登录账号迁移结果"])
    summary.append(["来源", source])
    summary.append(["目标", target])
    summary.append(["未导入异常", len(exceptions)])
    summary.append(["V2 表", "本次新增"])
    for table, columns in RESULT_COLUMNS.items():
        rows = results[table]
        summary.append([table, len(rows)])
        sheet = workbook.create_sheet(table.split(".", 1)[1])
        sheet.append(columns)
        for row in rows:
            sheet.append([row.get(column) for column in columns])
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
                    cell.number_format = "@"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(columns, start=1):
            sheet.column_dimensions[sheet.cell(1, index).column_letter].width = max(18, len(column) + 3)
        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor="DCE9F5")
            cell.font = Font(bold=True)
    summary.append(["合计", sum(len(rows) for rows in results.values())])
    summary.append(["导出时间", datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")])
    summary.column_dimensions["A"].width = 38
    summary.column_dimensions["B"].width = 20
    summary.freeze_panes = "A6"
    summary.auto_filter.ref = "A5:B11"
    for cell in summary[5]:
        cell.fill = PatternFill("solid", fgColor="DCE9F5")
        cell.font = Font(bold=True)
    exception_sheet = workbook.create_sheet("Exceptions")
    exception_sheet.append(["category", "key", "reason"])
    for row in exceptions:
        exception_sheet.append([row.get("category"), row.get("key"), row.get("reason")])
        for cell in exception_sheet[exception_sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = "s"
                cell.number_format = "@"
    exception_sheet.freeze_panes = "A2"
    exception_sheet.auto_filter.ref = exception_sheet.dimensions
    for column, width in {"A": 24, "B": 24, "C": 55}.items():
        exception_sheet.column_dimensions[column].width = width
    for cell in exception_sheet[1]:
        cell.fill = PatternFill("solid", fgColor="DCE9F5")
        cell.font = Font(bold=True)

    for key, value in (metadata or {}).items():
        summary.append([key, value])
    for name, rows in (details or {}).items():
        sheet = workbook.create_sheet(name)
        columns = list(dict.fromkeys(key for row in rows for key in row))
        sheet.append(columns or ['No records'])
        for row in rows:
            sheet.append([row.get(column) for column in columns])
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(columns, 1):
            values = [str(row.get(column) or '') for row in rows[:100]]
            width = min(65, max(18, len(column) + 2, max(map(len, values), default=0) + 2))
            sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
        for cell in sheet[1]:
            cell.fill = PatternFill('solid', fgColor='DCE9F5')
            cell.font = Font(bold=True)
    # All report strings are data, including source-derived names beginning with =.
    for sheet in workbook:
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'

    created = False
    try:
        with path.open("xb") as output:
            created = True
            workbook.save(output)
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise
    finally:
        workbook.close()


def main(argv=None):
    import sys
    # Also support direct execution from outside the unittrust working directory.
    if str(SCRIPT_DIR.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR.parent))
    from login_users.pipeline import run_cli
    return run_cli(argv, sys.modules[__name__])


if __name__ == "__main__":
    main()
