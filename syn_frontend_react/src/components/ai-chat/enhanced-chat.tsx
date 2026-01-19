"use client"

import * as React from "react"
import { Thread, ThreadSidebar } from "./thread-sidebar"
import { ChatList } from "./chat-list"
import type { ToolCall } from "./tool-call-display"
import {
  AgentReasoning,
  Tool,
  ToolHeader,
  ToolName,
  ToolStatus,
  ToolResult,
  ToolConfirmation,
  TaskList
} from "@/components/ai-elements"
import type { ConfirmationState } from "@/components/ai-elements/confirmation"
import {
  PromptInput,
  PromptInputHeader,
  PromptInputBody,
  PromptInputFooter,
  PromptInputTextarea,
  PromptInputSubmit
} from "@/components/ai-elements/prompt-input"
import {
  Conversation,
  ConversationContent
} from "@/components/ai-elements/conversation"
import { useManusStream } from "@/hooks/useManusStream"
import { Link2, Sparkles, Settings, Bot, MessageSquare, Sidebar } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/use-toast"
import { useRouter } from "next/navigation"
import { API_ENDPOINTS } from "@/lib/env"

interface Message {
  id: string
  role: "user" | "assistant" | "system" | "tool"
  content: string
  timestamp?: Date
  tool_calls?: ToolCall[]
  thinking?: string
  metadata?: Record<string, any>
}

interface ModelConfig {
  service_type: string
  provider: string
  model_name: string
  is_active: boolean
}

