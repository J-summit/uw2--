"""迁移审计文件：不输出密码，联系方式只在回退备份中保留原值。"""

import json
import os
from collections import Counter
from pathlib import Path


def write_json(path, document):
    """Exclusive, durable local evidence before database commit; never overwrite a prior run."""
    with Path(path).open('x', encoding='utf-8') as output:
        json.dump(document, output, ensure_ascii=False, indent=2, default=str)
        output.flush()
        os.fsync(output.fileno())


def change_rows(updates):
    rows = []
    for change in updates:
        for field, after in change['after'].items():
            before = change['before'][field]
            if field in {'mobile', 'email'}:
                before = '[present]' if before else '[empty]'
                after = '[present]' if after else '[empty]'
            rows.append(dict(table=change['table'], key=json.dumps(change['key'], ensure_ascii=False),
                             field=field, before=str(before) if before is not None else None,
                             after=str(after) if after is not None else None, reason=change['reason']))
    return rows


def report_details(updates, audit, checks):
    return {'Changes': change_rows(updates), 'Accounts': audit['accounts'],
            'MFA': audit['contacts'], 'ScopeDiff': audit['scope_differences'],
            'Issues': audit['issues'], 'Checks': checks + audit.get('source_checks', [])}


def report_summary(mode, updates, audit):
    summary = {'执行模式': mode, '更新记录数': len(updates),
               '可用状态不等于已验证真实密码': '未尝试源密码或发送验证码',
               '缺少两种验证码联系方式': sum(r['status'] == 'NO_CONTACT' for r in audit['contacts']),
               'V1 强制改密但存 Argon2 的账号': sum(r['v1_password_branch'] == 'FORCED_WITH_ARGON2_REVIEW' for r in audit['accounts']),
               '账户范围有差异的用户': len(audit['scope_differences']),
               '范围差异口径': '保留 V2 同证件号、联合主账户规则；V1 为客户分支产品范围',
               '子顾问策略': '保留现有 V2 模型；无等价身份映射的账号列入异常，不扩成父顾问权限'}
    summary.update({'更新 ' + table: count for table, count in Counter(c['table'] for c in updates).items()})
    return summary
