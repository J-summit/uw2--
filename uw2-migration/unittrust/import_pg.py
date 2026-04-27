"""
读取 export_mssql.py 导出的 JSON 文件，将数据插入到 PostgreSQL 数据库。

目标库：
  host=10.1.6.178  port=15432  database=wm  user=wealth  password=wealth@123

对应目标表（需事先在 PG 中建好）：
  base_client        ← mst_client.json
  base_client_detail ← mst_client2.json
  base_client_fbank  ← mst_clnt_fbank.json
  base_client_prd    ← mst_clnt_prd.json   （合并 MstClntPrd2/3，含 _source 列）
  rel_joint_acct     ← mst_joint_acct.json

字段映射规则：
  - MSSQL 侧字段已由 export_mssql.py 统一转为 snake_case（camel→snake、全大写→全小写+下划线）
  - 导入脚本直接使用 JSON key 作为 PG 列名，无需二次映射

依赖：
  pip install pg8000
"""

import json
import os
import sys
from typing import Dict, List, Set

import pg8000
import pg8000.native

# ── 数据库连接配置 ──────────────────────────────────────────────────────────────
PG_CONFIG = {
    "host": "10.1.6.178",
    "port": 15432,
    "database": "wm",
    "user": "wealth",
    "password": "wealth@123",
}

# 目标 schema
PG_SCHEMA = "account_service"

# JSON 文件目录（与 export_mssql.py 输出目录一致）
JSON_DIR = os.path.join(os.path.dirname(__file__), "json_export")

# 批量写入每批大小
BATCH_SIZE = 500

# JSON 字段名（历史 export 或 MSSQL 全大写缩写）→ PG 实际列名；与 export_mssql.camel_to_snake 对齐后可逐步清空
TABLE_JSON_TO_PG: Dict[str, Dict[str, str]] = {
    "base_client_detail": {
        "ecosid": "ecos_id",
        "epfss": "epf_ss",
        "crsmfigiin": "crs_mfigiin",
        "crsffigiin": "crs_ffigiin",
        "crsrfigiin": "crs_rfigiin",
        "crscfigiin": "crs_cfigiin",
    },
}


# ── 工具函数 ────────────────────────────────────────────────────────────────────

def get_pg_connection() -> pg8000.dbapi.Connection:
    return pg8000.connect(
        host=PG_CONFIG["host"],
        port=PG_CONFIG["port"],
        database=PG_CONFIG["database"],
        user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
    )


def load_json(filename: str) -> List[dict]:
    path = os.path.join(JSON_DIR, filename)
    if not os.path.exists(path):
        print(f"  [警告] 文件不存在，跳过：{path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  已加载 {path}（{len(data)} 条）")
    return data


def get_bit_columns(cur, table_name: str) -> set:
    """查询目标表中数据类型为 bit/varbit 的列名集合。"""
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name   = %s
          AND data_type IN ('bit', 'bit varying')
        """,
        [PG_SCHEMA, table_name],
    )
    return {row[0] for row in cur.fetchall()}


def get_table_columns(cur, table_name: str) -> Set[str]:
    """目标表全部列名（小写比较由 PG 返回；一般已为 snake_case）。"""
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """,
        [PG_SCHEMA, table_name],
    )
    return {row[0] for row in cur.fetchall()}


def normalize_row_for_pg(
    row: dict,
    json_to_pg: Dict[str, str],
    pg_columns: Set[str],
    dropped_keys: Set[str],
) -> dict:
    """别名映射后仅保留 PG 中存在的列；收集被丢弃的 JSON 键便于一次性告警。"""
    out: dict = {}
    for k, v in row.items():
        col = json_to_pg.get(k, k)
        if col in pg_columns:
            out[col] = v
        else:
            dropped_keys.add(k)
    return out


def coerce_value(val, col: str, bit_cols: Set):
    """将 Python bool 在 bit/varbit 列上转换为 '1'/'0' 字符串。"""
    if col in bit_cols and isinstance(val, bool):
        return '1' if val else '0'
    return val


def insert_batch(
    cur,
    table_name: str,
    rows: List[dict],
    bit_cols: Set,
    conflict_action: str = "DO NOTHING",
) -> int:
    """批量插入，返回实际写入行数。"""
    if not rows:
        return 0

    columns = sorted(rows[0].keys())
    col_str = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))

    sql = (
        f'INSERT INTO {PG_SCHEMA}.{table_name} ({col_str}) '
        f'VALUES ({placeholders}) ON CONFLICT {conflict_action}'
    )
    for row in rows:
        values = [coerce_value(row.get(c), c, bit_cols) for c in columns]
        cur.execute(sql, values)
    return len(rows)


def import_table(
    conn: pg8000.dbapi.Connection,
    table_name: str,
    json_file: str,
) -> None:
    print(f"\n导入 {table_name} ← {json_file} ...")
    rows = load_json(json_file)
    if not rows:
        return

    with conn.cursor() as cur:
        bit_cols = get_bit_columns(cur, table_name)
        pg_columns = get_table_columns(cur, table_name)
        json_to_pg = TABLE_JSON_TO_PG.get(table_name, {})
        dropped: Set[str] = set()
        if bit_cols:
            print(f"  检测到 bit/varbit 列：{bit_cols}")
        total = 0
        for i in range(0, len(rows), BATCH_SIZE):
            raw = rows[i : i + BATCH_SIZE]
            batch = [
                normalize_row_for_pg(r, json_to_pg, pg_columns, dropped)
                for r in raw
            ]
            if not batch:
                continue
            total += insert_batch(cur, table_name, batch, bit_cols)
        if dropped:
            sample = sorted(dropped)[:20]
            more = f" 等共 {len(dropped)} 个" if len(dropped) > 20 else ""
            print(
                f"  [提示] 以下 JSON 字段在表 {PG_SCHEMA}.{table_name} 中无对应列，已忽略："
                f"{sample}{more}"
            )
        conn.commit()
    print(f"  {table_name}: 共插入 {total} 条记录")


# ── 主流程 ──────────────────────────────────────────────────────────────────────

IMPORT_PLAN = [
    # ("base_client",        "mst_client.json"),
    # ("base_client_detail", "mst_client2.json"),
    # ("base_client_fbank",  "mst_clnt_fbank.json"),
     ("base_client_prd",    "mst_clnt_prd.json"),
    # ("rel_joint_acct",     "mst_joint_acct.json"),

    # ("base_advisor",     "202604141352_MstBFEUser.json"),

]


def main() -> None:
    print("连接 PostgreSQL 数据库...")
    try:
        conn = get_pg_connection()
    except Exception as e:
        print(f"连接失败：{e}", file=sys.stderr)
        sys.exit(1)

    try:
        for table_name, json_file in IMPORT_PLAN:
            import_table(conn, table_name, json_file)
    except Exception as e:
        conn.rollback()
        print(f"\n发生错误，已回滚：{e}", file=sys.stderr)
        raise
    finally:
        conn.close()

    print("\n全部导入完成！")


if __name__ == "__main__":
    main()
