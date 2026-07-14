# UWealth 数据迁移

`uw2-migration` 用于将老 UnitTrust MSSQL 数据迁移到 UWealth V2 PostgreSQL。

## 目录

- [`unittrust/eod/`](unittrust/eod/)：月末持仓和 Trust 快照迁移。
- [`unittrust/riskprofile/`](unittrust/riskprofile/)：风险测评题库和历史答题记录迁移。
- [`unittrust/ifa/`](unittrust/ifa/)：IFA 和 Branch 组织数据迁移。
- [`unittrust/db.ini`](unittrust/db.ini)：本地数据库连接配置。
- [`unittrust/requirements.txt`](unittrust/requirements.txt)：Python 依赖。

## 环境准备

在仓库根目录执行：

```powershell
cd uw2-migration\unittrust
pip install -r requirements.txt
```

迁移脚本默认读取 `unittrust/db.ini`。配置格式如下，密码不要提交到 Git：

```ini
[mssql]
driver = SQL Server
server = <host>
database = UnitTrust
user = <username>
password = <password>

[postgresql]
host = 127.0.0.1
port = 15432
database = wm
user = wealth
password = <password>
```

环境变量优先于 `db.ini`，支持：

- MSSQL：`MSSQL_DRIVER`、`MSSQL_SERVER`、`MSSQL_DATABASE`、`MSSQL_USER`、`MSSQL_PASSWORD`
- PostgreSQL：`PG_HOST`、`PG_PORT`、`PG_DATABASE`、`PG_USER`、`PG_PASSWORD`

## EOD 快照迁移

脚本位置：`unittrust/eod/migrate_eod_tables.py`。

源表和目标表：

| 源表 | PostgreSQL 目标表 |
|---|---|
| `dbo.TrnClientHoldingEOD` | `eod_service.trn_client_holding_eod` |
| `dbo.TrnTrustEOD` | `eod_service.trn_trust_eod` |

目标表必须先由 Fund Service Flyway migration 创建。写入使用组合主键 upsert，同一日期可以重复执行。

### 查看参数

```powershell
python eod\migrate_eod_tables.py --help
```

`--to-date` 是不包含当天的上界。例如迁移 `2026-03-31` 时，上界必须传 `2026-04-01`。

### 迁移前统计

只统计源库，不写 PostgreSQL：

```powershell
python eod\migrate_eod_tables.py `
  --from-date 2026-03-31 `
  --to-date 2026-04-01 `
  --count-only
```

### 迁移单个月末

同时迁移 Holding 和 Trust：

```powershell
python eod\migrate_eod_tables.py `
  --from-date 2026-03-31 `
  --to-date 2026-04-01 `
  --table all `
  --batch-size 1000
```

只迁移单张表时，将 `--table all` 改为 `--table holding` 或 `--table trust`。

### 批量迁移多个月末

Monthly AUA 只使用自然月最后一天的快照。以下命令逐月迁移 `2025-08-31` 至 `2026-03-31`，不会导入中间的每日数据：

```powershell
$month = [datetime]'2025-08-01'
$lastMonth = [datetime]'2026-03-01'

while ($month -le $lastMonth) {
    $monthEnd = $month.AddMonths(1).AddDays(-1)
    $nextDay = $monthEnd.AddDays(1)

    python eod\migrate_eod_tables.py `
      --from-date $($monthEnd.ToString('yyyy-MM-dd')) `
      --to-date $($nextDay.ToString('yyyy-MM-dd')) `
      --table all `
      --batch-size 1000

    if ($LASTEXITCODE -ne 0) {
        throw "EOD migration failed for $($monthEnd.ToString('yyyy-MM-dd'))"
    }
    $month = $month.AddMonths(1)
}
```

不要直接用 `--from-date 2025-08-01 --to-date 2026-04-01` 代替上述循环；该写法会迁移范围内所有 EOD 日期，而不只是月末。

### 指定本地 PostgreSQL

当 `db.ini` 指向其他环境时，可仅为当前 PowerShell 会话覆盖目标库：

```powershell
$env:PG_HOST = '127.0.0.1'
$env:PG_PORT = '15432'
$env:PG_DATABASE = 'wm'
$env:PG_USER = 'wealth'
$env:PG_PASSWORD = '<local-password>'
```

设置后再执行统计或迁移命令。若出现 `relation "eod_service.trn_client_holding_eod" does not exist`，应先确认目标数据库和 Fund Service Flyway migration，不要在错误数据库中手工建表。

### 测试

```powershell
python -m unittest discover -s eod -p "test_*.py" -v
python -m py_compile eod\migrate_eod_tables.py
```

### 迁移后验证

确认每个月两张表都有快照，并核对行数：

```sql
SELECT 'holding' AS source,
       holding_date::date AS snapshot_date,
       COUNT(*) AS row_count
FROM eod_service.trn_client_holding_eod
GROUP BY holding_date::date
UNION ALL
SELECT 'trust',
       trust_date::date,
       COUNT(*)
FROM eod_service.trn_trust_eod
GROUP BY trust_date::date
ORDER BY snapshot_date, source;
```

验证要求：

- 源表和目标表的同日行数一致。
- 快照日期均为自然月最后一天。
- 重复执行后行数不增加。
- Advisor Dashboard 的 Monthly AUA 月份与迁移月份一致，并遵守最近 12 个完整月份的查询范围。

## Risk Profile

目录：[`unittrust/riskprofile/`](unittrust/riskprofile/)

- 题库通过初始化 SQL 写入。
- 历史答题记录通过迁移脚本导入。

## IFA 和 Branch

目录：[`unittrust/ifa/`](unittrust/ifa/)

```powershell
cd uw2-migration\unittrust
python ifa\ifa_branch_migration.py migrate
```
