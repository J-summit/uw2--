"""登录状态、验证码资料与账户范围的离线验收，不尝试密码或发送验证码。"""

import re
from collections import defaultdict
from datetime import datetime


def normalized(value):
    return str(value or '').strip().casefold()


def timestamp(value):
    if value is None:
        return datetime.min
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=None)


def select_contact(rows, channel):
    def valid(row):
        value = str(row.get('mobile' if channel == 'SMS' else 'email') or '').strip()
        if channel == 'SMS':
            return bool(re.sub(r'[\s-]', '', value))
        # Match MfaService.normalizeEmail, which currently checks only the first @.
        return 0 < value.find('@') < len(value) - 1

    candidates = sorted((row for row in rows if valid(row)), key=lambda row: str(row.get('code') or ''))
    candidates.sort(key=lambda row: timestamp(row.get('updated_at')), reverse=True)
    return next(iter(candidates), None)


class AccountScopes:
    def __init__(self, clients, products, joints, now):
        self.now = timestamp(now)
        self.clients = {row['code']: row for row in clients}
        self.ic_codes = defaultdict(set)
        self.products = defaultdict(list)
        self.product_master = {}
        self.joints = defaultdict(set)
        for row in clients:
            for field in ('new_ic', 'old_ic'):
                # V2 uses exact nonblank identity strings, not a normalized ID.
                if str(row.get(field) or '').strip():
                    self.ic_codes[row[field]].add(row['code'])
        for row in products:
            self.products[row['code']].append(row)
            self.product_master[row['client_code']] = row['code']
        for row in joints:
            self.joints[row['client_code']].add(row['joint_client_code'])
        self.all_active = self.active_products(self.clients)

    def switchable(self, code):
        row = self.clients.get(code, {})
        identity = row.get('new_ic') if str(row.get('new_ic') or '').strip() else row.get('old_ic')
        individual = {code} | self.ic_codes.get(identity, set())
        codes = set(individual)
        for master in individual:
            for product in self.products[master]:
                for joint in self.joints[product['client_code']]:
                    joint_master = self.product_master.get(joint)
                    if joint_master:
                        codes.add(joint_master)
        return codes

    def active_products(self, codes):
        return {normalized(row['client_code']) for code in codes for row in self.products[code]
                if row.get('date_close') is None or timestamp(row['date_close']) > self.now}

    def v1_products(self, codes):
        """V1 client branch: direct products plus exact joint-product relations; no IC expansion."""
        products = {row['client_code'] for code in codes for row in self.products[code]}
        joint_products = {joint for product in products for joint in self.joints[product]}
        return {normalized(code) for code in products | joint_products} & self.all_active


