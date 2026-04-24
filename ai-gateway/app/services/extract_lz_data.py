"""离线导入丽滋关系拆分 Excel 到业务 MySQL（路径表 + 医生终检映射表）。

功能：
    读取 docs 下的三份结构化关系 Excel，将数据写入：
    - lz_clinical_pathway
    - lz_physicalexam_node
    - lz_treatment_node
    同时读取医生终检意见映射表，写入：
    - lz_doctor_conclusion_exam_mapping

说明：
    该脚本按“数据库已建表”前提运行，不再创建业务表。
    若检测/干预表缺少 `suitable_sex` 字段，会自动补列后再写入 male/female/all。
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

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_project_env_file() -> None:
    """加载 ai-gateway 根目录 `.env` 到进程环境。

    功能：
        脚本可能从任意目录直接执行，`pydantic` 默认只读当前工作目录 `.env`。
        这里主动加载项目根 `.env`，确保 BUSINESS_MYSQL_* 在脚本模式下稳定可用。
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

from app.core.mysql import build_business_mysql_conn_params

logger = logging.getLogger(__name__)

_DOCS_DIR = _REPO_ROOT / "docs"
_EXCEL_FILES = [
    "慢病诊疗_关系拆分结果_最终版.xlsx",
    "慢病24_8张关系表结果.xlsx",
    "功能养护_关系拆分结果.xlsx",
]
_DOCTOR_MAPPING_FILE = "医生终检意见映射表.xlsx"

_EXAM_KEYWORDS = ("体检", "检测", "质谱")
_TREATMENT_KEYWORDS = ("优选", "备选", "慢养", "养护", "干预", "项目")


@dataclass
class ImportStats:
    """导入统计。"""

    source_rows: int = 0
    pathway_inserted: int = 0
    pathway_skipped: int = 0
    exam_inserted: int = 0
    exam_skipped: int = 0
    treatment_inserted: int = 0
    treatment_skipped: int = 0
    mapping_source_rows: int = 0
    mapping_inserted: int = 0
    mapping_skipped: int = 0


def _normalize_text(value: Any) -> str:
    """标准化文本并过滤空值。"""

    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def _detect_suitable_sex(project_name: str) -> str:
    """按项目文本判定适用性别。

    规则：
        - 仅命中“男” -> male
        - 仅命中“女” -> female
        - 其他 -> all
    """

    if "男" in project_name and "女" not in project_name:
        return "male"
    if "女" in project_name and "男" not in project_name:
        return "female"
    return "all"


def _infer_source_sheet(file_name: str) -> str:
    """把文件名映射成业务来源标签。"""

    if "慢病24" in file_name:
        return "慢病24"
    if "功能养护" in file_name:
        return "功能养护"
    if "慢病诊疗" in file_name:
        return "慢病诊疗"
    return file_name.replace(".xlsx", "")


def _infer_trigger_type(first_column_name: str, trigger_name: str) -> str:
    """根据第一列语义推断触发类型。"""

    probe = f"{first_column_name}|{trigger_name}"
    if "病例" in probe or "症状" in probe:
        return "SYMPTOM"
    if "科室" in probe or "部门" in probe or "门诊" in probe:
        return "DEPARTMENT"
    return "DISEASE"


def _classify_relation(second_column_name: str) -> str:
    """按第二列列名将关系归类到检测或干预。"""

    name = second_column_name.lower()
    if any(keyword in name for keyword in _EXAM_KEYWORDS):
        return "exam"
    if any(keyword in name for keyword in _TREATMENT_KEYWORDS):
        return "treatment"
    # 兜底策略：未知列按干预处理，避免有效数据被丢弃。
    return "treatment"


def _derive_exam_type(second_col: str) -> str:
    """根据第二列名称推断检测类型。"""

    return "FUNCTIONAL" if "质谱" in second_col.lower() else "ROUTINE"


def _derive_priority_level(second_col: str) -> str:
    """根据第二列名称推断干预优先级。"""

    lowered = second_col.lower()
    if "优选" in lowered:
        return "PREFERRED"
    if "备选" in lowered:
        return "ALTERNATIVE"
    if "慢养" in lowered or "养护" in lowered:
        return "MAINTENANCE"
    return "ALTERNATIVE"


