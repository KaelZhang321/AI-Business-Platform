from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedModelSource:
    """模型加载源解析结果。

    功能：
        把“模型仓库名”和“本地模型目录”两个配置语义显式拆开，避免离线容器把
        `BAAI/bge-m3` 误当成本地目录或把本地目录误当成 HuggingFace 仓库名。

    Attributes:
        source: 最终传给底层模型加载器的参数，可能是绝对目录，也可能是模型名。
        source_kind: 当前 source 的来源类型，仅允许 `local_path` 或 `model_name`。
        configured_path: 原始配置的本地目录，便于日志层输出回退原因。
    """

    source: str
    source_kind: str
    configured_path: str | None = None


def resolve_model_source(*, model_name: str, local_model_path: str | None) -> ResolvedModelSource:
    """解析模型实际加载源。

    功能：
        企业离线部署下，模型通常通过镜像或挂载目录预置到容器中。这里优先使用本地目录，
        是为了彻底切断运行时对外网和 HuggingFace Hub 的硬依赖；只有本地目录未配置或
        不可用时，才回退到原有的 `model_name` 逻辑。

    Args:
        model_name: 远端仓库名或兼容旧配置的模型标识。
        local_model_path: 期望优先命中的本地模型目录。

    Returns:
        标准化后的模型加载源信息；若本地目录存在则返回绝对路径，否则返回原始模型名。

    Edge Cases:
        - 本地路径支持相对路径输入，但会在返回前统一归一化成绝对路径
        - 如果配置的是文件而不是目录，会被视为无效路径并回退到 `model_name`
        - 空字符串和纯空白路径会被视为“未配置本地目录”
    """
    normalized_path = (local_model_path or "").strip()
    if not normalized_path:
        return ResolvedModelSource(source=model_name, source_kind="model_name")

    candidate = Path(normalized_path).expanduser().resolve()
    if candidate.is_dir():
        return ResolvedModelSource(
            source=str(candidate),
            source_kind="local_path",
            configured_path=normalized_path,
        )

    return ResolvedModelSource(
        source=model_name,
        source_kind="model_name",
        configured_path=normalized_path,
    )