export function EnhancedAIChat() {
  const router = useRouter()
  const { toast } = useToast()
  const [mode, setMode] = React.useState<"chat" | "agent" | "openmanus">("chat")

  // Thread管理
  const [threads, setThreads] = React.useState<Thread[]>([])
  const [currentThreadId, setCurrentThreadId] = React.useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = React.useState(false)

  // 消息管理
  const [messages, setMessages] = React.useState<Message[]>([])
  const [input, setInput] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [isConnected, setIsConnected] = React.useState(false)
  const [connectionError, setConnectionError] = React.useState<string | null>(null)

  // AI Elements state
  const [agentThinking, setAgentThinking] = React.useState<string>("")
  const [isAgentThinking, setIsAgentThinking] = React.useState(false)
  const [agentTaskQueue, setAgentTaskQueue] = React.useState<Array<{
    id: string
    name: string
    status: "pending" | "in-progress" | "completed" | "failed"
    metadata?: Record<string, any>
  }>>([])

  // OpenManus 流式状态
  const manusStream = useManusStream()
  const resetManusStream = manusStream.resetState
  const startManusStreaming = manusStream.startStreaming
  const stopManusStreaming = manusStream.stopStreaming
  const manusLogMessageIdRef = React.useRef<string | null>(null)
  const manusLogThreadIdRef = React.useRef<string | null>(null)
  const manusLogContentRef = React.useRef<string>("")
  const manusLogSavedRef = React.useRef<boolean>(false)
  const manusEventCursorRef = React.useRef<number>(0)
  const manusThinkingMessageIdRef = React.useRef<string | null>(null)
  const manusThinkingContentRef = React.useRef<string>("")
  const manusThinkingSavedRef = React.useRef<boolean>(false)
  const lastManusInputRef = React.useRef<string>("")
  const lastAgentInputRef = React.useRef<string>("")
  const agentPausedRef = React.useRef<boolean>(false)
  const agentPendingResultRef = React.useRef<null | (() => void)>(null)
  const [manusRunState, setManusRunState] = React.useState<"idle" | "running" | "completed" | "failed">("idle")
  const [agentRunState, setAgentRunState] = React.useState<"idle" | "running" | "paused" | "completed" | "failed">("idle")
  const [manusConfirmation, setManusConfirmation] = React.useState<{
    state: ConfirmationState
    taskSummary?: {
      goal?: string
      tools?: Array<{ name: string; arguments: any }>
    }
  } | null>(null)
  const [manusConfirming, setManusConfirming] = React.useState(false)
  const manusConfirmTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  // 模型配置
  const [chatModelConfig, setChatModelConfig] = React.useState<ModelConfig | null>(null)
  const [agentModelConfig, setAgentModelConfig] = React.useState<ModelConfig | null>(null)
  const [openmanusModelConfig, setOpenmanusModelConfig] = React.useState<ModelConfig | null>(null)

  // 加载线程列表（按模式过滤）
  const loadThreads = React.useCallback(async () => {
    try {
      const response = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/threads/?limit=500&mode=${mode}`)
      const data = await response.json()
      if (data.status === "success") {
        setThreads(data.data.threads)
      }
    } catch (error) {
      console.error("Failed to load threads:", error)
    }
  }, [mode])

  // 加载模型配置
  const loadModelConfigs = React.useCallback(async () => {
    try {
      // 加载 Chat 模式的模型配置
      const chatResponse = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/model-configs/chat`)
      const chatData = await chatResponse.json()
      if (chatData.status === "success" && chatData.data) {
        setChatModelConfig(chatData.data)
      }

      // 加载 Agent 模式的模型配置（Function Calling）
      const agentResponse = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/model-configs/function_calling`)
      const agentData = await agentResponse.json()
      if (agentData.status === "success" && agentData.data) {
        setAgentModelConfig(agentData.data)
        // OpenManus 也使用 Function Calling 配置
        setOpenmanusModelConfig(agentData.data)
      }
    } catch (error) {
      console.error("Failed to load model configs:", error)
    }
  }, [])

  const clearManusConfirmationTimer = React.useCallback(() => {
    if (manusConfirmTimeoutRef.current) {
      clearTimeout(manusConfirmTimeoutRef.current)
      manusConfirmTimeoutRef.current = null
    }
  }, [])

  const scheduleManusConfirmationClear = React.useCallback(() => {
    clearManusConfirmationTimer()
    manusConfirmTimeoutRef.current = setTimeout(() => {
      setManusConfirmation(null)
      manusConfirmTimeoutRef.current = null
    }, 800)
  }, [clearManusConfirmationTimer])

  React.useEffect(() => {
    return () => {
      if (manusConfirmTimeoutRef.current) {
        clearTimeout(manusConfirmTimeoutRef.current)
      }
    }
  }, [])

  const decodeUnicodeEscapes = React.useCallback((text: string) => {
    if (!text || !text.includes("\\u")) return text
    return text.replace(/\\u([0-9a-fA-F]{4})/g, (_, code) =>
      String.fromCharCode(parseInt(code, 16))
    )
  }, [])

  const switchModel = React.useCallback(async (modelName: string) => {
    try {
      const response = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/switch-model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      await loadModelConfigs()
    } catch (error) {
      console.error("Failed to switch model:", error)
      toast({
        title: "错误",
        description: "切换模型失败",
        variant: "destructive"
      })
    }
  }, [loadModelConfigs, toast])

  // 加载线程消息
  const loadMessages = React.useCallback(async (threadId: string) => {
    try {
      const response = await fetch(
        `${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/threads/${threadId}/messages`
      )
      const data = await response.json()
      if (data.status === "success") {
        const loadedMessages: Message[] = data.data.messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: decodeUnicodeEscapes(msg.content || ""),
          timestamp: new Date(msg.created_at),
          tool_calls: msg.tool_calls,
          metadata: msg.metadata
        }))
        setMessages(loadedMessages)
      }
    } catch (error) {
      console.error("Failed to load messages:", error)
      toast({
        title: "错误",
        description: "加载消息失败",
        variant: "destructive"
      })
    }
  }, [toast])

  // 创建新线程（带 mode 参数）
  const handleCreateThread = React.useCallback(async () => {
    try {
      const response = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/threads/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `新对话 ${new Date().toLocaleString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`,
          mode: mode  // 传递当前模式
        })
      })
      const data = await response.json()
      if (data.status === "success") {
        const newThread: Thread = {
          id: data.data.thread_id,
          title: data.data.title,
          created_at: data.data.created_at,
          updated_at: data.data.updated_at,
          message_count: 0
        }
        setThreads(prev => [newThread, ...prev])
        setCurrentThreadId(newThread.id)
        setMessages([])
        resetManusStream()
        manusLogMessageIdRef.current = null
        manusLogThreadIdRef.current = null
        manusLogContentRef.current = ""
        manusLogSavedRef.current = false
        manusEventCursorRef.current = 0
        manusThinkingMessageIdRef.current = null
        manusThinkingContentRef.current = ""
        manusThinkingSavedRef.current = false
        setManusRunState("idle")
        setAgentRunState("idle")
        setManusConfirmation(null)
        setManusConfirming(false)
        clearManusConfirmationTimer()
        setAgentTaskQueue([])
        setAgentThinking("")
        setIsAgentThinking(false)
        toast({
          title: "成功",
          description: "新对话已创建"
        })
      }
    } catch (error) {
      console.error("Failed to create thread:", error)
      toast({
        title: "错误",
        description: "创建对话失败",
        variant: "destructive"
      })
    }
  }, [clearManusConfirmationTimer, toast, mode, resetManusStream])

  // 删除线程
  const handleDeleteThread = React.useCallback(async (threadId: string) => {
    try {
      const response = await fetch(
        `${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/threads/${threadId}`,
        { method: 'DELETE' }
      )
      if (response.ok) {
        setThreads(prev => prev.filter(t => t.id !== threadId))
        if (currentThreadId === threadId) {
          setCurrentThreadId(null)
          setMessages([])
        }
        toast({
          title: "成功",
          description: "对话已删除"
        })
      }
    } catch (error) {
      console.error("Failed to delete thread:", error)
      toast({
        title: "错误",
        description: "删除对话失败",
        variant: "destructive"
      })
    }
  }, [currentThreadId, toast])

  // 重命名线程
  const handleRenameThread = React.useCallback(async (threadId: string, newTitle: string) => {
    try {
      const response = await fetch(
        `${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/threads/${threadId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: newTitle })
        }
      )
      if (response.ok) {
        setThreads(prev => prev.map(t =>
          t.id === threadId ? { ...t, title: newTitle } : t
        ))
        toast({
          title: "成功",
          description: "对话已重命名"
        })
      }
    } catch (error) {
      console.error("Failed to rename thread:", error)
      toast({
        title: "错误",
        description: "重命名失败",
        variant: "destructive"
      })
    }
  }, [toast])

  // 选择线程
  const handleSelectThread = React.useCallback((threadId: string) => {
    // 切换线程时，清理运行态，避免新旧对话互相串台（尤其是 OpenManus 流式事件）
    resetManusStream()
    manusLogMessageIdRef.current = null
    manusLogThreadIdRef.current = null
    manusLogContentRef.current = ""
    manusLogSavedRef.current = false
    manusEventCursorRef.current = 0
    manusThinkingMessageIdRef.current = null
    manusThinkingContentRef.current = ""
    manusThinkingSavedRef.current = false
    setManusRunState("idle")
    setAgentRunState("idle")
    setManusConfirmation(null)
    setManusConfirming(false)
    clearManusConfirmationTimer()

    // Agent 面板也清一下（避免上一轮残留）
    setAgentTaskQueue([])
    setAgentThinking("")
    setIsAgentThinking(false)

    setCurrentThreadId(threadId)
    loadMessages(threadId)
  }, [clearManusConfirmationTimer, loadMessages, resetManusStream])

  // 保存消息到线程
  const saveMessageToThread = React.useCallback(async (
    threadId: string,
    role: string,
    content: string,
    toolCalls?: ToolCall[],
    metadata?: Record<string, any>
  ) => {
    try {
      const response = await fetch(
        `${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/threads/${threadId}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role,
            content,
            tool_calls: toolCalls,
            metadata
          })
        }
      )
      const data = await response.json()
      if (data.status === "success") {
        // 更新线程列表中的消息计数
        setThreads(prev => prev.map(t =>
          t.id === threadId
            ? { ...t, message_count: t.message_count + 1, updated_at: data.data.created_at }
            : t
        ))
      }
    } catch (error) {
      console.error("Failed to save message:", error)
    }
  }, [])

  const submitManusConfirmation = React.useCallback(async (approved: boolean) => {
    if (manusConfirming) return
    setManusConfirming(true)
    clearManusConfirmationTimer()
    try {
      const response = await fetch(
        `${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/agent/manus-confirm`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approved })
        }
      )
      const payload = await response.json().catch(() => null)
      if (!response.ok || !payload?.success) {
        const message = payload?.data?.message || payload?.detail || `HTTP ${response.status}`
        throw new Error(message)
      }
      setManusConfirmation(prev => prev ? { ...prev, state: approved ? "accepted" : "rejected" } : prev)
      scheduleManusConfirmationClear()
    } catch (error) {
      console.error("Manus confirm failed:", error)
      toast({
        title: "确认失败",
        description: "提交确认请求失败，请稍后重试。",
        variant: "destructive"
      })
    } finally {
      setManusConfirming(false)
    }
  }, [clearManusConfirmationTimer, manusConfirming, scheduleManusConfirmationClear, toast])


  // 发送消息
  const handleSubmit = React.useCallback(async (value: string) => {
    if (!value.trim() || isLoading) return
    if (mode === "openmanus" && manusStream.isStreaming) {
      toast({
        title: "请稍等",
        description: "Manus 正在执行中，结束后再发送下一条消息",
      })
      return
    }

    // 如果没有当前线程，创建一个
    let threadId = currentThreadId
    if (!threadId) {
      try {
        const response = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/threads/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: value.substring(0, 30) + (value.length > 30 ? '...' : ''),
            mode: mode  // 传递当前模式
          })
        })
        const data = await response.json()
        if (data.status === "success" && data.data.thread_id) {
          threadId = data.data.thread_id
          const newThread: Thread = {
            id: threadId!,
            title: data.data.title,
            created_at: data.data.created_at,
            updated_at: data.data.updated_at,
            message_count: 0
          }
          setThreads(prev => [newThread, ...prev])
          setCurrentThreadId(threadId!)
        } else {
          throw new Error("Failed to create thread")
        }
      } catch (error) {
        toast({
          title: "错误",
          description: "创建对话失败",
          variant: "destructive"
        })
        return
      }
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: value,
      timestamp: new Date()
    }
    if (mode === "openmanus") {
      lastManusInputRef.current = value
      setManusRunState("running")
    } else if (mode === "agent") {
      lastAgentInputRef.current = value
      agentPausedRef.current = false
      agentPendingResultRef.current = null
      setAgentRunState("running")
    }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setIsLoading(true)

    // 保存用户消息
    if (threadId) {
      await saveMessageToThread(threadId, "user", value)
    }

    try {
      if (mode === "chat") {
        // Chat 模式：流式响应
        const apiMessages = [...messages, userMsg].map(m => ({
          role: m.role,
          content: m.content
        }))

        const response = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: apiMessages })
        })

        if (!response.ok) throw new Error(`API Error: ${response.statusText}`)
        if (!response.body) throw new Error("No response body")

        const assistantMsgId = (Date.now() + 1).toString()
        const assistantMsg: Message = { id: assistantMsgId, role: "assistant", content: "", timestamp: new Date() }
        setMessages(prev => [...prev, assistantMsg])

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let done = false
        let fullContent = ""

        while (!done) {
          const { value, done: doneReading } = await reader.read()
          done = doneReading
          if (value) {
            const chunk = decoder.decode(value, { stream: true })
            fullContent += chunk
            setMessages(prev => prev.map(m =>
              m.id === assistantMsgId
                ? { ...m, content: fullContent }
                : m
            ))
          }
        }

        // 保存助手消息
        if (threadId) {
          await saveMessageToThread(threadId, "assistant", fullContent)
        }
      } else if (mode === "agent") {
        // Agent 模式 - 使用 Function Calling（不插入占位气泡）
        setIsAgentThinking(true)
        setAgentThinking("准备中")

        const apiMessages = [...messages, userMsg].map(m => ({
          role: m.role,
          content: m.content
        }))

        setAgentThinking("请求中")

        const response = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/agent-chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: apiMessages
          })
        })

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(`HTTP ${response.status}: ${errorText.substring(0, 200)}`)
        }

        const result = await response.json()

        if (result.status === "success" && result.data) {
          const data = result.data

          const applyAgentResult = async () => {
            // 工具调用
            if (data.tool_calls && data.tool_calls.length > 0) {
              setAgentThinking("执行中")
              const tasks = data.tool_calls.map((call: any, idx: number) => ({
                id: `task-${idx}`,
                name: call.name,
                status: call.result ? "completed" : call.error ? "failed" : "in-progress",
                metadata: { args: call.arguments, result: call.result }
              }))
              setAgentTaskQueue(tasks)
            }

            // 整理结果
            let resultText = ""

            if (data.success) {
              resultText = `**执行结果**\n\n${data.message}\n\n`
              // 工具调用明细
              if (data.tool_calls && data.tool_calls.length > 0) {
                resultText += `**调用了 ${data.tool_calls.length} 个工具**:\n`
                data.tool_calls.forEach((call: any, index: number) => {
                  resultText += `\n${index + 1}. **${call.name}**\n`
                  resultText += `   参数: \`${JSON.stringify(call.arguments)}\`\n`
                  if (call.result) {
                    const resultStr = typeof call.result === 'string'
                      ? call.result
                      : JSON.stringify(call.result, null, 2)
                    resultText += `   结果: ${resultStr.substring(0, 200)}${resultStr.length > 200 ? '...' : ''}\n`
                  }
                })
              }
              resultText += `\n**迭代次数**: ${data.iterations || 1}`
            } else {
              resultText = `**执行失败**\n\n${data.message || '执行失败'}`
            }
            setMessages(prev => [...prev, {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: resultText,
              tool_calls: data.tool_calls,
              timestamp: new Date()
            }])

            setIsAgentThinking(false)
            setAgentThinking("")
            setAgentRunState("completed")

            // 保存结果
            if (threadId) {
              await saveMessageToThread(threadId, "assistant", resultText, data.tool_calls)
            }
          }

          if (agentPausedRef.current) {
            agentPendingResultRef.current = () => { void applyAgentResult() }
            setAgentRunState("paused")
          } else {
            await applyAgentResult()
          }
        } else {
          const errorMsg = result.detail || "请求失败"
          const errorContent = `**执行失败**\n\n${errorMsg}`
          const applyError = async () => {
            setMessages(prev => [...prev, {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: errorContent,
              timestamp: new Date()
            }])
            setIsAgentThinking(false)
            setAgentThinking("")
            setAgentRunState("failed")

            // 保存错误到 UI
            if (threadId) {
              await saveMessageToThread(threadId, "assistant", errorContent)
            }
          }

          if (agentPausedRef.current) {
            agentPendingResultRef.current = () => { void applyError() }
            setAgentRunState("paused")
          } else {
            await applyError()
          }
        }
      } else if (mode === "openmanus") {
        // OpenManus mode - streaming execution
        try {
          manusLogMessageIdRef.current = null
          manusLogThreadIdRef.current = threadId || null
          manusLogContentRef.current = ""
          manusLogSavedRef.current = false
          manusEventCursorRef.current = 0
          manusThinkingMessageIdRef.current = null
          manusThinkingContentRef.current = ""
          manusThinkingSavedRef.current = false
          setManusRunState("idle")
          setAgentRunState("idle")
          setManusConfirmation(null)
          setManusConfirming(false)
          clearManusConfirmationTimer()

          await startManusStreaming(
            value,
            undefined,
            true,
            threadId || undefined
          )

        } catch (streamError) {
          console.error("OpenManus streaming error:", streamError)
          const errText = streamError instanceof Error ? streamError.message : String(streamError)
          const errorContent = `执行失败：${errText}`
          manusLogContentRef.current = errorContent
          const logId = manusLogMessageIdRef.current
          if (!logId) {
            const newId = `manus-result-${Date.now()}`
            manusLogMessageIdRef.current = newId
            setMessages(prev => [...prev, {
              id: newId,
              role: "assistant",
              content: errorContent,
              timestamp: new Date()
            }])
          } else {
            setMessages(prev => prev.map(m => (
              m.id === logId ? { ...m, content: errorContent } : m
            )))
          }
          setManusRunState("failed")
        }
      }
    } catch (error) {
      console.error("❌ Failed to send message:", error)
      const errorMessage = error instanceof Error ? error.message : String(error)
      const errorContent = `❌ 发送失败: ${errorMessage}`
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: "assistant",
        content: errorContent,
        timestamp: new Date()
      }])
      if (threadId) {
        await saveMessageToThread(threadId, "assistant", errorContent)
      }
    } finally {
      setIsLoading(false)
    }
  }, [clearManusConfirmationTimer, currentThreadId, messages, isLoading, mode, toast, saveMessageToThread, manusStream.isStreaming, startManusStreaming])


  const replayManus = React.useCallback(() => {
    if (!lastManusInputRef.current) return
    void handleSubmit(lastManusInputRef.current)
  }, [handleSubmit])

  const replayAgent = React.useCallback(() => {
    if (!lastAgentInputRef.current) return
    void handleSubmit(lastAgentInputRef.current)
  }, [handleSubmit])

  const pauseAgent = React.useCallback(() => {
    agentPausedRef.current = true
    setAgentRunState("paused")
  }, [])

  const resumeAgent = React.useCallback(() => {
    agentPausedRef.current = false
    setAgentRunState("running")
    const pending = agentPendingResultRef.current
    if (pending) {
      agentPendingResultRef.current = null
      pending()
    }
  }, [])

  const nextAgentStep = React.useCallback(() => {
    if (!lastAgentInputRef.current) return
    void handleSubmit("继续下一步")
  }, [handleSubmit])

  // OpenManus: append thoughts/tools/results into chat
  React.useEffect(() => {
    if (mode !== "openmanus") return

    const events = manusStream.events
    const startIndex = manusEventCursorRef.current
    if (events.length <= startIndex) return

    const ensureLog = () => {
      if (manusLogMessageIdRef.current) return manusLogMessageIdRef.current
      const newId = `manus-log-${Date.now()}`
      manusLogMessageIdRef.current = newId
      setMessages(prev => [...prev, {
        id: newId,
        role: "assistant",
        content: "",
        timestamp: new Date()
      }])
      return newId
    }

    const append = (text: string) => {
      const logId = ensureLog()
      manusLogContentRef.current = (manusLogContentRef.current || "") + text
      setMessages(prev => prev.map(m => (
        m.id === logId ? { ...m, content: manusLogContentRef.current } : m
      )))
    }

    for (let i = startIndex; i < events.length; i++) {
      const ev: any = events[i]
      switch (ev.type) {
        case "thinking": {
          const content = decodeUnicodeEscapes(String(ev.content || "")).trim()
          if (!content) break
          const thinkingId = manusThinkingMessageIdRef.current || `manus-thinking-${Date.now()}`
          manusThinkingMessageIdRef.current = thinkingId
          manusThinkingContentRef.current = content
          setMessages(prev => {
            const exists = prev.some(m => m.id === thinkingId)
            if (!exists) {
              return [
                ...prev,
                {
                  id: thinkingId,
                  role: "assistant",
                  content,
                  timestamp: new Date(),
                  metadata: { type: "thinking" }
                }
              ]
            }
            return prev.map(m =>
              m.id === thinkingId ? { ...m, content, metadata: { ...(m.metadata || {}), type: "thinking" } } : m
            )
          })
          break
        }
        case "confirmation_required": {
          clearManusConfirmationTimer()
          setManusConfirming(false)
          setManusConfirmation({
            state: "request",
            taskSummary: ev.task_summary
          })
          break
        }
        case "confirmation_received": {
          setManusConfirming(false)
          setManusConfirmation(prev => prev ? { ...prev, state: ev.approved ? "accepted" : "rejected" } : prev)
          scheduleManusConfirmationClear()
          break
        }
        case "final_result": {
          const result = ev.result || {}
          const finalText = decodeUnicodeEscapes(String(result.result || result.message || "已完成"))

          // 如果 thinking 消息存在且内容与最终结果相同，则移除 thinking 消息
          const thinkingId = manusThinkingMessageIdRef.current
          const thinkingContent = manusThinkingContentRef.current.trim()
          if (thinkingId && thinkingContent === finalText.trim()) {
            // 移除 thinking 消息，只保留最终结果
            setMessages(prev => prev.filter(m => m.id !== thinkingId))
            manusThinkingMessageIdRef.current = null
            manusThinkingContentRef.current = ""
          }

          append(`${finalText}\n`)
          setManusRunState("completed")
          break
        }
        case "error": {
          const errorText = decodeUnicodeEscapes(String(ev.error || ev.message || "未知错误"))
          append(`执行失败：${errorText}\n`)
          setManusRunState("failed")
          break
        }
        case "done": {
          setManusRunState("completed")
          break
        }
        default:
          break
      }
    }

    manusEventCursorRef.current = events.length
  }, [clearManusConfirmationTimer, mode, manusStream.events, scheduleManusConfirmationClear])

  // OpenManus: 执行结束后将“运行日志”落盘到线程消息，确保刷新/切换线程后 UI 仍能看到记录
  React.useEffect(() => {
    if (mode !== "openmanus") return
    const threadId = manusLogThreadIdRef.current
    if (!threadId) return
    if (manusStream.isStreaming) return
    if (manusLogSavedRef.current) return

    const content = (manusLogContentRef.current || "").trim()
    if (!content) return

    // 只要执行跑过（哪怕失败），也保存一次，避免“后台有记录 UI 无记录”
    void saveMessageToThread(threadId, "assistant", content)
    manusLogSavedRef.current = true
  }, [mode, manusStream.isStreaming, saveMessageToThread])

  React.useEffect(() => {
    if (mode !== "openmanus") return
    const threadId = manusLogThreadIdRef.current
    const thinkingId = manusThinkingMessageIdRef.current
    if (!threadId || !thinkingId) return
    if (manusStream.isStreaming) return
    if (manusThinkingSavedRef.current) return

    const content = (manusThinkingContentRef.current || "").trim()
    if (!content) return

    void saveMessageToThread(threadId, "assistant", content, undefined, { type: "thinking" })
    manusThinkingSavedRef.current = true
  }, [mode, manusStream.isStreaming, saveMessageToThread])

  // 移动端默认收起侧栏，避免把聊天区挤成一条缝
  React.useEffect(() => {
    if (typeof window === "undefined") return
    const isMobile = window.matchMedia("(max-width: 767px)").matches
    if (isMobile) {
      setSidebarOpen(false)
    }
  }, [])

  // 初始化
  React.useEffect(() => {
    loadThreads()
    loadModelConfigs()

    // Check connection status
    const checkStatus = async () => {
      try {
        const response = await fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/ai/status`)
        const data = await response.json()
        setIsConnected(data.connected || false)
        setConnectionError(data.connection_error || null)
      } catch (error) {
        console.error("Failed to check AI status:", error)
        setIsConnected(false)
        setConnectionError("无法连接到后端服务器")
      }
    }

    checkStatus()
    const interval = setInterval(checkStatus, 60000)  // 改为每 60 秒轮询一次
    return () => clearInterval(interval)
  }, [loadThreads, loadModelConfigs])

  // 当 mode 切换时，重新加载线程并清空当前对话
  React.useEffect(() => {
    resetManusStream()
    manusLogMessageIdRef.current = null
    manusLogThreadIdRef.current = null
    manusLogContentRef.current = ""
    manusLogSavedRef.current = false
    manusEventCursorRef.current = 0
    manusThinkingMessageIdRef.current = null
    manusThinkingContentRef.current = ""
    manusThinkingSavedRef.current = false
    setManusRunState("idle")
    setAgentRunState("idle")
    setManusConfirmation(null)

    setAgentTaskQueue([])
    setAgentThinking("")
    setIsAgentThinking(false)

    setCurrentThreadId(null)
    setMessages([])
    loadThreads()
  }, [clearManusConfirmationTimer, mode, loadThreads, resetManusStream])

  return (
    <div className="flex h-[85vh] w-full overflow-hidden rounded-3xl border border-white/10 bg-black shadow-2xl">
      {/* Thread Sidebar */}
      {sidebarOpen && (
        <ThreadSidebar
          threads={threads}
          currentThreadId={currentThreadId}
          onSelectThread={handleSelectThread}
          onCreateThread={handleCreateThread}
          onDeleteThread={handleDeleteThread}
          onRenameThread={handleRenameThread}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 bg-neutral-900/50 px-6 py-4 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              className="text-white/60 hover:text-white hover:bg-white/10"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              <Sidebar className="h-4 w-4" />
            </Button>

            <div>
              <h2 className="text-base font-bold text-white">SynapseAutomation</h2>
              <div className="flex items-center gap-2">
                {/* <p className="text-xs font-medium text-white/50">AiAgent</p> */}
                {/* 显示当前模式使用的模型 */}
                {mode === "chat" && chatModelConfig && (
                  <span className="text-xs text-blue-400/70">
                    • Chat模型: {chatModelConfig.model_name}{/*  || chatModelConfig.provider */}
                  </span>
                )}
                {mode === "agent" && agentModelConfig && (
                  <span className="text-xs text-purple-400/70">
                    • Agent模型: {agentModelConfig.model_name}  {/* || agentModelConfig.provider */}
                  </span>
                )}
                {mode === "openmanus" && openmanusModelConfig && (
                  <span className="text-xs text-orange-400/70">
                    • Manus模型: {openmanusModelConfig.model_name}
                  </span>
                )}
              </div>
            </div>

          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/ai-agent/settings")}
              className="text-white/60 hover:text-white hover:bg-white/10"
            >
              <Settings className="h-4 w-4 mr-1" />
              配置
            </Button>
            <Badge
              variant="outline"
              title={connectionError || (isConnected ? "一切系统正常" : "未配置 AI 服务")}
              className={`gap-1 text-xs font-normal transition-all ${isConnected
                ? connectionError
                  ? "border-amber-500/40 bg-amber-500/10 text-amber-500"
                  : "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                : "border-white/10 bg-white/5 text-white/40"
                }`}
            >
              <Sparkles className="h-3 w-3" />
              {isConnected ? connectionError ? "不稳定" : "在线" : "离线"}
            </Badge>
          </div>
        </div>


        <div className="border-b border-white/5 bg-neutral-900/40 px-6 py-3">
          <div className="relative flex items-center justify-center">
            <Tabs value={mode} onValueChange={(v) => setMode(v as "chat" | "agent" | "openmanus")}>
              <TabsList className="grid w-[700px] grid-cols-3 bg-white/5">
                <TabsTrigger
                  value="chat"
                  className="text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
                  title={chatModelConfig ? `使用模型: ${chatModelConfig.model_name}` : "对话模式"}
                >
                  <MessageSquare className="mr-2 h-3 w-3" />
                  Chat
                </TabsTrigger>
                <TabsTrigger
                  value="agent"
                  className="text-xs data-[state=active]:bg-purple-600 data-[state=active]:text-white"
                  title={agentModelConfig ? `使用模型: ${agentModelConfig.model_name}` : "Agent模式"}
                >
                  <Bot className="mr-2 h-3 w-3" />
                  Agent
                </TabsTrigger>
                <TabsTrigger
                  value="openmanus"
                  className="text-xs data-[state=active]:bg-orange-600 data-[state=active]:text-white"
                  title={openmanusModelConfig ? `使用模型: ${openmanusModelConfig.model_name}` : "OpenManus模式"}
                >
                  <Sparkles className="mr-2 h-3 w-3" />
                  OpenManus
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Messages Area */}
          <div className="flex-1 bg-gradient-to-b from-black to-neutral-950">
            <Conversation className="h-full">
              <ConversationContent>
                <div className="mx-auto w-full max-w-4xl space-y-6">
                  {mode === "agent" && agentTaskQueue.length > 0 && (
                    <div className="w-full rounded-2xl border border-white/10 bg-black/40 p-4 space-y-3 shadow-xl backdrop-blur-sm transition-all hover:border-white/20">
                      <TaskList
                        title="工具任务队列"
                        tasks={agentTaskQueue.map(task => ({
                          id: task.id,
                          title: task.name,
                          status: task.status,
                          metadata: task.metadata
                        }))}
                      />
                    </div>
                  )}
                  {mode === "openmanus" && manusStream.tasks.length > 0 && (
                    <div className="w-full rounded-2xl border border-white/10 bg-black/40 p-4 space-y-3 shadow-xl backdrop-blur-sm transition-all hover:border-white/20">
                      <TaskList
                        title="工具任务队列"
                        tasks={manusStream.tasks.map(task => ({
                          id: task.id,
                          title: task.name,
                          status: task.status,
                          metadata: task.metadata
                        }))}
                      />
                    </div>
                  )}
                  <ChatList
                    messages={messages.filter((m: any) => m.role !== 'tool') as any}
                    isLoading={isLoading}
                    showTypingIndicator={true}
                    showAvatars={false}
                  />
                  {mode === "openmanus" && manusConfirmation && (
                    <ToolConfirmation
                      state={manusConfirmation.state}
                      taskSummary={manusConfirmation.taskSummary}
                      disabled={manusConfirming}
                      onAccept={() => submitManusConfirmation(true)}
                      onReject={() => submitManusConfirmation(false)}
                    />
                  )}
                </div>
              </ConversationContent>
            </Conversation>
          </div>
        </div>

        {/* Input Area */}
        <div className="bg-black pb-4 pt-2">
          <div className="mx-auto w-full max-w-4xl px-4">
            <PromptInput
              value={input}
              onValueChange={setInput}
              onSubmit={({ text }) => {
                if (!text.trim()) return
                void handleSubmit(text)
              }}
            >
              <PromptInputBody>
                <div className="relative">
                  <PromptInputTextarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      // Enter 发送，Shift+Enter 换行
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault()
                        const text = input.trim()
                        if (!text) return
                        // 检查是否可以发送
                        const canSend = !isLoading &&
                          !(mode === "openmanus" && manusStream.isStreaming) &&
                          !(mode === "agent" && isAgentThinking)
                        if (canSend) {
                          void handleSubmit(text)
                        }
                      }
                    }}
                    placeholder={connectionError ? `AI 连接问题: ${connectionError}` : (!isConnected ? "请输入..." : (mode === "agent" ? "描述你的任务，例如：帮我分析最近的发布数据..." : "输入消息..."))}
                    className="bg-black/40 text-white border-white/10 pr-20"
                  />
                  <div className="absolute bottom-2 right-2 flex items-center gap-2">
                    {/* OpenManus 模式：仅保留停止按钮 */}
                    {mode === "openmanus" && (
                      <>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={(e) => {
                            e.preventDefault()
                            stopManusStreaming()
                          }}
                          disabled={!manusStream.isStreaming}
                          className="h-8"
                          type="button"
                        >
                          停止
                        </Button>
                      </>
                    )}

                    {/* 发送按钮 */}
                    <Button
                      type="submit"
                      size="sm"
                      disabled={isLoading || (mode === "openmanus" && manusStream.isStreaming) || (mode === "agent" && isAgentThinking)}
                      className="h-8"
                    >
                      发送
                    </Button>
                  </div>
                </div>
              </PromptInputBody>
            </PromptInput>
          </div>
        </div>
      </div>
    </div>
  )
}
