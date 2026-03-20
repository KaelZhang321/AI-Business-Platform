import { useRef } from 'react'
import { Button, Typography } from 'antd'
import { CloseOutlined, RobotOutlined } from '@ant-design/icons'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  ThreadPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
} from '@assistant-ui/react'
import '@assistant-ui/react/styles/index.css'

const { Text } = Typography

interface AIChatProps {
  onClose: () => void
}

/**
 * AI对话组件 — 基于 assistant-ui
 * 文档要求: assistant-ui 0.12+ (YC支持，专业AI对话组件)
 */
export default function AIChat({ onClose }: AIChatProps) {
  const messagesRef = useRef([
    {
      role: 'assistant' as const,
      content: [
        {
          type: 'text' as const,
          text: '你好！我是AI助手，可以帮你查询待办、搜索知识库、分析数据。请问有什么需要帮助的？',
        },
      ],
    },
  ])

  const runtime = useExternalStoreRuntime({
    messages: messagesRef.current,
    isRunning: false,
    onNew: async (message) => {
      const userText =
        message.content
          .filter((c): c is { type: 'text'; text: string } => c.type === 'text')
          .map((c) => c.text)
          .join('') || ''

      messagesRef.current = [
        ...messagesRef.current,
        { role: 'user' as const, content: [{ type: 'text' as const, text: userText }] },
      ]

      // TODO: 集成 SSE 流式调用 /api/v1/chat
      messagesRef.current = [
        ...messagesRef.current,
        {
          role: 'assistant' as const,
          content: [
            {
              type: 'text' as const,
              text: 'AI网关服务正在开发中，稍后将支持对话、检索和查数功能。',
            },
          ],
        },
      ]
    },
  })

  return (
    <div className="flex flex-col h-full">
      <div className="h-14 flex items-center justify-between px-4 border-b border-gray-200">
        <span className="flex items-center gap-2">
          <RobotOutlined />
          <Text strong>AI 助手</Text>
        </span>
        <Button type="text" icon={<CloseOutlined />} onClick={onClose} size="small" />
      </div>

      <AssistantRuntimeProvider runtime={runtime}>
        <div className="flex-1 overflow-auto">
          <ThreadPrimitive.Root className="flex flex-col h-full">
            <ThreadPrimitive.Viewport className="flex-1 overflow-auto p-4">
              <ThreadPrimitive.Messages
                components={{
                  UserMessage: () => (
                    <MessagePrimitive.Root className="mb-3 flex justify-end">
                      <div className="inline-block px-3 py-2 rounded-lg max-w-[85%] bg-blue-500 text-white">
                        <MessagePrimitive.Content />
                      </div>
                    </MessagePrimitive.Root>
                  ),
                  AssistantMessage: () => (
                    <MessagePrimitive.Root className="mb-3 flex justify-start">
                      <div className="inline-block px-3 py-2 rounded-lg max-w-[85%] bg-gray-100 text-gray-800">
                        <MessagePrimitive.Content />
                      </div>
                    </MessagePrimitive.Root>
                  ),
                }}
              />
            </ThreadPrimitive.Viewport>

            <div className="p-3 border-t border-gray-200">
              <ComposerPrimitive.Root className="flex gap-2">
                <ComposerPrimitive.Input
                  placeholder="输入消息..."
                  className="flex-1 px-3 py-2 border rounded-lg outline-none focus:border-blue-400"
                />
                <ComposerPrimitive.Send className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50">
                  发送
                </ComposerPrimitive.Send>
              </ComposerPrimitive.Root>
            </div>
          </ThreadPrimitive.Root>
        </div>
      </AssistantRuntimeProvider>
    </div>
  )
}
