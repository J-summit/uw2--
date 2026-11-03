# V1 登录用户迁移到 V2

本 package 读取 MSSQL `UnitTrust`，补齐 V2 PostgreSQL 的登录身份及业务依赖，并修正存量差异。默认只读；只有 `--apply` 会写入。配置独立放在本目录 `db.ini`（已被 Git 忽略）。

复制整个 `login_users` 文件夹即可使用，不依赖父目录的脚本或依赖清单。唯一执行入口是 `migrate_login_users.py`；完整迁移包含所需补正，不需要另跑修补脚本。

```text
login_users/
├── __init__.py              # Python 包标识
├── migrate_login_users.py   # 唯一执行入口
├── pipeline.py              # 预检、事务及验收
├── reconciliation.py        # 完整迁移自动调用的存量补正规则
├── audit.py                 # 登录身份与账户范围核对
├── reporting.py             # 备份、回执及 Excel
├── requirements.txt         # 本迁移所需 Python 依赖
├── db.ini                   # 当前环境连接配置
└── README.md                # 判断逻辑及执行说明
```

## 判断与处理流程（简版）

1. **确定登录主体**：从 `MstLogin` 读取登录名，检查 `MstGroup` 是否存在；不会给所有客户或联合账户编号直接创建登录账号。
2. **确定业务身份**：关联 `MstBFEUser`、`MstBFEUser4`、`MstClient`，识别顾问或客户及其业务 code。一个登录名同时关联普通客户和联合客户时，以普通客户作为登录主体。
3. **判断新增还是保留**：V2 已有且身份一致，保留用户名和密码，只补缺失角色；同 code 已有其他 V2 用户名也保留现有账号。V2 没有且身份、依赖齐全，新增 `sys_user` 和角色，密码为 `123456a.`。
4. **处理登录状态**：V1 已过期则禁用，失败次数达到 3 次则锁定；已有 V2 账号只收紧限制，不自动启用或解锁。新账号有未来到期时间则阻止导入，已有账号则记录警告。不验证旧密码。
5. **补齐并修正业务数据**：补缺失客户、顾问、产品账户和联合关系；已有产品账户对齐关闭日期，客户手机号和邮箱只补空值。保留 V2 同证件号及联合账户范围规则，并报告差异。
6. **处理异常**：身份冲突、必要依赖缺失等阻断整次写入；无业务身份、无法映射的子顾问等不自动导入，记录原因。预检无阻断项不代表所有历史账号都能导入。
7. **统一写入与验收**：保存修改前备份，在一个事务内执行新增和补正；确认无待处理变更、已有身份和密码未被覆盖后提交，再导出 Excel。失败回滚；提交结果未知时先查库核对。

只执行 `migrate_login_users.py` 统一入口，完整迁移已经包含补正步骤，无须再单独运行补正模块。

## 登录判断与迁移口径

1. `MstLogin INNER JOIN MstGroup` 确定 V1 登录记录和组是否存在。结合 `expiry_date`、`login_attemp >= 3` 判断过期及锁定。
2. 按 V1 优先级解析 `MstBFEUser`、`MstBFEUser4`、`MstClient`。普通顾问映射 `ADVISOR`；客户映射 `CLIENT`；同一登录名关联一个普通客户和联合客户时，普通客户作为登录主体。
3. **账号状态允许登录，不代表旧密码验证成功。** V1 还会走旧密码/强制改密分支及临时会话检查。报告保留密码分支分类，不读取或尝试旧密码，不迁移旧会话。`FORCED_WITH_ARGON2_REVIEW` 表示 V1 强制改密分支与 Argon2 存储组合需要复核；新账号按已确定的重置密码政策创建。
4. V2 已存在的账号保留用户名、密码、密码哈希类型及业务身份；只有确认业务身份一致时补角色、收紧状态。同 code 已有不同 V2 用户名时保留现有用户名并报告映射。两个待新增用户名竞争同 code 不自动合并，预检阻止写入。
5. 新增账号初始密码为 `123456a.`，**末尾包含句点**；每个账号使用独立 BCrypt 盐。已过期账号导入为禁用，V1 锁定账号导入为锁定；不自动解除 V2 已有的禁用/锁定。
6. 当前 V2 没有账号未来到期的等价检查。新账号存在未来到期时间时阻止写入；已有账号保留并列出警告，不能用 `password_expired_at` 代替账号到期策略。
7. 按现有 V2 模型处理，不新增子顾问权限模型。`MstBFEUser4` 的父顾问 code 与子顾问编号不能直接当作独立 V2 身份；没有等价映射的账号留在异常清单，不扩大为父顾问权限。无业务身份、带首尾空格的源登录名也明确列入未导入清单。

