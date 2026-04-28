from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TranscriptExtractRequest(BaseModel):
    """Transcript 信息提取请求模型。

    功能：
        对外暴露统一的 transcript 抽取入口，只允许调用方提供任务编码与原始转写文本，
        避免前端感知 prompt、模型后端等实现细节。

    入参业务含义：
        - `task_code`：前端选择的业务任务编码，服务层会再映射为内部 `service_code`
        - `transcript`：待分析的原始语音转写文本

    返回值约束：
        Pydantic 接收 snake_case，同时对外文档和序列化口径统一使用 camelCase。

    Edge Cases：
        - 兼容历史 snake_case 入参，减少联调期字段改名带来的阻塞
        - 文本只做最小非空校验，具体裁剪和清洗交由服务层处理
    """

    model_config = ConfigDict(populate_by_name=True)

    task_code: str = Field(..., alias="taskCode", min_length=1, description="抽取任务编码")
    transcript: str = Field(..., min_length=1, description="原始语音转写文本")


class TranscriptExtractData(BaseModel):
    """Transcript 信息提取结果。

    功能：
        统一承载当前请求命中的任务编码、运行时服务编码以及模型返回的结构化结果，
        让前端只消费稳定外壳，不需要感知内部路由细节。

    入参业务含义：
        - `task_code`：前端提交的任务编码
        - `service_code`：服务层最终命中的运行时服务编码
        - `result`：模型输出并经 JSON 解析后的结果对象

    返回值约束：
        `result` 必须是 JSON object；数组或纯文本会在服务层被拦截并报错。

    Edge Cases：
        三个任务可以共享同一外层 schema，同时保留各自 `result` 字段的演进空间。
    """

    model_config = ConfigDict(populate_by_name=True)

    task_code: str = Field(..., alias="taskCode", description="抽取任务编码")
    service_code: str = Field(..., alias="serviceCode", description="运行时服务编码")
    result: dict[str, Any] = Field(default_factory=dict, description="结构化提取结果")


class TranscriptExtractEnvelopeResponse(BaseModel):
    """Transcript 信息提取统一响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: TranscriptExtractData = Field(..., description="Transcript 提取结果")
