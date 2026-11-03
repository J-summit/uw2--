"""有边界的存量数据补正：不覆盖密码或已有非空联系方式。"""

from collections import defaultdict


UPDATE_FIELDS = {
    "account_service.base_client_prd": ({"code", "acct_no"}, {"date_close"}),
    "account_service.base_client": ({"code"}, {"mobile", "email"}),
    "auth_service.sys_user": ({"id"}, {"enabled", "locked", "failed_count"}),
}


def _key(value):
    return value.strip() if isinstance(value, str) else value


def _blank(value):
    return value is None or isinstance(value, str) and not value.strip()


def _update(table, key, current, desired, reason):
    changes = {field: value for field, value in desired.items() if current.get(field) != value}
    if not changes:
        return None
    return {"table": table, "key": key, "before": {field: current.get(field) for field in changes},
            "after": changes, "reason": reason}


def plan_reconciliation(source_business, logins, links, target_business, users, now, groups=None):
    updates, issues = [], []

    def block(category, key, reason):
        issues.append({"severity": "BLOCKER", "category": category, "key": str(key), "reason": reason})

    products = defaultdict(list)
    for table in ("MstClntPrd2", "MstClntPrd3"):
        for row in source_business[table]:
            products[(_key(row.get("code")), _key(row.get("acct_no")))].append(row)
    target_products = {(_key(r["code"]), _key(r["acct_no"])): r for r in target_business["base_client_prd"]}
    for key, rows in sorted(products.items(), key=lambda item: str(item[0])):
        if any(part is None or part == '' for part in key):
            block('MstClntPrd2/3', str(key), 'source product primary key is empty')
            continue
        current = target_products.get(key)
        variants = {(_key(r.get("client_code")), r.get("date_close")) for r in rows}
        if len(variants) != 1:
            block("MstClntPrd2/3", "/".join(str(x) for x in key), "conflicting source product identity/close date")
            continue
        if current is None:
            continue
        row = rows[0]
        if _key(current.get("client_code")) != _key(row.get("client_code")):
            block("base_client_prd", "/".join(str(x) for x in key), "product key belongs to a different client_code")
            continue
        change = _update("account_service.base_client_prd", dict(zip(("code", "acct_no"), key)),
                         current, {"date_close": row.get("date_close")}, "align V1 product close date")
        if change:
            updates.append(change)

    target_clients = {_key(r["code"]): r for r in target_business["base_client"]}
    for row in source_business["MstClient"]:
        current = target_clients.get(_key(row.get("code")))
        if current is None:
            continue
        desired = {field: row[field] for field in ("mobile", "email")
                   if _blank(current.get(field)) and not _blank(row.get(field))}
        change = _update("account_service.base_client", {"code": current["code"]}, current, desired,
                         "fill missing registered contact from V1; preserve existing contacts")
        if change:
            updates.append(change)

    identities = {kind: defaultdict(set) for kind in ("client", "advisor", "subadvisor")}
    for kind, records in links.items():
        for row in records:
            identities[kind][row["login_id"]].add(_key(row.get("code", row.get("Code"))))
    target_users = {u["username"]: u for u in users}
    user_restrictions = {}
    users_by_code = defaultdict(list)
    for user in users:
        users_by_code[(user.get('user_type'), _key(user.get('code')))].append(user)
    for login in logins:
        name = login["login_id"]
        current = target_users.get(name)
        if identities["advisor"][name]:
            kind, codes = "ADVISOR", identities["advisor"][name]
        elif identities["subadvisor"][name]:
            continue  # V2 does not represent sub-advisor account scope.
        else:
            kind, codes = "CLIENT", identities["client"][name]
        if current is None and len(codes) == 1:
            candidates = users_by_code[(kind, next(iter(codes)))]
            current = candidates[0] if len(candidates) == 1 else None
        if current is None:
            continue
        if not codes or _key(current.get("code")) not in codes or current.get("user_type") != kind:
            block("sys_user", name, "existing username has an unconfirmed V1 business identity")
            continue
        desired = {}
        if groups is not None and login.get('group_code') not in groups:
            desired['enabled'] = False
        if login.get("expiry_date") is not None and login["expiry_date"] <= now:
            desired["enabled"] = False
        attempts = int(login.get("login_attemp") or 0)
        if attempts >= 3:
            desired["locked"] = True
            desired["failed_count"] = max(attempts, int(current.get("failed_count") or 0))
        entry = user_restrictions.setdefault(current['id'], (current, {}))
        merged = entry[1]
        for field, value in desired.items():
            merged[field] = max(value, merged.get(field, 0)) if field == 'failed_count' else value
    for current, desired in user_restrictions.values():
        change = _update("auth_service.sys_user", {"id": current["id"]}, current, desired,
                         "preserve V1 restrictions without unlocking/re-enabling V2")
        if change:
            updates.append(change)
    return updates, issues


def apply_updates(cursor, updates):
    for change in updates:
        table, key, before, after = (change[name] for name in ("table", "key", "before", "after"))
        allowed = UPDATE_FIELDS.get(table)
        if not allowed or set(key) != allowed[0] or not after or not set(after).issubset(allowed[1]) or set(before) != set(after):
            raise ValueError("update table, key or fields not allowed")
        fields = sorted(after)
        keys = sorted(key)
        assignment = ", ".join(f'"{field}" = %s' for field in fields)
        conditions = [f'"{field}" = %s' for field in keys]
        conditions += [f'"{field}" IS NOT DISTINCT FROM %s' for field in fields]
        cursor.execute(f"UPDATE {table} SET {assignment} WHERE " + " AND ".join(conditions),
                       [after[f] for f in fields] + [key[f] for f in keys] + [before[f] for f in fields])
        if cursor.rowcount != 1:
            raise ValueError(f"concurrent modification while updating {table}/{key}")
    return updates
