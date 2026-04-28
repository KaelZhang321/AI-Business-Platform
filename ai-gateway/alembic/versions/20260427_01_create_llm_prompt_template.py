"""create llm runtime config and prompt template

Revision ID: 20260427_01
Revises:
Create Date: 2026-04-27 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260427_01"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    """判断目标表是否已存在。

    说明：
        该项目在 Alembic 接管前，部分环境可能已通过手工 SQL 或历史启动脚本建过表。
        初始迁移必须具备可重入能力，否则 `upgrade head` 会在“表已存在”直接失败。
    """

    return table_name in inspector.get_table_names()


def _has_unique_constraint(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    """判断唯一约束是否已存在（兼容 MySQL 约束/唯一索引双视图）。

    说明：
        MySQL 对唯一约束和唯一索引的反射在不同版本/方言里可能表现为两套元数据。
        这里同时检查 `get_unique_constraints` 与 `get_indexes`，避免重复创建导致迁移失败。
    """

    unique_constraints = inspector.get_unique_constraints(table_name) or []
    if any(item.get("name") == constraint_name for item in unique_constraints):
        return True

    indexes = inspector.get_indexes(table_name) or []
    return any(item.get("name") == constraint_name and item.get("unique") for item in indexes)


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    """判断索引是否已存在。"""

    indexes = inspector.get_indexes(table_name) or []
    return any(item.get("name") == index_name for item in indexes)


def upgrade() -> None:
    """创建 LLM 运行时配置表和 Prompt 模板表。

    功能：
        运行时服务不再执行 DDL，因此模型后端配置与 Prompt 模板必须统一由
        Alembic 管理，避免应用账号在生产环境持有建表权限。
    """

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1) 先保证主配置表存在；对已存在环境跳过建表，避免初始迁移在历史库上失败。
    if not _has_table(inspector, "llm_service_backend_config"):
        op.create_table(
            "llm_service_backend_config",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
            sa.Column("service_code", sa.String(length=128), nullable=False, comment="业务服务编码，如 api.query"),
            sa.Column("backend_name", sa.String(length=128), nullable=False, comment="后端配置名称"),
            sa.Column("backend_type", sa.String(length=32), nullable=False, comment="后端类型：ollama/openai/vllm"),
            sa.Column("base_url", sa.String(length=255), nullable=False, comment="后端基础地址"),
            sa.Column("model_name", sa.String(length=128), nullable=False, comment="模型名称"),
            sa.Column("api_key", sa.String(length=1024), nullable=True, comment="后端密钥（可空）"),
            sa.Column(
                "chat_path",
                sa.String(length=128),
                nullable=False,
                server_default="v1/chat/completions",
                comment="聊天接口相对路径",
            ),
            sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100"), comment="优先级，越小越优先"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
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
            comment="LLM运行时服务模型配置表",
            if_not_exists=True,
        )
        inspector = sa.inspect(bind)

    # 2) 补齐唯一约束与查询索引，确保历史手建表环境具备一致约束能力。
    if not _has_unique_constraint(inspector, "llm_service_backend_config", "uk_llm_service_backend_name"):
        op.create_unique_constraint(
            "uk_llm_service_backend_name",
            "llm_service_backend_config",
            ["service_code", "backend_name"],
        )
        inspector = sa.inspect(bind)
    if not _has_index(inspector, "llm_service_backend_config", "idx_llm_service_enabled_priority"):
        op.create_index(
            "idx_llm_service_enabled_priority",
            "llm_service_backend_config",
            ["service_code", "enabled", "priority"],
            unique=False,
            if_not_exists=True,
        )
        inspector = sa.inspect(bind)

    # 3) 保证 Prompt 模板表及其索引存在，覆盖“仅创建了配置表”的半完成环境。
    if not _has_table(inspector, "llm_prompt_template"):
        op.create_table(
            "llm_prompt_template",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
            sa.Column("service_code", sa.String(length=128), nullable=False, comment="服务编码"),
            sa.Column("system_prompt", sa.Text(), nullable=False, comment="系统提示词模板"),
            sa.Column("user_prompt", sa.Text(), nullable=False, comment="用户提示词模板"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
            sa.Column("remark", sa.String(length=512), nullable=True, comment="备注"),
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
            comment="LLM Prompt 模板表",
            if_not_exists=True,
        )
        inspector = sa.inspect(bind)

    if not _has_unique_constraint(inspector, "llm_prompt_template", "uk_service_code"):
        op.create_unique_constraint("uk_service_code", "llm_prompt_template", ["service_code"])
        inspector = sa.inspect(bind)
    if not _has_index(inspector, "llm_prompt_template", "idx_enabled_service_code"):
        op.create_index(
            "idx_enabled_service_code",
            "llm_prompt_template",
            ["enabled", "service_code"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    """回滚 LLM 运行时配置表和 Prompt 模板表。"""

    op.drop_index("idx_enabled_service_code", table_name="llm_prompt_template")
    op.drop_constraint("uk_service_code", "llm_prompt_template", type_="unique")
    op.drop_table("llm_prompt_template")

    op.drop_index("idx_llm_service_enabled_priority", table_name="llm_service_backend_config")
    op.drop_constraint("uk_llm_service_backend_name", "llm_service_backend_config", type_="unique")
    op.drop_table("llm_service_backend_config")