def _stable_pathway_id(source_sheet: str, trigger_name: str) -> str:
    """按来源+触发词生成稳定 pathway_id。"""

    digest = hashlib.md5(f"{source_sheet}|{trigger_name}".encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _iter_excel_rows() -> list[dict[str, str]]:
    """读取三份 Excel 全部 sheet 并输出统一行结构。"""

    rows: list[dict[str, str]] = []
    for file_name in _EXCEL_FILES:
        file_path = _DOCS_DIR / file_name
        if not file_path.exists():
            logger.warning("Excel 文件不存在，跳过: %s", file_path)
            continue

        excel = pd.ExcelFile(file_path)
        source_sheet = _infer_source_sheet(file_name)
        for sheet_name in excel.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            if df.empty or len(df.columns) < 2:
                continue

            first_col = _normalize_text(df.columns[0])
            second_col = _normalize_text(df.columns[1])
            relation_type = _classify_relation(second_col)

            for _, item in df.iterrows():
                trigger_name = _normalize_text(item.iloc[0])
                project_name = _normalize_text(item.iloc[1])
                if not trigger_name or not project_name:
                    continue
                rows.append(
                    {
                        "source_sheet": source_sheet,
                        "sheet_name": sheet_name,
                        "first_col": first_col,
                        "second_col": second_col,
                        "relation_type": relation_type,
                        "trigger_name": trigger_name,
                        "trigger_type": _infer_trigger_type(first_col, trigger_name),
                        "project_name": project_name,
                        "suitable_sex": _detect_suitable_sex(project_name),
                    }
                )
    return rows


def _iter_doctor_conclusion_mapping_rows() -> list[dict[str, str | None]]:
    """读取医生终检意见映射表并输出标准化行。

    业务意图：
        该表用于把终检意见提取出的“原始复查项目”统一映射到标准项目名。
        导入阶段先完成字段清洗和空值剔除，后续四象限计算直接按标准名做去重和推荐。
    """

    file_path = _DOCS_DIR / _DOCTOR_MAPPING_FILE
    if not file_path.exists():
        logger.warning("医生终检意见映射文件不存在，跳过: %s", file_path)
        return []

    rows: list[dict[str, str | None]] = []
    excel = pd.ExcelFile(file_path)
    for sheet_name in excel.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        if df.empty:
            continue

        raw_col = "处方检查项"
        code_col = "SFXMDM"
        mapped_col = "映射后检查项"
        if raw_col not in df.columns or mapped_col not in df.columns:
            logger.warning("Sheet 缺少必要列，跳过: %s.%s", file_path.name, sheet_name)
            continue

        for _, item in df.iterrows():
            raw_exam_name = _normalize_text(item.get(raw_col))
            mapped_exam_name = _normalize_text(item.get(mapped_col))
            exam_code_text = _normalize_text(item.get(code_col))

            # 原始项和标准项缺一不可，否则无法形成可用的标准化映射。
            if not raw_exam_name or not mapped_exam_name:
                continue

            rows.append(
                {
                    "raw_exam_name": raw_exam_name,
                    "exam_code": exam_code_text or None,
                    "mapped_exam_name": mapped_exam_name,
                }
            )
    return rows


def _ensure_table_exists(cursor: pymysql.cursors.Cursor, table_name: str) -> None:
    """校验目标表是否存在。"""

    cursor.execute(
        """
SELECT COUNT(1)
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = %s
""".strip(),
        (table_name,),
    )
    count = int(cursor.fetchone()[0])
    if count == 0:
        raise RuntimeError(f"目标表不存在: {table_name}")


def _has_column(cursor: pymysql.cursors.Cursor, table_name: str, column_name: str) -> bool:
    """判断字段是否存在。"""

    cursor.execute(
        """
SELECT COUNT(1)
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = %s
  AND column_name = %s
""".strip(),
        (table_name, column_name),
    )
    return int(cursor.fetchone()[0]) > 0


def _ensure_suitable_sex_columns(cursor: pymysql.cursors.Cursor) -> tuple[bool, bool]:
    """确保节点表包含 suitable_sex 列并返回可用性。

    业务意图：
        你要求根据第二列项目文本写入 male/female/all。如果库表是旧结构，
        这里自动补列，避免导入逻辑和表结构不一致。
    """

    exam_has = _has_column(cursor, "lz_physicalexam_node", "suitable_sex")
    if not exam_has:
        cursor.execute(
            """
ALTER TABLE lz_physicalexam_node
ADD COLUMN suitable_sex VARCHAR(16) NOT NULL DEFAULT 'all' COMMENT '适用性别 (male/female/all)'
""".strip()
        )
        exam_has = True

    treatment_has = _has_column(cursor, "lz_treatment_node", "suitable_sex")
    if not treatment_has:
        cursor.execute(
            """
ALTER TABLE lz_treatment_node
ADD COLUMN suitable_sex VARCHAR(16) NOT NULL DEFAULT 'all' COMMENT '适用性别 (male/female/all)'
""".strip()
        )
        treatment_has = True

    return exam_has, treatment_has


def import_excels_to_business_mysql(*, dry_run: bool = False) -> ImportStats:
    """导入三份 Excel 到业务 MySQL。

    Args:
        dry_run: 为 True 时只解析并统计，不写库。

    Returns:
        导入统计结果。
    """

    stats = ImportStats()
    rows = _iter_excel_rows()
    mapping_rows = _iter_doctor_conclusion_mapping_rows()
    stats.source_rows = len(rows)
    stats.mapping_source_rows = len(mapping_rows)
    if not rows and not mapping_rows:
        logger.warning("未解析到任何可导入数据。")
        return stats

    if dry_run:
        return stats

    conn = pymysql.connect(**build_business_mysql_conn_params())
    try:
        with conn.cursor() as cursor:
            _ensure_table_exists(cursor, "lz_clinical_pathway")
            _ensure_table_exists(cursor, "lz_physicalexam_node")
            _ensure_table_exists(cursor, "lz_treatment_node")
            _ensure_table_exists(cursor, "lz_doctor_conclusion_exam_mapping")
            exam_has_sex, treatment_has_sex = _ensure_suitable_sex_columns(cursor)

            # 1) 先写主路径，确保子节点始终可关联到主干。
            # 2) 再按关系类型写 exam/treatment 节点。
            for row in rows:
                pathway_id = _stable_pathway_id(row["source_sheet"], row["trigger_name"])
                inserted = cursor.execute(
                    """
INSERT INTO lz_clinical_pathway(pathway_id, trigger_name, trigger_type, source_sheet)
SELECT %s, %s, %s, %s
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM lz_clinical_pathway WHERE pathway_id = %s
)
""".strip(),
                    (
                        pathway_id,
                        row["trigger_name"],
                        row["trigger_type"],
                        row["source_sheet"],
                        pathway_id,
                    ),
                )
                if inserted:
                    stats.pathway_inserted += 1
                else:
                    stats.pathway_skipped += 1

                if row["relation_type"] == "exam":
                    exam_type = _derive_exam_type(row["second_col"])
                    if exam_has_sex:
                        inserted = cursor.execute(
                            """
INSERT INTO lz_physicalexam_node(pathway_id, exam_name, exam_type, suitable_sex)
SELECT %s, %s, %s, %s
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1
    FROM lz_physicalexam_node
    WHERE pathway_id=%s AND exam_name=%s AND exam_type=%s
)
""".strip(),
                            (
                                pathway_id,
                                row["project_name"],
                                exam_type,
                                row["suitable_sex"],
                                pathway_id,
                                row["project_name"],
                                exam_type,
                            ),
                        )
                    else:
                        inserted = cursor.execute(
                            """
INSERT INTO lz_physicalexam_node(pathway_id, exam_name, exam_type)
SELECT %s, %s, %s
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1
    FROM lz_physicalexam_node
    WHERE pathway_id=%s AND exam_name=%s AND exam_type=%s
)
""".strip(),
                            (
                                pathway_id,
                                row["project_name"],
                                exam_type,
                                pathway_id,
                                row["project_name"],
                                exam_type,
                            ),
                        )
                    if inserted:
                        stats.exam_inserted += 1
                    else:
                        stats.exam_skipped += 1
                    continue

                priority_level = _derive_priority_level(row["second_col"])
                if treatment_has_sex:
                    inserted = cursor.execute(
                        """
INSERT INTO lz_treatment_node(
    pathway_id, treatment_name, treatment_category, priority_level, suitable_sex
)
SELECT %s, %s, NULL, %s, %s
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1
    FROM lz_treatment_node
    WHERE pathway_id=%s AND treatment_name=%s AND priority_level=%s
)
""".strip(),
                        (
                            pathway_id,
                            row["project_name"],
                            priority_level,
                            row["suitable_sex"],
                            pathway_id,
                            row["project_name"],
                            priority_level,
                        ),
                    )
                else:
                    inserted = cursor.execute(
                        """
INSERT INTO lz_treatment_node(
    pathway_id, treatment_name, treatment_category, priority_level
)
SELECT %s, %s, NULL, %s
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1
    FROM lz_treatment_node
    WHERE pathway_id=%s AND treatment_name=%s AND priority_level=%s
)
""".strip(),
                        (
                            pathway_id,
                            row["project_name"],
                            priority_level,
                            pathway_id,
                            row["project_name"],
                            priority_level,
                        ),
                    )
                if inserted:
                    stats.treatment_inserted += 1
                else:
                    stats.treatment_skipped += 1

            for row in mapping_rows:
                inserted = cursor.execute(
                    """
INSERT INTO lz_doctor_conclusion_exam_mapping(
    raw_exam_name, exam_code, mapped_exam_name, is_active
)
SELECT %s, %s, %s, 1
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1
    FROM lz_doctor_conclusion_exam_mapping
    WHERE raw_exam_name = %s
      AND exam_code <=> %s
      AND mapped_exam_name = %s
)
""".strip(),
                    (
                        row["raw_exam_name"],
                        row["exam_code"],
                        row["mapped_exam_name"],
                        row["raw_exam_name"],
                        row["exam_code"],
                        row["mapped_exam_name"],
                    ),
                )
                if inserted:
                    stats.mapping_inserted += 1
                else:
                    stats.mapping_skipped += 1

        conn.commit()
        return stats
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description="导入丽滋关系拆分 Excel 到业务 MySQL")
    parser.add_argument("--dry-run", action="store_true", help="只解析不写库")
    args = parser.parse_args()

    result = import_excels_to_business_mysql(dry_run=args.dry_run)
    print(
        "导入完成: "
        f"source_rows={result.source_rows}, "
        f"pathway(inserted={result.pathway_inserted}, skipped={result.pathway_skipped}), "
        f"exam(inserted={result.exam_inserted}, skipped={result.exam_skipped}), "
        f"treatment(inserted={result.treatment_inserted}, skipped={result.treatment_skipped}), "
        f"doctor_mapping(source_rows={result.mapping_source_rows}, "
        f"inserted={result.mapping_inserted}, skipped={result.mapping_skipped})"
    )
