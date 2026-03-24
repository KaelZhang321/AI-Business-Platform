import { useRef, useState } from 'react'
import { Alert, Button, List, Space, Tag, Typography, message } from 'antd'
import { CloseOutlined, RobotOutlined } from '@ant-design/icons'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  ThreadPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
} from '@assistant-ui/react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github.css'
import type { Source } from '../../types'
import DynamicRenderer from '../dynamic-ui/DynamicRenderer'
import type { UIAction } from '../dynamic-ui/catalog'
import { useAppStore } from '../../stores/useAppStore'

const { Text } = Typography

interface AIChatProps {
  onClose: () => void
}

type ChatMsg = {
  role: 'user' | 'assistant'
  content: Array<{ type: 'text'; text: string }>
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin

export default function AIChat({ onClose }: AIChatProps) {
  const { user } = useAppStore()
  const messagesRef = useRef<ChatMsg[]>([
    {
      role: 'assistant',
      content: [
        {
          type: 'text',
          text: '你好！我是AI助手，可以帮你查询待办、搜索知识库、分析数据。请问有什么需要帮助的？',
        },
      ],
    },
  ])
  const abortControllerRef = useRef<AbortController | null>(null)
  const conversationIdRef = useRef<string | null>(null)
  const bufferRef = useRef('')
  const [uiSpec, setUiSpec] = useState<unknown>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [intent, setIntent] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [, forceRender] = useState(0)

  const runtime = useExternalStoreRuntime({
    messages: messagesRef.current,
    isRunning: isStreaming,
    convertMessage: (msg: ChatMsg) => ({
      role: msg.role,
      content: msg.content.map((c) => ({ type: 'text' as const, text: c.text })),
    }),
    onNew: async (appendMsg) => {
      const userText =
        appendMsg.content
          .filter((c): c is { type: 'text'; text: string } => c.type === 'text')
          .map((c) => c.text)
          .join('') || ''

      addMessage({ role: 'user', text: userText })
      await streamChat(userText)
    },
  })

  const addMessage = ({ role, text }: { role: 'user' | 'assistant'; text: string }) => {
    messagesRef.current = [
      ...messagesRef.current,
      { role, content: [{ type: 'text' as const, text }] },
    ]
    forceRender((tick) => tick + 1)
  }

  const appendAssistantChunk = (chunk: string) => {
    if (!chunk) return
    const nextMessages = [...messagesRef.current]
    const last = nextMessages[nextMessages.length - 1]
    if (!last || last.role !== 'assistant') {
      nextMessages.push({ role: 'assistant', content: [{ type: 'text', text: chunk }] })
    } else {
      const currentText = last.content?.[0]?.text ?? ''
      last.content = [{ type: 'text', text: currentText + chunk }]
    }
    messagesRef.current = nextMessages
    forceRender((tick) => tick + 1)
  }

  const streamChat = async (userText: string) => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller
    setIsStreaming(true)
    setUiSpec(null)
    setSources([])
    setIntent(null)

    try {
      const body = {
        message: userText,
        conversation_id: conversationIdRef.current,
        user_id: user?.id ?? 'demo-user',
        stream: true,
      }
      const token = localStorage.getItem('ai_platform_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const response = await fetch(`${API_BASE_URL}/api/v1/chat?stream=true`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        throw new Error('聊天服务不可用')
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      bufferRef.current = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        bufferRef.current += decoder.decode(value, { stream: true })
        bufferRef.current = processEventBuffer(bufferRef.current)
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        message.error((error as Error).message || 'AI 对话失败')
      }
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }

  const processEventBuffer = (buffer: string) => {
    let remaining = buffer
    let boundary = remaining.indexOf('\n\n')
    while (boundary !== -1) {
      const rawEvent = remaining.slice(0, boundary)
      remaining = remaining.slice(boundary + 2)
      handleRawEvent(rawEvent)
      boundary = remaining.indexOf('\n\n')
    }
    return remaining
  }

  const handleRawEvent = (raw: string) => {
    let event = 'message'
    let dataPayload = ''
    raw.split('\n').forEach((line) => {
      if (line.startsWith('event:')) {
        event = line.replace('event:', '').trim()
      } else if (line.startsWith('data:')) {
        dataPayload += line.replace('data:', '').trim()
      }
    })
    if (!dataPayload) return
    try {
      const parsed = JSON.parse(dataPayload)
      switch (event) {
        case 'intent':
          setIntent(parsed.intent as string)
          break
        case 'content':
          appendAssistantChunk(parsed.text as string)
          break
        case 'ui_spec':
          setUiSpec(parsed)
          break
        case 'sources':
          setSources(parsed as Source[])
          break
        case 'done':
          conversationIdRef.current = parsed.conversation_id as string
          break
        default:
          break
      }
    } catch {
      // ignore malformed payload
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="h-14 flex items-center justify-between px-4 border-b border-gray-200">
        <span className="flex items-center gap-2">
          <RobotOutlined />
          <Text strong>AI 助手</Text>
        </span>
        <Button type="text" icon={<CloseOutlined />} onClick={onClose} size="small" aria-label="关闭对话" />
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
                        <MessagePrimitive.Content
                          components={{
                            Text: ({ text }) => (
                              <Markdown
                                remarkPlugins={[remarkGfm]}
                                rehypePlugins={[rehypeHighlight]}
                                components={{
                                  pre: ({ children }) => (
                                    <pre className="overflow-x-auto rounded bg-gray-800 p-3 text-sm my-2">
                                      {children}
                                    </pre>
                                  ),
                                  code: ({ children, className }) =>
                                    className ? (
                                      <code className={className}>{children}</code>
                                    ) : (
                                      <code className="bg-gray-200 px-1 rounded text-sm">{children}</code>
                                    ),
                                  table: ({ children }) => (
                                    <table className="border-collapse border border-gray-300 my-2 w-full text-sm">
                                      {children}
                                    </table>
                                  ),
                                  th: ({ children }) => (
                                    <th className="border border-gray-300 bg-gray-50 px-2 py-1 text-left">
                                      {children}
                                    </th>
                                  ),
                                  td: ({ children }) => (
                                    <td className="border border-gray-300 px-2 py-1">{children}</td>
                                  ),
                                }}
                              >
                                {text}
                              </Markdown>
                            ),
                          }}
                        />
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
                  aria-label="聊天输入框"
                  className="flex-1 px-3 py-2 border rounded-lg outline-none focus:border-blue-400"
                />
                <ComposerPrimitive.Send className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50" aria-label="发送消息">
                  发送
                </ComposerPrimitive.Send>
              </ComposerPrimitive.Root>
            </div>
          </ThreadPrimitive.Root>
        </div>
      </AssistantRuntimeProvider>

      <div className="border-t border-gray-200 p-4 space-y-3">
        {intent && (
          <Space>
            <Text type="secondary">识别意图:</Text>
            <Tag color="geekblue">{intent}</Tag>
          </Space>
        )}
        {uiSpec != null ? (
          <div>
            <Text strong>智能 UI</Text>
            <DynamicRenderer
              spec={uiSpec}
              onAction={(action: UIAction, payload?: Record<string, unknown>) => {
                if (action.type === 'trigger_task' && payload) {
                  const summary = Object.entries(payload)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(', ')
                  streamChat(`请帮我创建任务：${summary}`)
                } else if (action.type === 'view_detail' && action.params?.id) {
                  streamChat(`查看任务详情：${action.params.id}`)
                } else if (action.type === 'open_link' && action.url) {
                  window.open(action.url, '_blank')
                }
              }}
            />
          </div>
        ) : null}
        {sources.length > 0 && (
          <div>
            <Text strong>引用来源</Text>
            <List
              size="small"
              dataSource={sources}
              className="mt-2"
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={item.title}
                    description={
                      <span className="text-gray-500">
                        来源: {item.content?.slice(0, 60) ?? '未知'}
                      </span>
                    }
                  />
                  <Tag>{item.score?.toFixed?.(2) ?? ''}</Tag>
                </List.Item>
              )}
            />
          </div>
        )}
        {isStreaming && <Alert type="info" message="AI正在生成，请稍候..." showIcon />}
      </div>
    </div>
  )
}
