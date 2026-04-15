用户发送消息
    ↓
ConsultantAIWorkbench（父）调用 getAiResponse → 追加 AI 消息
    ↓
AiSpecExtractor（无头组件）解析最新 AI 消息
    ↓
发现 Spec → setLatestAiSpec(spec) + setViewMode('AI_PANEL')
    ↓
┌─────────────────────────────────────────────────────┐
│  AssistantSidebar（左侧对话栏）                      │
│    气泡内 → AiMessageText（只显纯文本）              │
│    有 Spec 时 → ✨ 结构化卡片已展示在主面板（提示）  │
├─────────────────────────────────────────────────────┤
│  MainReportsPanel（中央主面板）                      │
│    viewMode=AI_PANEL → 展示 AssistantRenderer 卡片   │
│    带入场动画 + 顶部标题栏                           │
└─────────────────────────────────────────────────────┘
