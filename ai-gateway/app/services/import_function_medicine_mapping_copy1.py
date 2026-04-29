"""导入 167 项目手册到 function_medicine_ai_mapping_copy1。

功能：
    读取 `docs/167项目手册.xlsx` 的 `转项目手册` sheet，
    按数据库既有字段映射写入 `function_medicine_ai_mapping_copy1`。

说明：
    1. 本脚本假设目标表已存在。
    2. 主键 `id` 使用稳定哈希生成，支持重复执行幂等更新。
    3. 默认使用 `ON DUPLICATE KEY UPDATE` 做增量同步，不删除历史行。
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pymysql

from app.core.mysql import build_business_mysql_conn_params
from app.utils.text_utils import normalize_text as _normalize_text

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS_FILE = _REPO_ROOT / "docs" / "167项目手册.xlsx"
_SOURCE_SHEET_NAME = "转项目手册"
_TARGET_TABLE = "function_medicine_ai_mapping_copy1"
_DEFAULT_STATUS = "active"


def _load_project_env_file() -> None:
    """加载 ai-gateway 根目录 `.env` 到进程环境。

    功能：
        脚本常被直接从任意路径执行，运行时工作目录不稳定。这里主动读取项目根 `.env`，
        保证 BUSINESS_MYSQL_* 一致生效，避免“同一脚本在不同目录下连不同库”的隐患。
    """

    env_path = _PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ.setdefault(key, value)


if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))
_load_project_env_file()

logger = logging.getLogger(__name__)


@dataclass
class ImportStats:
    """导入统计结果。"""

    source_rows: int = 0
    valid_rows: int = 0
    skipped_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    unchanged_rows: int = 0


def _normalize_int(value: Any) -> int | None:
    """安全解析整数，失败时返回 None。"""

    if value is None:
        return None
    try:
        if isinstance(value, float) and value != value:  # NaN
            return None
        return int(float(str(value)))
    except Exception:
        return None


def _normalize_price_text(value: Any) -> str:
    """将方案金规范为文本，避免浮点格式污染。

    功能：
        表结构 `price_text` 是 varchar。这里把 Excel 数字写成稳定文本（如 39800 而非 39800.0），
        保证同一条记录在重复导入时不会因为展示格式差异触发无意义更新。
    """

    if value is None:
        return ""
    try:
        numeric = float(str(value))
        if numeric != numeric:  # NaN
            return ""
        if numeric.is_integer():
            return str(int(numeric))
        return str(numeric)
    except Exception:
        return _normalize_text(value)


def _build_stable_id(
    *,
    source_sheet_name: str,
    source_row_no: int,
    serial_no: int | None,
    project_name: str,
    package_version: str,
) -> str:
    """生成稳定主键 ID。

    功能：
        业务手册会反复修订，重新导入必须可定位到同一行进行更新。这里以
        `sheet + row_no + serial_no + project_name + package_version` 生成稳定哈希，
        满足幂等 upsert，避免每次重跑都新增脏数据。
    """

    payload = f"{source_sheet_name}|{source_row_no}|{serial_no or ''}|{project_name}|{package_version}"
    digest = hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()
    return digest[:64]


def _ensure_table_exists(cursor: pymysql.cursors.Cursor, table_name: str) -> None:
    """校验目标表存在。"""

    cursor.execute(
        """
