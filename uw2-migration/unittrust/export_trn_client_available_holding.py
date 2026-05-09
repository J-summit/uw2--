"""
从 MSSQL UnitTrust 导出 TrnClientAvailableHolding，并计算 pending_sell_unit（与线上一致）：
  - 汇总：dbo.fn_UtGetPendingRdptTrans(1)
  - 分组：client_code + fund_id + payment_mode_code + portfolio_key
  - 左连到持仓行，无匹配则 pending_sell_unit = 0
  - 持仓先按新系统业务五维聚合：client_code + fund_id + payment_mode_code + fund_sub_acc + portfolio_code

输出：json_export 目录下带时间戳的 trn_client_available_holding_*.json

环境变量（必填）：
  MSSQL_SERVER   例：10.1.6.177
  MSSQL_DATABASE 例：UnitTrust
  MSSQL_USER
  MSSQL_PASSWORD

可选：
  MSSQL_DRIVER   默认 SQL Server；需换驱动时自行设置（名称须与「ODBC 数据源管理器」或 pyodbc.drivers() 中一致）
  MSSQL_ENCRYPT  仅推荐用于 ODBC Driver xx for SQL Server；旧驱动默认不附带此项
  MSSQL_TRUST_SERVER_CERTIFICATE 同上
  MSSQL_LOGIN_TIMEOUT  连接超时秒数，默认 30

  CAP_PENDING_TO_UNIT  设为 1/true 时，pending_sell_unit = min(pending, unit)

导出列与 PG 表 transaction_service.trn_client_available_holding 一致（仅业务字段，不含 created_*）：
  client_code, branch, fund_id, dividend_instruction, payment_mode_code, portfolio_code, fund_sub_acc,
  unit, pending_sell_unit, average_nav, m_average_nav, total_inv_unit, total_inv_amount, m_total_inv_amount

依赖：pip install pyodbc
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator, List

import pyodbc

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "json_export")

EXPORT_SQL = """
WITH pending_norm AS (
    SELECT
        client_code,
        fund_id,
        payment_mode_code,
        CASE
            WHEN portfolio_code IS NULL THEN N''
            WHEN LTRIM(RTRIM(portfolio_code)) = N'' THEN N''
            ELSE LTRIM(RTRIM(portfolio_code))
        END AS portfolio_key,
        unit
    FROM dbo.fn_UtGetPendingRdptTrans(1)
),
pending_agg AS (
    SELECT
        client_code,
        fund_id,
        payment_mode_code,
        portfolio_key,
        SUM(unit) AS pending_sell_unit
    FROM pending_norm
    GROUP BY
        client_code,
        fund_id,
        payment_mode_code,
        portfolio_key
),
holding_norm AS (
    SELECT
        LEFT(COALESCE(LTRIM(RTRIM(CAST(h.client_code AS NVARCHAR(40)))), N''), 20) AS client_code,
        LEFT(COALESCE(LTRIM(RTRIM(CAST(h.branch AS NVARCHAR(20)))), N''), 3) AS branch,
        LEFT(COALESCE(LTRIM(RTRIM(CAST(h.fund_id AS NVARCHAR(40)))), N''), 20) AS fund_id,
        LEFT(COALESCE(LTRIM(RTRIM(CAST(h.dividend_instruction AS NVARCHAR(20)))), N'P'), 8) AS dividend_instruction,
        LEFT(COALESCE(LTRIM(RTRIM(CAST(h.payment_mode_code AS NVARCHAR(20)))), N''), 10) AS payment_mode_code,
        LEFT(
            CASE
                WHEN h.portfolio_code IS NULL THEN N''
                WHEN LTRIM(RTRIM(h.portfolio_code)) = N'' THEN N''
                ELSE LTRIM(RTRIM(h.portfolio_code))
            END,
            20
        ) AS portfolio_code,
        LEFT(COALESCE(NULLIF(LTRIM(RTRIM(h.fund_sub_acc)), N''), N'N'), 10) AS fund_sub_acc,
        h.unit,
        h.average_nav,
        h.m_average_nav,
        h.total_inv_unit,
        h.total_inv_amount,
        h.m_total_inv_amount,
        CASE
            WHEN h.portfolio_code IS NULL THEN N''
            WHEN LTRIM(RTRIM(h.portfolio_code)) = N'' THEN N''
            ELSE LTRIM(RTRIM(h.portfolio_code))
        END AS portfolio_key
    FROM dbo.TrnClientAvailableHolding AS h
),
holding_grouped AS (
    SELECT
        client_code,
        MIN(branch) AS branch,
        fund_id,
        CASE
            WHEN SUM(CASE WHEN dividend_instruction = N'R' THEN 1 ELSE 0 END) > 0 THEN N'R'
            ELSE MIN(dividend_instruction)
        END AS dividend_instruction,
        payment_mode_code,
        portfolio_code,
        fund_sub_acc,
        portfolio_key,
        SUM(unit) AS unit,
        SUM(total_inv_unit) AS total_inv_unit,
        SUM(total_inv_amount) AS total_inv_amount,
        SUM(m_total_inv_amount) AS m_total_inv_amount,
        SUM(CASE WHEN average_nav IS NULL OR unit IS NULL THEN 0 ELSE average_nav * unit END) AS average_nav_weighted_sum,
        SUM(CASE WHEN average_nav IS NULL OR unit IS NULL THEN 0 ELSE unit END) AS average_nav_weight_unit,
        SUM(CASE WHEN m_average_nav IS NULL OR unit IS NULL THEN 0 ELSE m_average_nav * unit END) AS m_average_nav_weighted_sum,
        SUM(CASE WHEN m_average_nav IS NULL OR unit IS NULL THEN 0 ELSE unit END) AS m_average_nav_weight_unit,
        COUNT(1) AS source_row_count
    FROM holding_norm
    GROUP BY
        client_code,
        fund_id,
        payment_mode_code,
        fund_sub_acc,
        portfolio_code,
        portfolio_key
)
SELECT
    hg.client_code,
    hg.branch,
    hg.fund_id,
    hg.dividend_instruction,
    hg.payment_mode_code,
    hg.portfolio_code,
    hg.fund_sub_acc,
    hg.unit,
    CAST(ISNULL(pa.pending_sell_unit, 0) AS DECIMAL(18, 4)) AS pending_sell_unit,
    CAST(
        CASE
            WHEN ISNULL(hg.total_inv_unit, 0) <> 0 AND hg.total_inv_amount IS NOT NULL
                THEN hg.total_inv_amount / NULLIF(hg.total_inv_unit, 0)
            WHEN hg.average_nav_weight_unit <> 0
                THEN hg.average_nav_weighted_sum / NULLIF(hg.average_nav_weight_unit, 0)
            ELSE NULL
        END AS DECIMAL(18, 6)
    ) AS average_nav,
    CAST(
        CASE
            WHEN ISNULL(hg.total_inv_unit, 0) <> 0 AND hg.m_total_inv_amount IS NOT NULL
                THEN hg.m_total_inv_amount / NULLIF(hg.total_inv_unit, 0)
            WHEN hg.m_average_nav_weight_unit <> 0
                THEN hg.m_average_nav_weighted_sum / NULLIF(hg.m_average_nav_weight_unit, 0)
            ELSE NULL
        END AS DECIMAL(18, 6)
    ) AS m_average_nav,
    hg.total_inv_unit,
    hg.total_inv_amount,
    hg.m_total_inv_amount
