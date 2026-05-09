"""
将 export_trn_client_available_holding.py 导出的 JSON 插入 PostgreSQL：
  transaction_service.trn_client_available_holding

业务字段（与当前 PG 表定义一致）：client_code, branch, fund_id, dividend_instruction,
payment_mode_code, portfolio_code, fund_sub_acc, unit, pending_sell_unit, average_nav,
m_average_nav, total_inv_unit, total_inv_amount, m_total_inv_amount；另插入 created_by、
created_ip；created_at 使用表默认值。

环境变量（必填）：
  PG_HOST
  PG_PORT（可选，默认 5432）
  PG_DATABASE
  PG_USER
  PG_PASSWORD

可选：
  PG_SCHEMA           默认 transaction_service
  JSON_FILE           指定 json_export 下某一文件；不填则取该目录下最新的 *trn_client_available_holding*.json
  CREATED_BY          默认 LEGACY_IMPORT
  TRUNCATE_BEFORE     设为 1/true 时先 TRUNCATE 目标表（仅空库/测试用）

  PG_MERGE_BUSINESS_KEY 默认 1：按业务五列合并重复持仓（不含 branch/dividend），数值列求和、pending 取一次
  PG_ON_CONFLICT      默认 nothing：INSERT 使用 ON CONFLICT (主键列) DO NOTHING，便于重跑；设为 fail 则不加 ON CONFLICT
  PG_ON_CONFLICT_COLUMNS  逗号分隔，覆盖 ON CONFLICT 的列顺序；须与库中唯一约束一致。不写则默认主键 7 列（pk_trn_client_available_holding）。若库存在 uq 五列唯一索引可设为 client_code,fund_id,payment_mode_code,fund_sub_acc,portfolio_code
  PG_CLAMP_NUMERIC    默认 1：按目标表各 numeric 列精度钳制数值，避免 22003（如 numeric(9,2) 上限 9999999.99）；长期建议把 PG 列宽改为与业务一致（如 numeric(18,2)）

依赖：pip install pg8000
"""

from __future__ import annotations

import glob
import json
import os
import sys
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

import pg8000

JSON_DIR = os.path.join(os.path.dirname(__file__), "json_export")

BATCH_SIZE = 500

DEFAULT_SCHEMA = "transaction_service"
TARGET_TABLE = "trn_client_available_holding"

# 新系统卖出冻结/扣减逻辑按这五列定位持仓，因此迁移时需保证该业务键最多一行。
UQ_KEY_FIELDS = (
    "client_code",
    "fund_id",
    "payment_mode_code",
    "fund_sub_acc",
    "portfolio_code",
)

MERGE_SUM_FIELDS = (
    "unit",
    "total_inv_unit",
    "total_inv_amount",
    "m_total_inv_amount",
)

# 与 PG 主键一致（你方 DDL：CONSTRAINT pk_trn_client_available_holding PRIMARY KEY (...)）
# 当前无单独 uq 五列索引时，ON CONFLICT 必须用此集合，否则会 42P10
PK_FIELDS = (
    "client_code",
    "branch",
    "fund_id",
    "payment_mode_code",
    "dividend_instruction",
    "portfolio_code",
    "fund_sub_acc",
)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_on_conflict_key_columns() -> Tuple[str, ...]:
    """ON CONFLICT 目标列，须对应库中唯一/主键索引。可用 PG_ON_CONFLICT_COLUMNS 覆盖。"""
    raw = _env("PG_ON_CONFLICT_COLUMNS")
    if raw:
        cols = tuple(c.strip() for c in raw.split(",") if c.strip())
        if not cols:
            print(
                "环境变量 PG_ON_CONFLICT_COLUMNS 无效（空列）",
                file=sys.stderr,
            )
            sys.exit(1)
        return cols
    return PK_FIELDS


def _require_env(name: str) -> str:
    v = _env(name)
    if not v:
        print(f"缺少环境变量: {name}", file=sys.stderr)
        sys.exit(1)
    return v


def get_pg_connection():
    return pg8000.connect(
        host=_require_env("PG_HOST"),
        port=int(_env("PG_PORT", "5432") or "5432"),
        database=_require_env("PG_DATABASE"),
        user=_require_env("PG_USER"),
        password=_require_env("PG_PASSWORD"),
    )


def pick_latest_json() -> str:
    pattern = os.path.join(JSON_DIR, "*trn_client_available_holding*.json")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not files:
        print(f"未找到 {pattern}", file=sys.stderr)
        sys.exit(1)
    return files[0]