## 哪些表会变

| V2 表 | 新增 | 存量修正 |
| --- | --- | --- |
| `account_service.base_client` | 缺失客户主档，来源 `MstClient` | 仅补空 `mobile/email`，不覆盖非空值，不改变 `updated_at` |
| `account_service.base_advisor` | 缺失顾问，来源 `MstBFEUser` | 不修改 |
| `account_service.base_client_prd` | 缺失产品账户，来源 `MstClntPrd2/3` | 身份主键和产品号一致时对齐 `date_close`，包括撤销错误关闭 |
| `account_service.rel_joint_acct` | 缺失联合关系，来源 `MstJointAcct`，要求两端产品账户存在 | 不删除或改写已有关系 |
| `auth_service.sys_user` | 缺失且身份可确定的登录账号 | 仅 `enabled/locked/failed_count` 收紧，不修改任何密码或登录身份字段 |
| `auth_service.ref_user_role` | 缺失的 CLIENT/ADVISOR 角色关联 | 不删除或替换已有角色 |

源字段超长、主键冲突及缺失依赖不截断、不猜测。影响本次登录主体或新增用户账户范围的错误标为 `BLOCKER`，整次不写入；当前模型不支持的历史身份及非登录主体业务异常保留为 `WARNING`。预检通过不等于异常清单为空。

## 账户范围

- 保留当前 V2 **同证件号 + 联合主账户**规则，不调整基金服务或网关权限实现。
- `ScopeDiff` 比较 V1 客户分支的直接/联合产品范围与 V2 当前规则的开放产品范围；V1 菜单/页面/团队/子顾问授权不会被当作 V2 全局权限迁移。它不是所有 V1 页面权限的完整复刻。
- `APPROVED_V2_SCOPE` 为已接受的规则差异；`DATA_DRIFT` 为在相同 V2 规则下仍有的数据差异。现有账号的数据差异会报告；影响本次新增账号的差异会阻止导入。已有 V2 人工修改的证件资料不被迁移覆盖。
- `MstUserLogin` 不用来创建 V2 登录账号。V1 部分账户下拉接口使用它过滤客户，和实际产品函数口径不同；本脚本不把这些差异直接判成越权。
- J02441、J00439 是联合账户编号，不自动创建同名登录；CKSun、T00304 等实际登录身份通过联合关系访问相应产品。

## 使用流程

先修改本目录 `db.ini` 中的 `[mssql]` 和 `[postgresql]` 配置，每节包含 `host`、`port`、`database`、`user`、`password`。MSSQL 源库必须是 `UnitTrust`，PostgreSQL 填实际生产目标库。`db.ini` 不在 Git 中，从仓库获取代码时需自行创建或安全复制该配置。

生产迁移前停止 V1/V2 相关数据变更，备份目标库；数据库时间应与 V1/V2 应用时区一致。本脚本用 V1 `GETDATE()` 作为一次运行的状态判断时间，是一次切换迁移，不是持续同步工具。提交后再次运行完整预检，核对报告，并做真实登录验收。