SELECT COUNT(1)
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = %s
""".strip(),
        (table_name,),
    )
    if int(cursor.fetchone()[0]) == 0:
        raise RuntimeError(f"目标表不存在: {table_name}")


def _read_source_rows() -> tuple[list[dict[str, Any]], ImportStats]:
    """读取并标准化 Excel 源数据。

    Returns:
        `(rows, stats)`：
        - rows: 可落库的标准化行
        - stats: 源数据规模与跳过统计

    Raises:
        FileNotFoundError: Excel 文件不存在时抛出
        ValueError: 指定 sheet 不存在时抛出

    Edge Cases:
        若某行缺少 `项目名称`，会跳过该行。因为项目名是推荐映射的核心锚点，
        空项目名写库会直接污染后续召回与安全过滤。
    """

    if not _DOCS_FILE.exists():
        raise FileNotFoundError(f"Excel 文件不存在: {_DOCS_FILE}")

    excel = pd.ExcelFile(_DOCS_FILE)
    if _SOURCE_SHEET_NAME not in excel.sheet_names:
        raise ValueError(f"sheet 不存在: {_SOURCE_SHEET_NAME}")

    df = pd.read_excel(_DOCS_FILE, sheet_name=_SOURCE_SHEET_NAME)
    stats = ImportStats(source_rows=len(df))
    rows: list[dict[str, Any]] = []

    # Excel 第一行是表头，因此 source_row_no 从 2 开始，便于人工回查原始行。
    for index, row in df.iterrows():
        source_row_no = int(index) + 2
        project_name = _normalize_text(row.get("项目名称"))
        if not project_name:
            stats.skipped_rows += 1
            continue

        serial_no = _normalize_int(row.get("序号"))
        system_name = _normalize_text(row.get("所属系统"))
        package_version = _normalize_text(row.get("版本/疗程"))
        normalized = {
            "id": _build_stable_id(
                source_sheet_name=_SOURCE_SHEET_NAME,
                source_row_no=source_row_no,
                serial_no=serial_no,
                project_name=project_name,
                package_version=package_version,
            ),
            "serial_no": serial_no,
            "system_name": system_name,
            "project_name": project_name,
            "package_version": package_version,
            "price_text": _normalize_price_text(row.get("方案金")),
            "core_effect": _normalize_text(row.get("核心功效")),
            "indications": _normalize_text(row.get("适应症")),
            "contraindications": _normalize_text(row.get("禁忌症(风险)")),
            "status": _DEFAULT_STATUS,
            "source_sheet_name": _SOURCE_SHEET_NAME,
            "source_row_no": source_row_no,
        }
        rows.append(normalized)

    stats.valid_rows = len(rows)
    return rows, stats


def import_project_manual(*, dry_run: bool = False, truncate: bool = False) -> ImportStats:
    """导入 `转项目手册` 到 `function_medicine_ai_mapping_copy1`。

    Args:
        dry_run: True 时仅解析与校验，不写数据库。
        truncate: True 时先清空目标表再导入（谨慎使用）。

    Returns:
        ImportStats: 导入统计。

    Raises:
        RuntimeError: 目标表不存在或数据库写入失败时抛出。

    Edge Cases:
        1. 幂等重跑：相同主键行会走 update，不会重复插入。
        2. 无业务变更：`ON DUPLICATE KEY UPDATE` 后 rowcount 可能为 0，计入 unchanged。
    """

    rows, stats = _read_source_rows()
    if dry_run:
        return stats

    conn = pymysql.connect(**build_business_mysql_conn_params())
    try:
        with conn.cursor() as cursor:
            _ensure_table_exists(cursor, _TARGET_TABLE)
            if truncate:
                # 仅在显式传参时清表，避免脚本默认行为破坏人工修订数据。
                cursor.execute(f"TRUNCATE TABLE {_TARGET_TABLE}")

            upsert_sql = f"""
INSERT INTO {_TARGET_TABLE} (
    id, serial_no, system_name, project_name, package_version,
    price_text, core_effect, indications, contraindications, status,
    source_sheet_name, source_row_no
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    serial_no = VALUES(serial_no),
    system_name = VALUES(system_name),
    project_name = VALUES(project_name),
    package_version = VALUES(package_version),
    price_text = VALUES(price_text),
    core_effect = VALUES(core_effect),
    indications = VALUES(indications),
    contraindications = VALUES(contraindications),
    status = VALUES(status),
    source_sheet_name = VALUES(source_sheet_name),
    source_row_no = VALUES(source_row_no),
    updated_at = CURRENT_TIMESTAMP
""".strip()

            for row in rows:
                cursor.execute(
                    upsert_sql,
                    (
                        row["id"],
                        row["serial_no"],
                        row["system_name"],
                        row["project_name"],
                        row["package_version"],
                        row["price_text"],
                        row["core_effect"],
                        row["indications"],
                        row["contraindications"],
                        row["status"],
                        row["source_sheet_name"],
                        row["source_row_no"],
                    ),
                )

                # PyMySQL rowcount 语义：
                # 1=insert，2=update，0=duplicate key但值未变。
                if cursor.rowcount == 1:
                    stats.inserted_rows += 1
                elif cursor.rowcount == 2:
                    stats.updated_rows += 1
                else:
                    stats.unchanged_rows += 1

        conn.commit()
        return stats
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description="导入 167 项目手册到 function_medicine_ai_mapping_copy1")
    parser.add_argument("--dry-run", action="store_true", help="只解析不写库")
    parser.add_argument("--truncate", action="store_true", help="导入前清空目标表（谨慎）")
    cli_args = parser.parse_args()

    result = import_project_manual(dry_run=cli_args.dry_run, truncate=cli_args.truncate)
    print(
        "导入完成: "
        f"source_rows={result.source_rows}, "
        f"valid_rows={result.valid_rows}, "
        f"skipped_rows={result.skipped_rows}, "
        f"inserted_rows={result.inserted_rows}, "
        f"updated_rows={result.updated_rows}, "
        f"unchanged_rows={result.unchanged_rows}"
    )
