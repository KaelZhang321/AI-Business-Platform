"""create report intent dictionary tables

Revision ID: 20260428_01
Revises: 20260427_01
Create Date: 2026-04-28 13:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260428_01"
down_revision = "20260427_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建报告意图词典三表。

    功能：
        把 report-intent 的规则词典、优先级定义、metric-focus 指标映射统一纳入 Alembic，
        避免线上环境依赖应用账号执行 DDL，满足“结构变更只经迁移发布”的治理约束。
    """

    op.create_table(
        "report_intent_definition",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键"),
        sa.Column("intent_code", sa.String(length=64), nullable=False, comment="意图编码"),
        sa.Column("display_name", sa.String(length=128), nullable=False, comment="展示名称"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100"), comment="优先级，越小越优先"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'"), comment="状态"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("remark", sa.String(length=500), nullable=True, comment="备注"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
        comment="报告意图主定义",
    )
    op.create_unique_constraint(
        "uk_report_intent_definition_code",
        "report_intent_definition",
        ["intent_code"],
    )
    op.create_index(
        "idx_report_intent_definition_status_priority",
        "report_intent_definition",
        ["status", "enabled", "priority"],
        unique=False,
    )

    op.create_table(
        "report_intent_keyword",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键"),
        sa.Column("intent_code", sa.String(length=64), nullable=False, comment="归属意图编码"),
        sa.Column("keyword", sa.String(length=128), nullable=False, comment="命中关键词"),
        sa.Column(
            "match_mode",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'contains'"),
            comment="匹配模式：contains/exact",
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'"), comment="状态"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100"), comment="同意图内匹配顺序"),
        sa.Column("remark", sa.String(length=500), nullable=True, comment="备注"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
        comment="报告意图关键词词典",
    )
    op.create_unique_constraint(
        "uk_report_intent_keyword",
        "report_intent_keyword",
        ["intent_code", "keyword"],
    )
    op.create_index(
        "idx_report_intent_keyword_status",
        "report_intent_keyword",
        ["status", "enabled", "intent_code", "sort_order"],
        unique=False,
    )

    op.create_table(
        "report_intent_metric_focus_keyword",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键"),
        sa.Column(
            "target_intent_code",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'metric-focus'"),
            comment="目标意图编码",
        ),
        sa.Column("keyword", sa.String(length=255), nullable=False, comment="命中关键词"),
        sa.Column("metric_code", sa.String(length=64), nullable=False, comment="标准指标编码"),
        sa.Column("standard_metric_name", sa.String(length=255), nullable=False, comment="标准指标名称"),
        sa.Column("abbreviation", sa.String(length=255), nullable=True, comment="指标缩写"),
        sa.Column("aliases", sa.Text(), nullable=True, comment="原始别名串"),
        sa.Column("metric_category", sa.String(length=128), nullable=True, comment="指标分类"),
        sa.Column("common_unit", sa.String(length=64), nullable=True, comment="常用单位"),
        sa.Column("result_type", sa.String(length=32), nullable=True, comment="结果类型"),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'standard_dict_csv'"),
            comment="数据来源",
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'"), comment="状态"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100"), comment="命中排序"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
        comment="metric-focus 指标关键词映射词典",
    )
    op.create_unique_constraint(
        "uk_metric_focus_keyword",
        "report_intent_metric_focus_keyword",
        ["metric_code", "keyword"],
    )
    op.create_index(
        "idx_metric_focus_lookup",
        "report_intent_metric_focus_keyword",
        ["status", "enabled", "keyword", "sort_order"],
        unique=False,
    )
    op.create_index(
        "idx_metric_focus_target",
        "report_intent_metric_focus_keyword",
        ["target_intent_code", "metric_code"],
        unique=False,
    )


def downgrade() -> None:
    """回滚 report intent 词典三表。"""

    op.drop_index("idx_metric_focus_target", table_name="report_intent_metric_focus_keyword")
    op.drop_index("idx_metric_focus_lookup", table_name="report_intent_metric_focus_keyword")
    op.drop_constraint("uk_metric_focus_keyword", "report_intent_metric_focus_keyword", type_="unique")
    op.drop_table("report_intent_metric_focus_keyword")

    op.drop_index("idx_report_intent_keyword_status", table_name="report_intent_keyword")
    op.drop_constraint("uk_report_intent_keyword", "report_intent_keyword", type_="unique")
    op.drop_table("report_intent_keyword")

    op.drop_index("idx_report_intent_definition_status_priority", table_name="report_intent_definition")
    op.drop_constraint("uk_report_intent_definition_code", "report_intent_definition", type_="unique")
    op.drop_table("report_intent_definition")
