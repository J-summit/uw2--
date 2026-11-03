"""预检、单事务迁移、存量补正及提交前验收。"""

import argparse
import copy
from contextlib import suppress
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .audit import build_account_audit
from .reconciliation import plan_reconciliation
from .reporting import write_json, report_details, report_summary


def classify_exceptions(exceptions, required_codes):
    blockers = {'username belongs to another business code', 'code belongs to another username',
                'existing V2 user_type differs', 'V2 business identity missing',
                'login ID maps to multiple clients', 'advisor has multiple business codes',
                'future account expiry cannot be enforced by current V2', 'duplicate source key after mapping'}
    required_codes = set(required_codes)
    return [dict(row, severity='BLOCKER' if row['reason'] in blockers or
                 row['category'] != 'MstLogin' and row['key'].split('/')[0] in required_codes
                 else 'WARNING') for row in exceptions]


def validate_identities(users):
    issues = []
    for field in ('username', 'code'):
        owners = defaultdict(list)
        for row in users:
            if row.get(field):
                owners[row[field]].append(row.get('id'))
        for key, ids in owners.items():
            if len(ids) > 1:
                issues.append(dict(severity='BLOCKER', category='sys_user', key=key,
                                   reason=f'duplicate target {field}; cannot infer account owner'))
    return issues


def project_target(business, users, actions, new_users, updates):
    business, users = copy.deepcopy(business), copy.deepcopy(users)
    for update in updates:
        table = update['table'].split('.')[1]
        rows = users if table == 'sys_user' else business[table]
        for row in rows:
            if all(row.get(k) == v for k, v in update['key'].items()):
                row.update(update['after'])
                break
    for table, rows in actions.items():
        business[table].extend(copy.deepcopy(rows))
    users.extend(dict(row, id='planned:' + row['username']) for row in new_users)
    return business, users


def build_plan(api, source, target, column_info, now, repair_only=False):
    business, logins, groups, links, user_login = source
    existing, users, roles, user_roles = target
    actions, business_errors = api.business_plan(business, existing, column_info)
    new_users, missing_roles, user_errors = api.account_plan(
        logins, groups, links, existing, actions, users, roles, user_roles, now=now)
    updates, update_errors = plan_reconciliation(business, logins, links, existing, users, now, groups=groups)
    required = {row['code'] for row in links['client']} | {row['Code'] for row in links['advisor']}
    issues = classify_exceptions(business_errors + user_errors, required)
    users_by_name = {row['username']: row for row in users}
    for issue in issues:
        if issue['reason'] == 'advisor has multiple business codes':
            user = users_by_name.get(issue['key'])
            codes = {row['Code'].strip() for row in links['advisor'] if row['login_id'] == issue['key']}
            if user and user['user_type'] == 'ADVISOR' and user['code'] in codes:
                issue['severity'] = 'WARNING'
                issue['reason'] = 'preserved existing V2 advisor identity among multiple V1 business codes'
    issues += validate_identities(users) + update_errors
    source_names = Counter(row['login_id'] for row in logins)
    issues += [dict(severity='BLOCKER', category='MstLogin', key=key, reason='duplicate source login_id')
               for key, count in source_names.items() if count > 1]
    if repair_only:
        actions = {table: [] for table in api.BUSINESS_TARGETS}
        new_users, missing_roles = [], []
        # Repair only touches existing rows. Unrelated excluded new-account dependencies are reported.
        for issue in issues:
            if issue not in update_errors and issue['category'] != 'sys_user':
                issue['severity'] = 'WARNING'
    projected_business, projected_users = project_target(existing, users, actions, new_users, updates)
    audit = build_account_audit(business, logins, groups, links, user_login, projected_business, projected_users, now)
    new_names = {row['username'] for row in new_users}
    for row in audit['accounts']:
        if row.get('v2_username') in new_names:
            row['disposition'] = 'NEW_PLANNED'
    for row in audit['scope_differences']:
        if row['classification'] == 'DATA_DRIFT':
            issues.append(dict(severity='BLOCKER' if row['username'] in new_names else 'WARNING',
                               category='ACCOUNT_SCOPE', key=row['username'],
                               reason='V2 product scope differs from the same V2 rule applied to V1 data; see ScopeDiff'))
    issues += audit['issues']
    audit['issues'] = issues
    return dict(business=actions, new_users=new_users, missing_roles=missing_roles,
                updates=updates, issues=issues, audit=audit)


def signature(plan):
    value = {key: plan[key] for key in ('business', 'new_users', 'missing_roles', 'updates')}
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def change_count(plan):
    return sum(map(len, plan['business'].values())) + len(plan['new_users']) + len(plan['missing_roles']) + len(plan['updates'])


def credentials(api, connection):
    # Only keep fingerprints in memory; no old hash, plaintext or fingerprint is exported.
    rows = api.query_rows(connection, "SELECT id, username, code, login_id, biz_code, password_hash_type, "
                          "md5(COALESCE(password, '')) AS digest FROM auth_service.sys_user")
    return {row['id']: row for row in rows}


