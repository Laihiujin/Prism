'use client'

import { useEffect, useRef, useState } from "react"
import { AIMessage, HumanMessage, ToolMessage } from "@langchain/core/messages"
import { Send, Settings, Sparkles, PlayCircle, Ban, RefreshCcw } from "lucide-react"
import createAgent from "@/lib/agent/agent"
import { tools } from "@/lib/agent/tools"
import clsx from "clsx"

type ToolCallState = "confirmed" | "rejected" | "none"
type AnyMessage = HumanMessage | AIMessage | ToolMessage

const presetPrompts = [
  {
    title: "查看脚本列表",
    description: "列出后端可运行的自动化脚本",
    prompt: "列出可用的脚本，并解释每个脚本用途",
  },
  {
    title: "运行今日维护",
    description: "执行 daily_maintenance 脚本",
    prompt: "帮我运行 daily_maintenance.py，并告诉我结果",
  },
  {
    title: "清理任务",
    description: "检查并清理周度产物",
    prompt: "看看有哪些清理脚本可以执行，帮我选一个安全的运行",
  },
  {
    title: "获取数据",
    description: "拉取最新的运营数据脚本",
    prompt: "运行 fetch_all_analytics.py 之前需要注意什么？",
  },
]

const formatTime = (value?: string) => {
  if (!value) return ""
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function AIAgentChat() {
  const [messages, setMessages] = useState<AnyMessage[]>([])
  const [inputMessage, setInputMessage] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [settings, setSettings] = useState({
    endpoint: "",
    api_key: "",
    model: "",
  })
  const [availableModels, setAvailableModels] = useState<{ value: string; label: string }[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [toolCallStates, setToolCallStates] = useState<Record<string, ToolCallState>>({})

  const agentRef = useRef<any>(null)
  const firstMessageRef = useRef(true)
  const messageContainerRef = useRef<HTMLDivElement | null>(null)
  const messagesRef = useRef<AnyMessage[]>([])

  const hasAgent = !!agentRef.current

  useEffect(() => {
    messagesRef.current = messages
    localStorage.setItem(
      "agent_messages",
      JSON.stringify(
        messages.map((m: AnyMessage) => ({
          id: m.id,
          kwargs: (m as any).kwargs,
          additional_kwargs: (m as any).additional_kwargs,
          tool_calls: (m as any).tool_calls,
        }))
      )
    )
    localStorage.setItem("agent_tool_states", JSON.stringify(toolCallStates))
  }, [messages, toolCallStates])

  useEffect(() => {
    const savedSettings = localStorage.getItem("agent_settings")
    if (savedSettings) {
      const parsed = JSON.parse(savedSettings)
      setSettings((prev) => ({ ...prev, ...parsed }))
      if (parsed.api_key && parsed.endpoint) {
        agentRef.current = createAgent({
          apiKey: parsed.api_key,
          baseURL: parsed.endpoint,
          model: parsed.model,
        })
        loadModels(parsed.endpoint, parsed.api_key)
      }
    }

    const storedMessages = JSON.parse(localStorage.getItem("agent_messages") || "[]")
    if (storedMessages.length) {
      const restored = storedMessages.map((msg: any) => {
        if (msg.id?.includes("HumanMessage")) {
          const m = new HumanMessage(msg.kwargs)
          m.additional_kwargs = msg.additional_kwargs || {}
          ;(m as any).tool_calls = msg.tool_calls
          return m
        }
        if (msg.id?.includes("AIMessage")) {
          const m = new AIMessage(msg.kwargs)
          m.additional_kwargs = msg.additional_kwargs || {}
          ;(m as any).tool_calls = msg.tool_calls
          return m
        }
        const m = new ToolMessage(msg.kwargs)
        m.additional_kwargs = msg.additional_kwargs || {}
        ;(m as any).tool_calls = msg.tool_calls
        return m
      })
      setMessages(restored)
    }

    const storedToolStates = localStorage.getItem("agent_tool_states")
    if (storedToolStates) {
      setToolCallStates(JSON.parse(storedToolStates))
    }
  }, [])

  const scrollToBottom = () => {
    if (messageContainerRef.current) {
      setTimeout(() => {
        messageContainerRef.current?.scrollTo({
          top: messageContainerRef.current.scrollHeight,
          behavior: "smooth",
        })
      }, 120)
    }
  }

  const fetchModels = async (endpoint: string, apiKey: string) => {
    const resp = await fetch(`${endpoint}/models`, {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    if (Array.isArray(data?.data)) {
      return data.data.map((model: any) => ({
        value: model.id,
        label: model.id,
      }))
    }
    return []
  }

  const loadModels = async (endpoint?: string, apiKey?: string) => {
    if (!endpoint || !apiKey) return
    setIsLoadingModels(true)
    try {
      const models = await fetchModels(endpoint, apiKey)
      if (models.length) {
        setAvailableModels(models)
      }
    } catch (err) {
      console.error("Failed to load models", err)
    } finally {
      setIsLoadingModels(false)
    }
  }

  const saveSettings = async () => {
    localStorage.setItem("agent_settings", JSON.stringify(settings))
    if (settings.api_key && settings.endpoint) {
      agentRef.current = createAgent({
        apiKey: settings.api_key,
        baseURL: settings.endpoint,
        model: settings.model,
      })
      await loadModels(settings.endpoint, settings.api_key)
    } else {
      agentRef.current = null
    }
    setShowSettings(false)
  }

  const clearConversation = () => {
    setMessages([])
    setToolCallStates({})
    localStorage.removeItem("agent_messages")
    localStorage.removeItem("agent_tool_states")
    firstMessageRef.current = true
  }

  const isToolCall = (message: AnyMessage) => {
    return Boolean((message as any).tool_calls && (message as any).tool_calls.length > 0)
  }

  const isSensitiveToolCall = (message: AnyMessage) => {
    if (!isToolCall(message)) return false
    return (message as any).tool_calls.some((call: any) =>
      ["run_script", "delete", "remove"].some((kw) => call.name?.includes(kw))
    )
  }

  const getToolCallState = (message: AnyMessage): ToolCallState => {
    if (isToolCall(message)) {
      const id = (message as any).tool_calls[0]?.id
      return (toolCallStates as any)[id] || "none"
    }
    return "none"
  }

  const executeToolAndResume = async (toolCall: any) => {
    setIsProcessing(true)
    try {
      const tool = tools.find((t) => t.name === toolCall.name)
      if (!tool) throw new Error(`Tool ${toolCall.name} not found`)
      const toolResult = await (tool as any).invoke(toolCall.args)

      const toolMessage = new ToolMessage({
        name: toolCall.name,
        content: JSON.stringify(toolResult),
        tool_call_id: toolCall.id || `tool_${Date.now()}`,
      })
      toolMessage.additional_kwargs = {
        ...(toolMessage as any).additional_kwargs,
        timestamp: new Date().toISOString(),
      }

      await continueAgentFlow([toolMessage])
    } catch (error: any) {
      const resultMessage = new ToolMessage({
        name: toolCall.name,
        content: error?.message || String(error),
        tool_call_id: toolCall.id || `tool_${Date.now()}`,
      })
      resultMessage.additional_kwargs = {
        ...(resultMessage as any).additional_kwargs,
        timestamp: new Date().toISOString(),
      }
      await continueAgentFlow([resultMessage])
    } finally {
      setIsProcessing(false)
      scrollToBottom()
    }
  }

  const handleToolCallConfirm = async (toolCall: any) => {
    setToolCallStates((prev) => ({ ...prev, [toolCall.id]: "confirmed" }))
    await executeToolAndResume(toolCall)
  }

  const handleToolCallReject = async (toolCall: any) => {
    setToolCallStates((prev) => ({ ...prev, [toolCall.id]: "rejected" }))
    const resultMessage = new ToolMessage({
      name: toolCall.name,
      content: "用户拒绝执行工具",
      tool_call_id: toolCall.id || `tool_${Date.now()}`,
    })
    resultMessage.additional_kwargs = {
      ...(resultMessage as any).additional_kwargs,
      timestamp: new Date().toISOString(),
    }
    await continueAgentFlow([resultMessage])
    scrollToBottom()
  }

  const continueAgentFlow = async (newMessages: AnyMessage[]) => {
    if (!agentRef.current) return
    const merged = [...messagesRef.current, ...newMessages]
    setMessages(merged)
    setIsProcessing(true)
    try {
      const result = await agentRef.current.invoke(
        {
          messages: firstMessageRef.current ? merged : newMessages,
        },
        {
          configurable: { thread_id: "chat-session" },
        }
      )

      const newLastMessage = result.messages[result.messages.length - 1]
      newLastMessage.additional_kwargs = {
        ...(newLastMessage as any).additional_kwargs,
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...merged, newLastMessage as AnyMessage])

      if (isToolCall(newLastMessage as AnyMessage) && !isSensitiveToolCall(newLastMessage as AnyMessage)) {
        handleToolCallConfirm((newLastMessage as any).tool_calls[0])
      }
    } catch (error) {
      const errMsg = new AIMessage("抱歉，处理您的消息时出现错误，请稍后重试。")
      errMsg.additional_kwargs = {
        ...(errMsg as any).additional_kwargs,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...merged, errMsg])
      console.error("Agent error", error)
    } finally {
      setIsProcessing(false)
      firstMessageRef.current = false
      scrollToBottom()
    }
  }

  const sendMessage = async (text?: string) => {
    const content = (text ?? inputMessage).trim()
    if (!content || isProcessing || !agentRef.current) return
    const msg = new HumanMessage(content)
    msg.additional_kwargs = {
      ...(msg as any).additional_kwargs,
      timestamp: new Date().toISOString(),
    }
    setInputMessage("")
    await continueAgentFlow([msg])
  }

  const renderMessage = (message: AnyMessage, index: number) => {
    const timestamp = (message as any).additional_kwargs?.timestamp
    const base = "rounded-2xl px-4 py-3 text-sm shadow"
    if (message instanceof HumanMessage) {
      return (
        <div key={index} className="flex justify-end">
          <div className={clsx(base, "bg-blue-600 text-white max-w-[80%]")}>
            <div>{message.content as string}</div>
            <div className="mt-1 text-[10px] text-white/80 text-right">{formatTime(timestamp)}</div>
          </div>
        </div>
      )
    }

    if (message instanceof AIMessage) {
      const toolCallState = getToolCallState(message)
      const hasToolCall = isToolCall(message)
      const toolCall = (message as any).tool_calls?.[0]
      return (
        <div key={index} className="flex justify-start">
          <div className={clsx(base, "bg-white/90 text-slate-900 border border-slate-200 max-w-[80%]")}>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 mb-1">
              <Sparkles className="h-4 w-4 text-blue-500" />
              小轴
              {timestamp && <span className="text-[10px] text-slate-500">{formatTime(timestamp)}</span>}
            </div>
            <div className="prose prose-sm max-w-none whitespace-pre-wrap leading-relaxed">{message.content as string}</div>
            {hasToolCall && (
              <div className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <PlayCircle className="h-4 w-4 text-emerald-600" />
                  准备调用工具: {toolCall?.name}
                </div>
                <pre className="mt-2 text-[11px] bg-white rounded-lg p-2 border border-slate-200 overflow-auto">
                  {JSON.stringify(toolCall?.args || {}, null, 2)}
                </pre>
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => handleToolCallConfirm(toolCall)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-500 text-white text-xs hover:bg-emerald-600 disabled:opacity-60"
                    disabled={toolCallState === "confirmed" || isProcessing}
                  >
                    允许执行
                  </button>
                  <button
                    onClick={() => handleToolCallReject(toolCall)}
                    className="px-3 py-1.5 rounded-lg bg-rose-500 text-white text-xs hover:bg-rose-600 disabled:opacity-60"
                    disabled={toolCallState !== "none" || isProcessing}
                  >
                    拒绝
                  </button>
                  <span className="text-[11px] text-slate-500 flex items-center">
                    状态: {toolCallState === "none" ? "待确认" : toolCallState === "confirmed" ? "已执行" : "已拒绝"}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )
    }

    return (
      <div key={index} className="flex justify-start">
        <div className={clsx(base, "bg-amber-50 text-amber-900 border border-amber-200 max-w-[80%]")}>
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-700 mb-1">
            <Ban className="h-4 w-4" />
            工具响应
            {timestamp && <span className="text-[10px] text-amber-500">{formatTime(timestamp)}</span>}
          </div>
          <pre className="text-[12px] whitespace-pre-wrap break-words leading-relaxed">
            {(message as any).content as string}
          </pre>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">AI 脚本助手</h1>
          <p className="text-sm text-slate-500">使用 LangGraph + 工具调用自动化脚本</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSettings(true)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900 text-white text-sm hover:bg-slate-800"
          >
            <Settings className="h-4 w-4" />
            模型设置
          </button>
          <button
            onClick={clearConversation}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 text-sm hover:bg-slate-50"
          >
            清空对话
          </button>
        </div>
      </div>

      {!hasAgent && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center">
          <p className="text-slate-700 text-sm">请先配置 OpenAI 兼容的 Endpoint / Key 才能使用 AI 工具。</p>
          <button
            onClick={() => setShowSettings(true)}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700"
          >
            <Settings className="h-4 w-4" />
            打开设置
          </button>
        </div>
      )}

      {hasAgent && messages.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {presetPrompts.map((p) => (
              <button
                key={p.prompt}
                onClick={() => sendMessage(p.prompt)}
                className="group text-left p-4 rounded-xl border border-slate-200 hover:border-blue-200 hover:shadow-md transition bg-slate-50 hover:bg-white"
              >
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center shadow">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 group-hover:text-blue-600">{p.title}</p>
                    <p className="text-xs text-slate-500 mt-1">{p.description}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <div
        ref={messageContainerRef}
        className="flex-1 overflow-y-auto rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white p-4 space-y-4"
      >
        {messages.map((m, idx) => renderMessage(m, idx))}
        {isProcessing && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-3 text-sm bg-white border border-slate-200 shadow max-w-[70%]">
              <div className="flex items-center gap-2 text-slate-500">
                <RefreshCcw className="h-4 w-4 animate-spin" />
                正在思考/执行...
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-3">
        <div className="flex items-center gap-3">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.isComposing) return
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
            placeholder={hasAgent ? "输入问题或脚本需求..." : "请先配置模型"}
            className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50"
            rows={2}
            disabled={!hasAgent || isProcessing}
          />
          <button
            onClick={() => sendMessage()}
            disabled={!inputMessage.trim() || !hasAgent || isProcessing}
            className="h-11 px-4 rounded-xl bg-blue-600 text-white text-sm inline-flex items-center gap-2 disabled:opacity-60"
          >
            <Send className="h-4 w-4" />
            发送
          </button>
        </div>
      </div>

      {showSettings && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-slate-200">
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">模型设置</h3>
                  <p className="text-xs text-slate-500 mt-1">配置 OpenAI 兼容接口，信息仅保存在浏览器</p>
                </div>
                <button
                  onClick={() => setShowSettings(false)}
                  className="rounded-full p-2 hover:bg-slate-100 text-slate-500"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3">
                <label className="text-sm text-slate-700">
                  Endpoint
                  <input
                    type="text"
                    value={settings.endpoint}
                    onChange={(e) => setSettings((prev) => ({ ...prev, endpoint: e.target.value }))}
                    placeholder="https://api.openai.com/v1"
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="text-sm text-slate-700">
                  API Key
                  <input
                    type="password"
                    value={settings.api_key}
                    onChange={(e) => setSettings((prev) => ({ ...prev, api_key: e.target.value }))}
                    placeholder="sk-..."
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="text-sm text-slate-700">
                  模型
                  <div className="flex gap-2 mt-1">
                    <input
                      list="agent-models"
                      type="text"
                      value={settings.model}
                      onChange={(e) => setSettings((prev) => ({ ...prev, model: e.target.value }))}
                      placeholder="gpt-4o-mini / deepseek..."
                      className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                    <button
                      onClick={() => loadModels(settings.endpoint, settings.api_key)}
                      disabled={!settings.endpoint || !settings.api_key || isLoadingModels}
                      className="px-3 py-2 rounded-lg border border-slate-200 text-sm hover:bg-slate-50 disabled:opacity-60"
                      type="button"
                    >
                      {isLoadingModels ? "加载..." : "刷新模型"}
                    </button>
                  </div>
                  <datalist id="agent-models">
                    {availableModels.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </datalist>
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowSettings(false)}
                  className="px-4 py-2 rounded-lg border border-slate-200 text-sm hover:bg-slate-50"
                >
                  取消
                </button>
                <button
                  onClick={saveSettings}
                  className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700"
                >
                  保存
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