def build_account_audit(source, logins, groups, links, user_login, target, users, now):
    from .migrate_login_users import make_link_maps, resolve_identity, MigrationConflict

    accounts, contacts, differences, issues = [], [], [], []
    clients, advisors, subadvisors = make_link_maps(links)
    by_name = {row['username']: row for row in users}
    by_code = defaultdict(list)
    for row in users:
        by_code[(row.get('user_type'), row.get('code'))].append(row)
    source_index = AccountScopes(source['MstClient'], source['MstClntPrd2'] + source['MstClntPrd3'], source['MstJointAcct'], now)
    target_index = AccountScopes(target['base_client'], target['base_client_prd'], target['rel_joint_acct'], now)
    contact_code, contact_login = defaultdict(list), defaultdict(list)
    for row in target['base_client']:
        contact_code[row['code']].append(row)
        if row.get('login_id'):
            contact_login[row['login_id']].append(row)

    for login in logins:
        name = login['login_id']
        expired = login.get('expiry_date') is not None and timestamp(login['expiry_date']) <= timestamp(now)
        source_locked = int(login.get('login_attemp') or 0) >= 3
        record = dict(v1_login_id=name, v1_group_present=login['group_code'] in groups,
                      v1_expired=expired, v1_locked=source_locked,
                      v1_state_eligible=login['group_code'] in groups and not expired and not source_locked,
                      v1_password_branch=login.get('password_branch', 'NOT_READ'),
                      v2_username=None, user_type=None, code=None, disposition='EXCLUDED')
        try:
            kind, code = resolve_identity(name, clients[name], advisors[name], subadvisors[name])
            record.update(user_type=kind, code=code)
            user = by_name.get(name)
            if user is None:
                owners = by_code[(kind, code)]
                user = owners[0] if len(owners) == 1 else None
                if user:
                    record['disposition'] = 'PRESERVED_V2_USERNAME'
            elif user.get('code') != code or user.get('user_type') != kind:
                # Existing multi-business-code advisors can be valid under the current V2 model.
                user = None
                record['disposition'] = 'IDENTITY_CONFLICT'
            else:
                record['disposition'] = 'EXISTING_V2'
        except MigrationConflict as error:
            record['reason'] = str(error)
            user = by_name.get(name)
            kind, code = (user.get('user_type'), user.get('code')) if user else (None, None)
            if user:
                record.update(disposition='EXISTING_V2_REVIEW', user_type=kind, code=code)
        if user:
            record.update(v2_username=user['username'], v2_enabled=user.get('enabled'),
                          v2_locked=user.get('locked'), v2_state_eligible=bool(user.get('enabled')) and not bool(user.get('locked')))
            record['v2_hash_type'] = user.get('password_hash_type', 'BCRYPT_ON_INSERT')
            if user.get('password_hash_type') == 'LEGACY_ARGON2':
                issues.append(dict(severity='WARNING',category='V2_PASSWORD_HASH',key=name,
                    reason='Current V2 does not verify LEGACY_ARGON2; existing credential preserved and needs separate password reset'))
            if login.get('expiry_date') and timestamp(login['expiry_date']) > timestamp(now):
                issues.append(dict(severity='WARNING', category='FUTURE_EXPIRY', key=name,
                                   reason='Current V2 does not enforce future account expiry; existing account preserved'))
            if kind == 'CLIENT':
                candidates = {}
                for field in ('code', 'biz_code'):
                    for row in contact_code[user.get(field)]:
                        candidates[row['code']] = row
                for field in ('username', 'login_id'):
                    for row in contact_login[user.get(field)]:
                        candidates[row['code']] = row
                sms, email = (select_contact(candidates.values(), channel) for channel in ('SMS', 'EMAIL'))
                contacts.append(dict(username=user['username'], code=code, matches=len(candidates),
                                     sms_client_code=sms['code'] if sms else None,
                                     email_client_code=email['code'] if email else None,
                                     status='READY' if sms or email else 'NO_CONTACT'))
                if not sms and not email:
                    issues.append(dict(severity='WARNING', category='MFA_CONTACT', key=name,
                                       reason='No usable registered SMS/email; Web MFA cannot complete'))
                v1 = source_index.v1_products({c for c, _ in clients[name]})
                expected = source_index.active_products(source_index.switchable(code))
                actual = target_index.active_products(target_index.switchable(code))
                if v1 != actual or expected != actual:
                    differences.append(dict(username=user['username'], code=code,
                        v1_products=', '.join(sorted(v1)), v2_products=', '.join(sorted(actual)),
                        v2_extra_vs_v1=', '.join(sorted(actual-v1)), v2_missing_vs_v1=', '.join(sorted(v1-actual)),
                        data_extra=', '.join(sorted(actual-expected)), data_missing=', '.join(sorted(expected-actual)),
                        classification='DATA_DRIFT' if expected != actual else 'APPROVED_V2_SCOPE',
                        note='V2 retains same-IC and joint master-account expansion; V1 client function baseline, not a password login test'))
            else:
                record['scope_policy'] = 'CURRENT_V2_ADVISOR_MODEL; V1 page/team/subadvisor grants not reproduced'
        accounts.append(record)
    login_names = {normalized(row['login_id']) for row in logins}
    client_codes = {normalized(row['code']) for row in source['MstClient']}
    source_checks = [
        dict(check='MstUserLogin_missing_login', result='INFO',
             value=sum(normalized(row['login_id']) not in login_names for row in user_login)),
        dict(check='MstUserLogin_missing_client', result='INFO',
             value=sum(normalized(row['code']) not in client_codes for row in user_login)),
    ]
    return dict(accounts=accounts, contacts=contacts, scope_differences=differences, issues=issues,
                source_checks=source_checks)