def print_plan(plan):
    print('待新增:', {key: len(rows) for key, rows in plan['business'].items()}, flush=True)
    print(f"待新增登录账号: {len(plan['new_users'])}; 待补已有账号角色: {len(plan['missing_roles'])}", flush=True)
    print('待更新:', dict(Counter(row['table'] for row in plan['updates'])), flush=True)
    print('预检问题:', dict(Counter(row['severity'] for row in plan['issues'])), flush=True)
    print('问题原因:', dict(Counter(row['reason'] for row in plan['issues'])), flush=True)


def planned_inserts(api, plan):
    rows = []
    for source, table, keys in api.SOURCE_BUSINESS:
        if source == 'MstClntPrd3':
            continue
        for row in plan['business'][table]:
            rows.append(dict(table='account_service.'+table,
                             key='/'.join(str(row.get(k) or '') for k in keys), action='INSERT_PLANNED'))
    for user in plan['new_users']:
        rows.append(dict(table='auth_service.sys_user',key=user['username'],action='INSERT_PLANNED',
                         code=user['code'],user_type=user['user_type']))
        rows.append(dict(table='auth_service.ref_user_role',key=user['username'],action='INSERT_PLANNED',
                         code=user['code'],role_id=user['role_id']))
    for user_id, code, role_id in plan['missing_roles']:
        rows.append(dict(table='auth_service.ref_user_role',key=str(user_id),action='INSERT_PLANNED',code=code,role_id=role_id))
    return rows


