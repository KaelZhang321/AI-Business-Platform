from app.models.schemas import IntentType


class IntentClassifier:
    """意图分类服务 - 4类意图识别

    意图类型:
    - CHAT: 闲聊/通用对话
    - KNOWLEDGE: 知识库检索
    - QUERY: 数据查询（Text2SQL）
    - TASK: 待办/任务操作
    """

    async def classify(self, message: str, context: dict | None = None) -> IntentType:
        """对用户消息进行意图分类"""
        # TODO: 基于LLM的意图分类
        keywords_map = {
            IntentType.QUERY: ["查询", "统计", "多少", "报表", "数据"],
            IntentType.KNOWLEDGE: ["文档", "知识", "搜索", "查找资料"],
            IntentType.TASK: ["待办", "任务", "审批", "工单"],
        }
        for intent, keywords in keywords_map.items():
            if any(kw in message for kw in keywords):
                return intent
        return IntentType.CHAT
