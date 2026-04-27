"""
从 MSSQL UnitTrust 数据库读取以下表的数据，并导出为 JSON 文件：
  - MstClient
  - MstClient2
  - MstClntFBank
  - MstClntPrd2 / MstClntPrd3（字段相同，合并导出）
  - MstJointAcct

依赖：
  pip install pyodbc python-dotenv
"""

import json
import os
import re
from datetime import datetime, date
from decimal import Decimal

import pyodbc

# ── 数据库连接配置 ──────────────────────────────────────────────────────────────
DB_CONFIG = {
    "server": "10.1.6.177",
    "database": "UnitTrust",
    "username": "sa",
    "password": "Tongyu@123456",
    "driver": "SQL Server",
    "encrypt": "no",
    "trust_server_certificate": "yes",
}

# 输出目录（脚本同级目录下的 json_export 子目录）
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "json_export")


# ── 工具函数 ────────────────────────────────────────────────────────────────────

def get_connection() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        f"Encrypt={DB_CONFIG['encrypt']};"
        f"TrustServerCertificate={DB_CONFIG['trust_server_certificate']};"
    )
    return pyodbc.connect(conn_str)


def camel_to_snake(name: str) -> str:
    """将驼峰命名或大写字段名转换为 snake_case（已是 snake_case 的原样返回）。"""
    # 先处理连续大写缩写（如 APIKey → API_Key）
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    # MSSQL 全大写且无下划线时的已知列（避免通配 ...ID 误伤 UUID 等）
    if "_" not in s2 and s2.isupper() and len(s2) > 2:
        up = s2
        if up == "ECOSID":
            s2 = "ECOS_id"
        elif up == "EPFSS":
            s2 = "EPF_ss"
        else:
            for prefix, rest in (
                ("CRS", "MFIGIIN"),
                ("CRS", "FFIGIIN"),
                ("CRS", "RFIGIIN"),
                ("CRS", "CFIGIIN"),
            ):
                if up.startswith(prefix) and up[len(prefix) :] == rest:
                    s2 = f"{prefix}_{rest}"
                    break
    return s2.lower()


def serialize_value(val):
    """将不可直接 JSON 序列化的类型转换为可序列化格式。"""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        # bit/binary 字段
        return bool(int.from_bytes(val, "little")) if len(val) == 1 else val.hex()
    return val


def fetch_table(conn: pyodbc.Connection, table: str) -> list:
    """查询整张表，列名统一转为 snake_case，返回 dict 列表。"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM [{table}]")
    columns = [camel_to_snake(col[0]) for col in cursor.description]
    rows = []
    for row in cursor.fetchall():
        record = {col: serialize_value(val) for col, val in zip(columns, row)}
        rows.append(record)
    cursor.close()
    print(f"  [{table}] 共读取 {len(rows)} 条记录")
    return rows


def save_json(data: list, filename: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    prefix = datetime.now().strftime("%Y%m%d%H%M")
    timestamped_filename = f"{prefix}_{filename}"
    path = os.path.join(OUTPUT_DIR, timestamped_filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  已写入 {path}（{len(data)} 条）")


# ── 主流程 ──────────────────────────────────────────────────────────────────────

def main():
    print("连接 MSSQL 数据库...")
    conn = get_connection()

    try:
        # print("\n读取 MstClient ...")
        # mst_client = fetch_table(conn, "MstClient")
        # save_json(mst_client, "mst_client.json")
        #
        # print("\n读取 MstClient2 ...")
        # mst_client2 = fetch_table(conn, "MstClient2")
        # save_json(mst_client2, "mst_client2.json")
        #
        # print("\n读取 MstClntFBank ...")
        # mst_clnt_fbank = fetch_table(conn, "MstClntFBank")
        # save_json(mst_clnt_fbank, "mst_clnt_fbank.json")
        #
        # print("\n读取 MstClntPrd2 ...")
        # prd2 = fetch_table(conn, "MstClntPrd2")
        # print("\n读取 MstClntPrd3 ...")
        # prd3 = fetch_table(conn, "MstClntPrd3")
        # # MstClntPrd2 与 MstClntPrd3 字段相同，合并后加 source 字段区分来源
        # for r in prd2:
        #     r["_source"] = "MstClntPrd2"
        # for r in prd3:
        #     r["_source"] = "MstClntPrd3"
        # mst_clnt_prd = prd2 + prd3
        # save_json(mst_clnt_prd, "mst_clnt_prd.json")
        #
        # print("\n读取 MstJointAcct ...")
        # mst_joint_acct = fetch_table(conn, "MstJointAcct")
        # save_json(mst_joint_acct, "mst_joint_acct.json")

         print("\n读取 MstBFEUser ...")
         MstBFEUser = fetch_table(conn, "MstBFEUser")
         save_json(MstBFEUser, "MstBFEUser.json")

    finally:
        conn.close()

    print("\n全部导出完成！文件位于：", OUTPUT_DIR)


if __name__ == "__main__":
    main()
