from __future__ import annotations

import logging
import threading
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from openai import OpenAI
from vanna.chromadb import ChromaDB_VectorStore

from app.bi.meeting_bi.ai.training_data import BUSINESS_DOCS, QA_PAIRS, TABLES
from app.core.config import settings

logger = logging.getLogger(__name__)

_vn = None
_lock = threading.Lock()
_CHROMA_PATH = Path(__file__).resolve().parents[4] / "data" / "chroma" / "meeting_bi"

_BUSINESS_RULES = """
重要业务规则（生成 SQL 时必须严格遵守）：

1. 表和字段选择：
   - 查"报名客户"或"报名人数"时，使用 meeting_registration 表，过滤条件为 real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%'
   - 查"已签到"或"已抵达"客户时，在报名条件基础上加 sign_in_status = '已签到'
   - 查"大区"维度时，meeting_registration 表需要用 SUBSTRING_INDEX(market_service_attribution, ',', 1) 提取大区名称
   - meeting_customer_analysis 和 meeting_transaction_details 表直接使用 region 字段

2. 金额与计算：
   - 金额字段（new_deal_amount、received_amount、consumed_amount）单位为元
   - 展示金额时建议除以 10000 换算为万元，并用 ROUND 保留 2 位小数
   - ROI 计算公式：ROUND(6000000 / NULLIF(SUM(new_deal_amount), 0) * 0.4 * 100, 2)
   - 百分比计算统一使用 ROUND(..., 2) 保留两位小数

3. 区域目标达成查询：
   - 需要 meeting_region_transaction_targets 和 meeting_transaction_details 两张表 LEFT JOIN
   - JOIN 条件：t.region = d.region AND d.deal_type = '新成交'
   - 达成率 = deal_amount / NULLIF(performance_target, 0) * 100

4. 客户等级分组规则：
   - customer_level_name LIKE '%千万%' → 千万级客户
   - customer_level_name LIKE '%百万%' OR LIKE '%300万%' → 百万级客户
   - 其余或 NULL → 普通/未分类

5. 客户来源判断：
   - store_name LIKE '%盟主%' → 盟主
   - store_name LIKE '%商务%' → 商务
   - 其余 → 店铺

6. 运营统计注意事项：
   - 查询 meeting_schedule_stats 人数时排除含 '率' 和 '占比' 的 time_period 记录
   - 离开人数：time_period = '离开人数'
   - 到院人数：time_period = '医院人数合计'

7. SQL 语法约束：
   - 只生成 SELECT 语句
   - 使用 MySQL 5.7 语法（不支持窗口函数如 ROW_NUMBER()，用 @rownum 变量替代）
   - 使用 COALESCE 处理 NULL 值
   - 使用 NULLIF 避免除零错误
   - 客户去重统计使用 COUNT(DISTINCT customer_unique_id)
"""


def _parse_mysql_url(url: str) -> dict[str, str | int]:
    cleaned = url.replace("mysql+pymysql://", "mysql://").replace("mysql+aiomysql://", "mysql://")
    parsed = urlparse(cleaned)
    params = parse_qs(parsed.query)

    def _first(name: str, default: str) -> str:
        value = params.get(name, [default])
        if isinstance(value, list):
            return str(value[0]) if value else default
        return str(value)

    return {
        "host": parsed.hostname or "localhost",
        "dbname": unquote((parsed.path or "/").lstrip("/") or "meeting_bi"),
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "port": parsed.port or 3306,
        "charset": _first("charset", "utf8mb4"),
    }


class MeetingBIVanna(ChromaDB_VectorStore):
    """使用 ChromaDB 做向量存储，兼容 OpenAI 接口 LLM 做 SQL 生成。"""

    def __init__(self, config=None):
        super().__init__(config=config)
        self._llm_client = OpenAI(
            api_key=settings.meeting_bi_api_key,
            base_url=settings.meeting_bi_base_url,
        )

    def system_message(self, message: str) -> dict:
        return {"role": "system", "content": message}

    def user_message(self, message: str) -> dict:
        return {"role": "user", "content": message}

    def assistant_message(self, message: str) -> dict:
        return {"role": "assistant", "content": message}

    def submit_prompt(self, prompt, **kwargs) -> str:
        """调用火山引擎 DeepSeek-v3 生成回复。"""
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        response = self._llm_client.chat.completions.create(
            model=settings.meeting_bi_model,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    def get_sql_prompt(self, initial_prompt, question, question_sql_list, ddl_list, doc_list, **kwargs):
        prompt = super().get_sql_prompt(
            initial_prompt=initial_prompt,
            question=question,
            question_sql_list=question_sql_list,
            ddl_list=ddl_list,
            doc_list=doc_list,
            **kwargs,
        )
        if isinstance(prompt, list) and prompt:
            prompt[0]["content"] = prompt[0]["content"] + "\n\n" + _BUSINESS_RULES
        return prompt


def get_vanna() -> MeetingBIVanna:
    global _vn
    if _vn is not None:
        return _vn

    with _lock:
        if _vn is not None:
            return _vn
        if not settings.meeting_bi_api_key:
            raise RuntimeError("Meeting BI 未配置 API Key，请设置 meeting_bi_api_key")

        _CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        logger.info("Initializing Meeting BI Vanna client (chroma_path=%s)", _CHROMA_PATH)
        _vn = MeetingBIVanna(config={"model": "meeting-bi", "path": str(_CHROMA_PATH)})
        _vn.connect_to_mysql(**_parse_mysql_url(settings.meeting_bi_database_url))
        _train(_vn)
        return _vn


def _train(vn: MeetingBIVanna) -> None:
    for table in TABLES:
        try:
            result = vn.run_sql(f"SHOW CREATE TABLE {table}")
            if result is not None and not result.empty:
                ddl = result.iloc[0]["Create Table"]
                vn.train(ddl=ddl)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.warning("Meeting BI DDL training warning for %s: %s", table, exc)

    for doc in BUSINESS_DOCS:
        try:
            vn.train(documentation=doc)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.warning("Meeting BI documentation training warning: %s", exc)

    for qa in QA_PAIRS:
        try:
            vn.train(question=qa["question"], sql=qa["sql"])
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.warning("Meeting BI QA training warning: %s", exc)