def run_cli(argv, api):
    parser = argparse.ArgumentParser(description=api.__doc__)
    parser.add_argument('--config', default=str(api.DEFAULT_CONFIG))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--repair-only', action='store_true', help='仅修正存量行，不新增业务/用户/角色')
    parser.add_argument('--confirm-target', help='必须等于 host:port/database')
    parser.add_argument('--report-json', help='可选只读审计 JSON，不包含密码或联系方式原值')
    parser.add_argument('--result-xlsx', help='Excel 路径，写入时必填；预检时可选')
    args = parser.parse_args(argv)
    config = api.load_config(args.config)
    target_label = f"{config['postgresql']['host']}:{config.get('postgresql','port',fallback='5432')}/{config['postgresql']['database']}"
    source_host, source_port = api.mssql_endpoint(config)
    source_label = f"{source_host}:{source_port}/{config['mssql']['database']}"
    if config['mssql']['database'].casefold() != 'unittrust':
        parser.error('V1 登录迁移来源必须是 UnitTrust，不是 PYMTGW')
    if args.apply and args.confirm_target != target_label:
        parser.error(f'写入目标确认失败；请传入 --confirm-target {target_label}')
    if args.apply and not args.result_xlsx:
        parser.error('--apply 必须指定 --result-xlsx')
    path = Path(args.result_xlsx).resolve() if args.result_xlsx else None
    if path and (path.suffix.lower() != '.xlsx' or not path.parent.is_dir()):
        parser.error('Excel 必须是父目录已存在的 .xlsx 路径')
    prefix = path.with_suffix('') if path else None
    artifact_paths = [path] if path else []
    if args.apply:
        artifact_paths += [Path(str(prefix)+suffix) for suffix in ('.backup.json','.pending.json','.committed.json')]
    if args.report_json:
        artifact_paths.append(Path(args.report_json))
    if any(p.exists() for p in artifact_paths):
        parser.error('输出文件已存在；请使用新文件名，历史结果不会覆盖')
    print(f'来源 {source_label}; 目标 {target_label}; 模式 '+('写入' if args.apply else '只读预检'), flush=True)
    source_connection = target_connection = None
    committed = False
    try:
        source_connection = api.connect_source(config)
        source_meta = api.query_rows(source_connection, 'SELECT DB_NAME() AS name, GETDATE() AS source_now')[0]
        if source_meta['name'].casefold() != 'unittrust':
            raise ValueError('Connected source is not UnitTrust')
        now = source_meta['source_now']
        source = api.source_data(source_connection)
        source_connection.close()
        source_connection = None
        target_connection = api.connect_target(config)
        if api.query_rows(target_connection, 'SELECT current_database() AS name')[0]['name'] != config['postgresql']['database']:
            raise ValueError('Connected target database differs from configuration')
        columns = {table: api.target_columns(target_connection, table) for table in api.BUSINESS_TARGETS}
        target = api.target_data(target_connection)
        plan = build_plan(api, source, target, columns, now, args.repair_only)
        insert_plan = planned_inserts(api, plan)
        print_plan(plan)
        results = {table: [] for table in api.RESULT_COLUMNS}
        checks = []
        blocked = any(issue['severity'] == 'BLOCKER' for issue in plan['issues'])
        checks.append(dict(check='preflight_blockers', result='FAIL' if blocked else 'PASS',
                           value=sum(issue['severity'] == 'BLOCKER' for issue in plan['issues'])))
        def export_report(mode):
            details = report_details(plan['updates'], plan['audit'], checks)
            details['PlannedInserts'] = insert_plan
            summary = report_summary(mode, plan['updates'], plan['audit'])
            summary['计划新增行数（含角色）'] = len(insert_plan)
            api.export_result_xlsx(path, results, source_label, target_label, plan['issues'],
                                   details=details, metadata=summary)
        if args.report_json:
            write_json(args.report_json, dict(mode='PREFLIGHT', source=source_label, target=target_label,
                                             planned_inserts=insert_plan,
                                             updates=report_details(plan['updates'],plan['audit'],checks)['Changes'], **plan['audit']))
        if args.apply and blocked:
            export_report('BLOCKED / NO WRITES')
            raise ValueError('预检有 BLOCKER，未执行写入；请处理 Excel 中的问题后重跑')
        if args.apply:
            target_connection.rollback()
            before_credentials = {}
            def prepare(connection):
                cursor = connection.cursor()
                try:
                    cursor.execute("SET LOCAL lock_timeout = '10s'")
                    cursor.execute("SET LOCAL statement_timeout = '120s'")
                    cursor.execute('LOCK TABLE account_service.base_client, account_service.base_advisor, '
                        'account_service.base_client_prd, account_service.rel_joint_acct, '
                        'auth_service.sys_user, auth_service.ref_user_role IN SHARE ROW EXCLUSIVE MODE')
                    cursor.execute('LOCK TABLE auth_service.sys_role IN SHARE MODE')
                finally:
                    cursor.close()
                fresh = build_plan(api, source, api.target_data(connection), columns, now, args.repair_only)
                if signature(fresh) != signature(plan) or any(x['severity']=='BLOCKER' for x in fresh['issues']):
                    raise ValueError('Target changed since preflight; no writes, rerun against fresh data')
                before_credentials.update(credentials(api, connection))
                keys = {table: [{key: row.get(key) for key in api.RESULT_COLUMNS['account_service.'+table]}
                                for row in rows] for table, rows in plan['business'].items()}
                write_json(str(prefix)+'.backup.json', dict(status='PREPARED_NOT_PROOF_OF_COMMIT',
                    source=source_label,target=target_label,source_time=now,updates=plan['updates'],
                    planned_business_keys=keys,planned_usernames=[r['username'] for r in plan['new_users']],
                    planned_existing_roles=plan['missing_roles']))

            def verify(connection):
                fresh_target = api.target_data(connection)
                remaining = build_plan(api, source, fresh_target, columns, now, args.repair_only)
                if change_count(remaining):
                    raise ValueError('Post-write verification found pending changes; entire transaction rolled back')
                after_credentials = credentials(api, connection)
                if any(after_credentials.get(key) != value for key, value in before_credentials.items()):
                    raise ValueError('Existing credential/identity changed; entire transaction rolled back')
                expected_names = {row['username'] for row in plan['new_users']}
                actual_names = {row['username'] for key,row in after_credentials.items() if key not in before_credentials}
                if actual_names != expected_names:
                    raise ValueError('New account count or identity mismatch')
                plan['audit'] = remaining['audit']
                for row in plan['audit']['accounts']:
                    if row.get('v2_username') in expected_names:
                        row['disposition'] = 'INSERTED_THIS_RUN'
                checks.extend([dict(check='remaining_mutations',result='PASS',value=0),
                               dict(check='existing_credentials_preserved',result='PASS',value=len(before_credentials)),
                               dict(check='new_accounts_verified',result='PASS',value=len(actual_names))])

            def pending(insert_results):
                write_json(str(prefix)+'.pending.json', dict(status='VERIFIED_PENDING_COMMIT',
                    source=source_label,target=target_label,results=insert_results,checks=checks))

            print('开始准备新用户密码和事务；已有密码保持不变。', flush=True)
            results = api.apply_plan(target_connection, plan['business'], plan['new_users'], plan['missing_roles'],
                updates=plan['updates'], prepare_transaction=prepare, verify=verify, before_commit=pending)
            committed = True
            write_json(str(prefix)+'.committed.json', dict(status='COMMITTED',source=source_label,target=target_label,
                results=results,updates=report_details(plan['updates'],plan['audit'],checks)['Changes'],
                audit=plan['audit'],checks=checks))
            print('事务已提交，提交前验收通过。', flush=True)
        if path:
            export_report('COMMITTED' if args.apply else 'READ ONLY / PLANNED')
            print(f'Excel: {path}', flush=True)
        if blocked:
            raise ValueError('预检有 BLOCKER；未执行写入')
    except Exception:
        if committed:
            print(f'数据库已经提交；后续报告失败。请根据 {prefix}.pending.json 与 .committed.json 恢复报告，不要误判为回滚。', flush=True)
        raise
    finally:
        if source_connection:
            source_connection.close()
        if target_connection:
            with suppress(Exception):
                target_connection.rollback()
            with suppress(Exception):
                target_connection.close()