FROM holding_grouped AS hg
LEFT JOIN pending_agg AS pa
    ON pa.client_code = hg.client_code
   AND pa.fund_id = hg.fund_id
   AND pa.payment_mode_code = hg.payment_mode_code
   AND pa.portfolio_key = hg.portfolio_key
ORDER BY
    hg.client_code,
    hg.fund_id,
    hg.payment_mode_code,
    hg.fund_sub_acc,
    hg.portfolio_code
"""


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"缺少环境变量: {name}", file=sys.stderr)
        sys.exit(1)
    return v


DEFAULT_ODBC_DRIVER = "SQL Server"


def _pick_odbc_driver() -> str:
    """未设置 MSSQL_DRIVER 时使用默认驱动；否则完全按环境变量指定的名称。"""
    explicit = os.environ.get("MSSQL_DRIVER", "").strip()
    return explicit if explicit else DEFAULT_ODBC_DRIVER


def _use_modern_sql_driver(driver: str) -> bool:
    """Microsoft ODBC Driver 11+ for SQL Server 支持 Encrypt=/TrustServerCertificate=。旧版 Native Client / SQL Server 常不必写。"""
    d = driver.strip()
    return d.startswith("ODBC Driver") and "SQL Server" in d


def build_connection_string() -> str:
    server = _require_env("MSSQL_SERVER")
    database = _require_env("MSSQL_DATABASE")
    user = _require_env("MSSQL_USER")
    password = _require_env("MSSQL_PASSWORD")
    driver = _pick_odbc_driver()
    login_timeout = os.environ.get("MSSQL_LOGIN_TIMEOUT", "30").strip() or "30"
    parts = [
        f"DRIVER={{{driver}}};",
        f"SERVER={server};",
        f"DATABASE={database};",
        f"UID={user};",
        f"PWD={password};",
        f"LoginTimeout={login_timeout};",
    ]
    if _use_modern_sql_driver(driver):
        encrypt = os.environ.get("MSSQL_ENCRYPT", "yes").strip()
        trust = os.environ.get("MSSQL_TRUST_SERVER_CERTIFICATE", "yes").strip()
        parts.append(f"Encrypt={encrypt};")
        parts.append(f"TrustServerCertificate={trust};")
    return "".join(parts)


def _print_driver_help() -> None:
    print("本机已安装的 ODBC 驱动：", file=sys.stderr)
    for d in pyodbc.drivers():
        print(f"  - {d}", file=sys.stderr)
    print(
        "\n默认使用 DRIVER={SQL Server}；若 IM002，请指定与本机列表一致的名称，例如：",
        file=sys.stderr,
    )
    print("  $env:MSSQL_DRIVER='ODBC Driver 18 for SQL Server'", file=sys.stderr)
    print("  $env:MSSQL_DRIVER='SQL Server Native Client 10.0'", file=sys.stderr)


def _print_connectivity_hint() -> None:
    print(
        "\n[连接失败 08001 / 10054] 常见原因：网络不可达、端口未开放、实例名或端口写错，"
        "或服务端要求加密/TLS 而当前 ODBC 握手被拒后强制断连。\n"
        "建议检查：\n"
        "  · MSSQL_SERVER：命名实例用 主机\\实例 ；指定端口可用  tcp:IP,1433  或  IP,1433\n"
        "  · VPN、防火墙、SQL Server 是否允许远程 TCP\n"
        "  · 安装 Microsoft ODBC Driver 17/18 for SQL Server，并设置：\n"
        "      $env:MSSQL_DRIVER='ODBC Driver 18 for SQL Server'\n"
        "      $env:MSSQL_ENCRYPT='optional'   # 或 yes / no，按服务器策略\n"
        "      $env:MSSQL_TRUST_SERVER_CERTIFICATE='yes'\n"
        "  · 增大等待： $env:MSSQL_LOGIN_TIMEOUT='60'\n",
        file=sys.stderr,
    )


def serialize_value(val: Any) -> Any:
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        return bool(int.from_bytes(val, "little")) if len(val) == 1 else val.hex()
    return val


def snake_label(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_")


def _truthy(s: str) -> bool:
    return s.strip().lower() in ("1", "true", "yes", "y")


def fetch_holding_rows(conn: pyodbc.Connection) -> Iterator[dict]:
    cap = _truthy(os.environ.get("CAP_PENDING_TO_UNIT", ""))
    cur = conn.cursor()
    cur.execute(EXPORT_SQL)
    cols = [snake_label(c[0]) for c in cur.description]
    for row in cur.fetchall():
        rec = {cols[i]: serialize_value(row[i]) for i in range(len(cols))}
        if cap and rec.get("unit") is not None and rec.get("pending_sell_unit") is not None:
            try:
                u = float(rec["unit"])
                p = float(rec["pending_sell_unit"])
                rec["pending_sell_unit"] = min(p, u)
            except (TypeError, ValueError):
                pass
        yield rec
    cur.close()


def save_json(rows: List[dict], base_name: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    prefix = datetime.now().strftime("%Y%m%d%H%M")
    filename = f"{prefix}_{base_name}"
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return path


def main() -> None:
    drv = _pick_odbc_driver()
    print(f"使用 ODBC 驱动: {drv}")
    conn_str = build_connection_string()
    print("连接 MSSQL ...")
    login_s = int(os.environ.get("MSSQL_LOGIN_TIMEOUT", "30") or "30")
    try:
        conn = pyodbc.connect(conn_str, timeout=login_s)
    except pyodbc.Error as e:
        err = str(e)
        if "IM002" in err:
            _print_driver_help()
        if "08001" in err or "10054" in err or "HYT00" in err:
            _print_connectivity_hint()
        raise
    try:
        rows = list(fetch_holding_rows(conn))
    finally:
        conn.close()

    path = save_json(rows, "trn_client_available_holding.json")
    print(f"已导出 {len(rows)} 条 → {path}")


if __name__ == "__main__":
    main()
