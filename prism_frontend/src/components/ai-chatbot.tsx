import React, { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { MessageCircle, X, Send, CheckCircle, AlertCircle, Loader, ChevronDown } from "lucide-react"
import { AIChatMessageList } from "./ai-chat-message"
import { AIQuickCommandPalette } from "./ai-quick-command-palette"
import { AIProviderSetupDialog } from "./ai-provider-setup-dialog"
import { AIProviderSelector } from "./ai-provider-selector"

interface AIMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  metadata?: {
    model?: string
    provider?: string
    executionTime?: number
    tokensUsed?: number
  }
}

interface AIProvider {
  name: string
  models_count: number
}

interface AIModel {
  id: string
  model_id: string
  name: string
  provider: string
  contextWindow?: number
  maxTokens?: number
  speed?: "fast" | "medium" | "slow"
}

export function AIChatBot() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<AIMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [showSettings, setShowSettings] = useState(true)

  const [currentProvider, setCurrentProvider] = useState<string | null>(null)
  const [currentModel, setCurrentModel] = useState<string | null>(null)
  const [providers, setProviders] = useState<Record<string, AIProvider>>({})
  const [modelsByProvider, setModelsByProvider] = useState<Record<string, AIModel[]>>({})

  const [healthStatus, setHealthStatus] = useState<Record<string, any>>({})
  const [isHealthChecking, setIsHealthChecking] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (isOpen) {
      loadModels()
    }
  }, [isOpen])

  const loadModels = async () => {
    try {
      const response = await fetch("/api/ai/models")
      if (response.ok) {
        const data = await response.json()
        setProviders(data.providers || {})

        const modelsByProv: Record<string, AIModel[]> = {}
        if (data.providers) {
          for (const [providerName, providerData] of Object.entries(data.providers)) {
            const providerModels = (providerData as any).models || []
            modelsByProv[providerName] = providerModels
          }
        }

        setModelsByProvider(modelsByProv)
        setCurrentProvider(data.current_provider)
        setCurrentModel(data.current_model)
      }
    } catch (error) {
      console.error("Failed to load AI models:", error)
    }
  }

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading || !currentProvider) return

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    const messageText = input
    setInput("")
    setIsLoading(true)

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          context: messages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          role: "default",
        }),
      })

      if (response.ok) {
        const data = await response.json()
        const assistantMessage: AIMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.content || "No response",
          timestamp: new Date(),
          metadata: {
            model: data.model,
            provider: data.provider,
            tokensUsed: data.tokens_used,
          },
        }
        setMessages((prev) => [...prev, assistantMessage])
      } else {
        const errorData = await response.json()
        const errorMessage: AIMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: `❌ 错误: ${errorData.message || "请求失败"}`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, errorMessage])
      }
    } catch (error) {
      console.error("Failed to send message:", error)
      const errorMessage: AIMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "❌ 网络错误，请检查连接",
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSwitchProvider = async (provider: string) => {
    try {
      const response = await fetch("/api/ai/switch-provider", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider }),
      })

      if (response.ok) {
        await loadModels()
      }
    } catch (error) {
      console.error("Failed to switch provider:", error)
      alert("切换提供商失败")
    }
  }

  const handleSwitchModel = async (model: string) => {
    try {
      const response = await fetch("/api/ai/switch-model", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      })

      if (response.ok) {
        setCurrentModel(model)
      } else {
        alert("切换模型失败")
      }
    } catch (error) {
      console.error("Failed to switch model:", error)
      alert("切换模型失败")
    }
  }

  const handleAddProvider = async (provider: string, apiKey: string) => {
    try {
      const response = await fetch("/api/ai/add-provider", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          api_key: apiKey,
        }),
      })

      if (response.ok) {
        await loadModels()
        return true
      } else {
        const errorData = await response.json()
        alert(`添加失败: ${errorData.message}`)
        return false
      }
    } catch (error) {
      console.error("Failed to add provider:", error)
      alert("添加提供商失败")
      return false
    }
  }

  const handleHealthCheck = async () => {
    setIsHealthChecking(true)
    try {
      const response = await fetch("/api/ai/health-check", {
        method: "POST",
      })

      if (response.ok) {
        const data = await response.json()
        setHealthStatus(data.health_check_results || {})
      }
    } catch (error) {
      console.error("Failed to perform health check:", error)
    } finally {
      setIsHealthChecking(false)
    }
  }

  const handleQuickCommand = async (command: string) => {
    setInput(command)
  }

  const hasProviders = Object.keys(providers).length > 0

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg hover:shadow-xl transition-all duration-300 flex items-center justify-center text-white hover:scale-110"
        title="AI 聊天助手"
      >
        {isOpen ? (
          <X className="h-6 w-6" />
        ) : (
          <MessageCircle className="h-6 w-6" />
        )}
      </button>

      {isOpen && (
        <div className="fixed bottom-24 right-6 z-40 w-96 max-w-[calc(100vw-2rem)] h-[700px] flex flex-col rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-white/10 shadow-2xl overflow-hidden">
          {/* 头部 */}
          <div className="flex items-center justify-between p-4 border-b border-white/10 bg-slate-900/80 backdrop-blur">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <div>
                <h3 className="text-sm font-semibold text-white">AI 助手</h3>
                {currentModel && (
                  <p className="text-xs text-white/60 mt-0.5">
                    {currentProvider} · {currentModel.split("/").pop() || currentModel}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="text-white/60 hover:text-white transition p-1"
              title={showSettings ? "隐藏设置" : "显示设置"}
            >
              <ChevronDown className={`h-4 w-4 transition-transform ${showSettings ? "rotate-180" : ""}`} />
            </button>
          </div>

          {/* 设置面板 */}
          {showSettings && (
            <div className="border-b border-white/10 p-4 bg-white/5 backdrop-blur overflow-y-auto flex-shrink-0 space-y-4">
              {/* AI 提供商检测和选择 */}
              <AIProviderSelector />
            </div>
          )}

          {/* 消息区域 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-slate-900 to-slate-900/50">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <p className="text-2xl mb-2">
                  {!hasProviders ? "⚙️" : "👋"}
                </p>
                <p className="text-sm text-white/60 mb-4">
                  {!hasProviders ? "请先配置 AI 提供商" : "开始对话"}
                </p>
                {hasProviders && (
                  <>
                    <div className="w-full max-w-xs">
                      <AIQuickCommandPalette onCommandSelect={handleQuickCommand} isLoading={isLoading} />
                    </div>
                    <p className="text-xs text-white/40 mt-3">或输入任意问题开始对话</p>
                  </>
                )}
              </div>
            ) : (
              <>
                <AIChatMessageList
                  messages={messages}
                  isLoading={isLoading}
                  onCopy={(content) => {
                    navigator.clipboard.writeText(content)
                    alert("已复制到剪贴板")
                  }}
                  emptyMessage={null}
                />
                {hasProviders && !isLoading && messages.length > 0 && (
                  <div className="pt-2">
                    <AIQuickCommandPalette onCommandSelect={handleQuickCommand} isLoading={isLoading} />
                  </div>
                )}
              </>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* 输入区域 */}
          <div className="border-t border-white/10 p-4 bg-slate-900/80 backdrop-blur flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.isComposing) return
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    handleSendMessage()
                  }
                }}
                placeholder={hasProviders ? "输入消息或快捷命令..." : "请先配置 AI..."}
                className="bg-white/10 border-white/20 text-white placeholder:text-white/40 h-10 text-sm"
                disabled={isLoading || !currentProvider}
              />
              <Button
                onClick={handleSendMessage}
                disabled={isLoading || !currentProvider || !input.trim()}
                className="px-3 h-10 bg-blue-600 hover:bg-blue-700"
                size="sm"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