def load_json(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_table_columns(cur, schema: str, table: str) -> Set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """,
        [schema, table],
    )
    return {row[0] for row in cur.fetchall()}


def load_numeric_max_abs(cur, schema: str, table: str) -> Dict[str, Decimal]:
    """各 numeric/decimal 列绝对值上限：10^(p-s) - 10^(-s)。无精度元数据则不限制。"""
    cur.execute(
        """
        SELECT column_name, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND udt_name = 'numeric'
          AND numeric_precision IS NOT NULL
        """,
        [schema, table],
    )
    out: Dict[str, Decimal] = {}
    for name, prec, scale in cur.fetchall():
        pr = int(prec)
        sc = int(scale) if scale is not None else 0
        out[str(name)] = Decimal(10) ** (pr - sc) - Decimal(10) ** (-sc)
    return out


def normalize_row(
    row: dict,
    pg_columns: Set[str],
    created_by: str,
    dropped: Set[str],
    numeric_max_abs: Optional[Dict[str, Decimal]],
    clamp_stats: Optional[Dict[str, int]],
) -> dict:
    out = dict(row)
    out["created_by"] = created_by
    out.setdefault("created_ip", "127.0.0.1")
    cleaned = {}
    for k, v in out.items():
        if k in pg_columns:
            cleaned[k] = v
        else:
            dropped.add(k)
    _coerce_pg_not_null_numerics(cleaned)
    if numeric_max_abs:
        _clamp_numeric_to_column_precision(
            cleaned, numeric_max_abs, clamp_stats
        )
    return cleaned


def _coerce_pg_not_null_numerics(row: dict) -> None:
    """显式 INSERT null 会绕过 PG DEFAULT；对常见非空列做回退。"""
    if row.get("pending_sell_unit") is None:
        row["pending_sell_unit"] = 0
    avg = row.get("average_nav")
    if avg is None:
        row["average_nav"] = 0
        avg = 0
    if row.get("m_average_nav") is None:
        row["m_average_nav"] = avg


def _clamp_numeric_to_column_precision(
    row: dict,
    max_abs: Dict[str, Decimal],
    clamp_stats: Optional[Dict[str, int]],
) -> None:
    """将超出 PG numeric(p,s) 范围的值钳到可存储的最大/最小值。"""
    for k, hi in max_abs.items():
        if k not in row or row[k] is None:
            continue
        try:
            d = Decimal(str(row[k]))
        except Exception:
            continue
        lo = -hi
        if d > hi:
            row[k] = float(hi)
            if clamp_stats is not None:
                clamp_stats["n"] = clamp_stats.get("n", 0) + 1
        elif d < lo:
            row[k] = float(lo)
            if clamp_stats is not None:
                clamp_stats["n"] = clamp_stats.get("n", 0) + 1


def _uq_key(row: dict) -> tuple:
    pc = row.get("portfolio_code")
    if pc is None:
        p = ""
    elif isinstance(pc, str):
        p = pc.strip()
    else:
        p = str(pc)
    return (
        row.get("client_code"),
        row.get("fund_id"),
        row.get("payment_mode_code"),
        row.get("fund_sub_acc"),
        p,
    )


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _sum_optional(values: List[object]) -> Optional[Decimal]:
    total = Decimal("0")
    seen = False
    for value in values:
        d = _to_decimal(value)
        if d is None:
            continue
        total += d
        seen = True
    return total if seen else None


def _max_optional(values: List[object]) -> Optional[Decimal]:
    nums = [d for d in (_to_decimal(v) for v in values) if d is not None]
    return max(nums) if nums else None


def _first_sorted_text(values: List[object], default: str) -> str:
    texts = sorted(
        {
            str(v).strip()
            for v in values
            if v is not None and str(v).strip()
        }
    )
    return texts[0] if texts else default


def _choose_dividend_instruction(values: List[object]) -> str:
    texts = {
        str(v).strip().upper()
        for v in values
        if v is not None and str(v).strip()
    }
    if "R" in texts:
        return "R"
    return sorted(texts)[0] if texts else "P"


def _safe_div(numerator, denominator) -> Optional[Decimal]:
    n = _to_decimal(numerator)
    d = _to_decimal(denominator)
    if n is None or d is None or d == 0:
        return None
    return n / d


def _recompute_average_nav(row: dict) -> None:
    avg = _safe_div(row.get("total_inv_amount"), row.get("total_inv_unit"))
    if avg is None:
        avg = _safe_div(row.get("total_inv_amount"), row.get("unit"))
    if avg is not None:
        row["average_nav"] = avg

    m_avg = _safe_div(row.get("m_total_inv_amount"), row.get("total_inv_unit"))
    if m_avg is None:
        m_avg = _safe_div(row.get("m_total_inv_amount"), row.get("unit"))
    if m_avg is not None:
        row["m_average_nav"] = m_avg


def merge_by_business_key(rows: List[dict]) -> Tuple[List[dict], int]:
    """同业务五维的持仓合并为一行，避免简单丢弃导致份额和成本缺失。"""
    grouped: Dict[tuple, List[dict]] = {}
    for r in rows:
        grouped.setdefault(_uq_key(r), []).append(r)

    out: List[dict] = []
    merged_extra = 0
    for group in grouped.values():
        if len(group) == 1:
            out.append(group[0])
            continue

        merged = dict(group[0])
        merged["branch"] = _first_sorted_text([r.get("branch") for r in group], "")
        merged["dividend_instruction"] = _choose_dividend_instruction(
            [r.get("dividend_instruction") for r in group]
        )
        for field in MERGE_SUM_FIELDS:
            merged[field] = _sum_optional([r.get(field) for r in group])

        # pending 来源已在导出时按 client/fund/payment/portfolio 汇总；旧 JSON 中同业务键多行会重复同一个 pending，取一次即可。
        pending = _max_optional([r.get("pending_sell_unit") for r in group])
        if pending is not None:
            merged["pending_sell_unit"] = pending
        _recompute_average_nav(merged)

        out.append(merged)
        merged_extra += len(group) - 1
    return out, merged_extra


def truncate_if_requested(cur, schema: str) -> None:
    if _env("TRUNCATE_BEFORE", "").lower() not in ("1", "true", "yes"):
        return
    cur.execute(
        f'TRUNCATE TABLE "{schema}"."{TARGET_TABLE}";'
    )
    print(f"  已 TRUNCATE {schema}.{TARGET_TABLE}")


def insert_batch(
    cur,
    schema: str,
    rows: List[dict],
    on_conflict_nothing: bool,
    on_conflict_columns: Tuple[str, ...],
) -> int:
    if not rows:
        return 0
    columns = sorted(rows[0].keys())
    col_str = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    conflict_target = ", ".join(f'"{c}"' for c in on_conflict_columns)
    suffix = ""
    if on_conflict_nothing:
        suffix = f" ON CONFLICT ({conflict_target}) DO NOTHING"
    sql = (
        f'INSERT INTO "{schema}"."{TARGET_TABLE}" ({col_str}) VALUES ({placeholders})'
        f"{suffix}"
    )
    n = 0
    for row in rows:
        values = [row.get(c) for c in columns]
        cur.execute(sql, values)
        rc = cur.rowcount
        if rc is not None and rc >= 0:
            n += rc
        else:
            n += 1
    return n


def main() -> None:
    schema = _env("PG_SCHEMA", DEFAULT_SCHEMA) or DEFAULT_SCHEMA
    created_by = _env("CREATED_BY", "LEGACY_IMPORT") or "LEGACY_IMPORT"

    path = _env("JSON_FILE")
    if path:
        if not os.path.isabs(path):
            path = os.path.join(JSON_DIR, path)
    else:
        path = pick_latest_json()

    if not os.path.isfile(path):
        print(f"文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"加载 {path} ...")
    raw_rows = load_json(path)
    print(f"  共 {len(raw_rows)} 条")

    merge_on = _env("PG_MERGE_BUSINESS_KEY", "1").lower() not in (
        "0",
        "false",
        "no",
    )
    if merge_on:
        raw_rows, n_merged = merge_by_business_key(raw_rows)
        if n_merged:
            print(
                f"  按业务五列合并：合并 {n_merged} 条重复持仓（数值列求和、pending 取一次）"
            )
        print(f"  合并后 {len(raw_rows)} 条")

    on_conflict_nothing = _env("PG_ON_CONFLICT", "nothing").lower() != "fail"
    conflict_cols = (
        resolve_on_conflict_key_columns() if on_conflict_nothing else ()
    )
    if on_conflict_nothing and conflict_cols:
        print(
            "  ON CONFLICT 键列 "
            f"({len(conflict_cols)} 列): {', '.join(conflict_cols)}"
        )

    if not raw_rows:
        print("无数据，退出。")
        return

    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            truncate_if_requested(cur, schema)
            pg_columns = get_table_columns(cur, schema, TARGET_TABLE)
            numeric_max: Optional[Dict[str, Decimal]] = None
            clamp_stats: Dict[str, int] = {}
            if _env("PG_CLAMP_NUMERIC", "1").lower() not in ("0", "false", "no"):
                numeric_max = load_numeric_max_abs(cur, schema, TARGET_TABLE)
                if numeric_max:
                    print(
                        f"  已加载 {len(numeric_max)} 个 numeric 列的钳制范围（PG_CLAMP_NUMERIC）"
                    )
            dropped: Set[str] = set()
            batch_buf: List[dict] = []
            total = 0
            for r in raw_rows:
                batch_buf.append(
                    normalize_row(
                        r,
                        pg_columns,
                        created_by,
                        dropped,
                        numeric_max,
                        clamp_stats,
                    )
                )
                if len(batch_buf) >= BATCH_SIZE:
                    total += insert_batch(
                        cur,
                        schema,
                        batch_buf,
                        on_conflict_nothing,
                        conflict_cols,
                    )
                    batch_buf.clear()
            if batch_buf:
                total += insert_batch(
                    cur,
                    schema,
                    batch_buf,
                    on_conflict_nothing,
                    conflict_cols,
                )

            if clamp_stats.get("n"):
                print(
                    f"  [提示] numeric 钳制：共 {clamp_stats['n']} 个字段值曾超出列精度（已裁到边界）。"
                    " 建议在库中扩大 numeric 精度后重新导。"
                )

            if dropped:
                sample = sorted(dropped)[:30]
                more = len(dropped) > 30
                print(
                    f"  [提示] 以下 JSON 键在目标表中不存在已忽略（示例）：{sample}"
                    + (" ..." if more else "")
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\n完成：写入 {total} 行到 {schema}.{TARGET_TABLE}")


if __name__ == "__main__":
    main()