```powershell
# 在 login_users 文件夹中打开 PowerShell
python -m pip install -r requirements.txt
New-Item -ItemType Directory -Force .\reports
$loginMigrationStamp = Get-Date -Format "yyyyMMdd_HHmmss"

# 只读预检，可导出计划和全部账号审计
python migrate_login_users.py --result-xlsx ".\reports\$loginMigrationStamp-preflight.xlsx"

# 完整迁移：补缺失数据 + 修正存量 + 提交前验收
python migrate_login_users.py --apply --confirm-target "<PG_HOST>:<PG_PORT>/<PG_DATABASE>" --result-xlsx ".\reports\$loginMigrationStamp-result.xlsx"

# 执行后再次只读核对：待新增、待补角色、待更新应为 0
python migrate_login_users.py --result-xlsx ".\reports\$loginMigrationStamp-after.xlsx"
```

先核对预检报告，处理 `BLOCKER` 并确认 `WARNING`，再执行写入命令；将目标占位符替换为与 `db.ini` 一致的实际值。生产完整迁移不加 `--repair-only`，也不单独执行 `reconciliation.py`。

`--config` 可指定其他配置文件。`--report-json` 可额外保存预检审计。以上命令的报告和备份保存在本目录 `reports/` 中；相对输出路径以**控制台当前目录**为基准，也可指定绝对路径。输出父目录必须存在，所有输出文件均禁止覆盖。目标确认包含端口，旧的 `host/database` 写法不再接受。

## 事务、备份和报告

1. 只读预检与内存模拟，列出新增、更新、阻断项及迁移后的预计范围。
2. 提前为新增账号生成 BCrypt；随后锁定涉及的目标表，重新预检，避免在旧计划上写入。拿锁超时则退出，不自动重放写入。
3. 同一个 PostgreSQL 事务内修正存量、补业务依赖、补用户和角色。更新 SQL 同时校验旧值；身份或并发冲突立即回滚。
4. 提交前再次读取并计算计划，要求待写入记录为零、原有账号的登录身份和密码指纹完全不变、新增用户名集合一致。失败整次回滚。
5. 提交成功后输出 Excel 与提交回执。重复运行不会再产生同样新增或更新。

同一个输出名前缀会产生：

- `.backup.json`：写前准备状态、更新前后原值、新增业务键和用户名。**含用于回退的联系方式，保存在受控本地目录。** 不含密码；文件存在不代表已提交。
- `.pending.json`：已完成事务内验收、等待提交的结果。网络在 commit 时断开可能导致提交状态未知，必须查库核对；不能仅凭该文件认定成功或失败。
- `.committed.json`：客户端收到成功提交后保存的结果、审计和检查项；可据此恢复 Excel。
- `.xlsx`：`Summary`、六张新增表明细、`Exceptions`、`Changes`、`Accounts`、`MFA`、`ScopeDiff`、`Issues`、`Checks`、`PlannedInserts`。新增明细只列实际新增；更新页列字段前后值，联系方式脱敏。预检报告会明确标为只读计划，不计作实际新增；`PlannedInserts` 与计划计数单列，待创建用户标为 `NEW_PLANNED`。

数据库提交与 Excel 保存是两个步骤。若已提交但导出失败，控制台明确提示数据库已提交；根据回执恢复报告，不覆盖历史报告。脚本仅重试建立 TCP 连接，不自动重试事务或提交。

## 本次修正了原脚本什么问题

原脚本只补缺失主键，无法修复已迁入的关闭日期和现有账号状态；没有把联系方式缺失、同证件号范围变化纳入验收；身份冲突和不支持账号只跳过，缺少阻断分级；仅统计新增不足以说明实际登录可用性。

现在增加字段受限的存量补正、完整账号和范围审计、阻断分级、写前备份、并发保护、提交前幂等性与密码保持校验。数据或模型无法表达的情况仍明确报告，不把所有历史账号都描述为迁移后可直接登录。数据库行核对、单元测试以及真实登录验收是分别记录的步骤。
