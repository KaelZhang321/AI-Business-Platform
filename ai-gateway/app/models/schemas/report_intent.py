from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field


class ReportIntentDialogRequest(BaseModel):
    """报告意图识别请求。

    功能：
        为 AI 咨询跳转提供最小输入契约。该接口只关注“用户当前查询词”，不承载
        会话历史或用户画像，确保判定逻辑可回放且易于测试。

    Args:
        query: 用户自然语言查询词。

    Returns:
        无直接返回；由路由层包装成标准响应壳。

    Edge Cases:
        仅做基础非空约束。复杂语义歧义由词典优先级仲裁，不在请求模型层处理。
    """

    query: str = Field(..., min_length=1, max_length=500, description="用户查询词")


class ReportIntentDialogData(BaseModel):
    """报告意图识别数据载荷。

    功能：
        统一前端跳转所需的核心字段，避免前端再解析后端内部步骤信息。

    Returns:
        - `targetId`：单一主意图
        - `focusedMetric`：仅当 `targetId=metric-focus` 时返回标准指标名
        - `targetYear`：本期固定 `null`，预留未来按年弹窗扩展
    """

    model_config = ConfigDict(populate_by_name=True)

    target_id: str = Field(..., alias="targetId", description="主命中意图标识")
    focused_metric: str | None = Field(None, alias="focusedMetric", description="命中的标准单项指标名称")
    target_year: int | None = Field(None, alias="targetYear", description="目标年份，当前固定为空")


class ReportIntentDialogEnvelopeResponse(BaseModel):
    """报告意图识别统一响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: ReportIntentDialogData = Field(..., description="意图识别结果")
