# uw2-- Agent Guide

## 背景

`uw2--` 是 UWealth V2 迁移与调研资料仓库，主要承载老 UnitTrust 系统到新 Wealth 系统的数据迁移脚本、导出数据、问题记录和临时分析材料。

当前重点迁移来源为老项目 `UnitTrustMYWebAPI` / `UnitTrustMYWebApp` 及 MSSQL `UnitTrust` 数据库；目标通常是本地 PostgreSQL `wm` 库，对应新系统的 `auth_service`、`fund_service` 等 schema。

## 目录说明

- `uw2-migration/`：迁移脚本与迁移说明。
- `uw2-migration/unittrust/`：UnitTrust 迁移主目录，包含通用 MSSQL 导出、PostgreSQL 导入脚本和 `db.ini`。
- `uw2-migration/unittrust/ifa/`：IFA / Branch 组织数据迁移脚本、测试和 JSON 导出目录。
- `uw2-migration/unittrust/riskprofile/`：风险测评题库与历史答题记录迁移材料。
- `question/`、`op/`：问题记录、操作记录或临时分析材料。

## 数据迁移流程

迁移通常分三步：

1. 从老 UnitTrust MSSQL 读取源数据。
2. 转换为新系统需要的 JSON 或中间结构。
3. 写入本地 PostgreSQL，并执行校验。

以 IFA / Branch 为例：

```powershell
cd uw2-migration\unittrust
pip install -r requirements.txt
python ifa\ifa_branch_migration.py migrate
```

也可以分步执行：

```powershell
python ifa\ifa_branch_migration.py export
python ifa\ifa_branch_migration.py import --input-dir ifa\json_export\<batch_dir>
python ifa\ifa_branch_migration.py verify --input-dir ifa\json_export\<batch_dir>
```

## 数据库约定

- 默认读取 `uw2-migration/unittrust/db.ini`。
- 本地 PostgreSQL 默认端口为 `15432`。
- 本地开发目标库优先使用 `wm`，schema 通常为 `auth_service`。
- 执行迁移前确认目标表存在，例如 `auth_service.base_organization`、`auth_service.base_branch`。
- 如报 `relation "auth_service.base_organization" does not exist`，优先检查是否连到了未初始化的库，例如误连 `uw`。

## 开发注意事项

- 修改迁移逻辑前先看同目录测试，保持现有脚本的参数、JSON 输出和校验方式一致。
- 不要随意删除 `json_export/`、历史 SQL、问题记录或临时分析文件；这些常用于追溯迁移批次。
- 新增或修改迁移逻辑时，补充对应单元测试，并运行相关测试。
- 文档、迁移脚本和导出说明尽量写中文；表名、字段名、命令和枚举值保留英文。
- 不要把临时远程库地址、个人密码或一次性连接串写入提交内容；优先使用 `db.ini` 或命令行参数。

## 常用验证

```powershell
python -m unittest discover -s uw2-migration\unittrust\ifa -p "test_*.py"
```

迁移后至少确认：

- 导出记录数与预期一致。
- PostgreSQL 目标表存在且写入成功。
- `verify` 命令通过。
- 重复执行不会产生异常重复数据。
