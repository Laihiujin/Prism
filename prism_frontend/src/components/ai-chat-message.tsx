import React from "react"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Copy, Check, Download, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useState } from "react"

interface ChatMessage {
  role: "user" | "assistant"
  content: string
  timestamp?: Date
  metadata?: {
    model?: string
    provider?: string
    executionTime?: number
    tokensUsed?: number
  }
}

interface AIChatMessageProps {
  message: ChatMessage
  isLoading?: boolean
  onCopy?: (content: string) => void
  onRetry?: () => void
}

export function AIChatMessage({
  message,
  isLoading = false,
  onCopy,
  onRetry,
}: AIChatMessageProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (onCopy) {
      onCopy(message.content)
    } else {
      navigator.clipboard.writeText(message.content)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const isUser = message.role === "user"

  return (
    <div className={cn("flex gap-3 mb-4", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-xs lg:max-w-md xl:max-w-lg", isUser ? "order-2" : "order-1")}>
        <Card
          className={cn(
            "p-3 rounded-lg",
            isUser
              ? "bg-white text-foreground border-white/17"
              : "bg-black border-border/80 text-foreground backdrop-blur-sm"
          )}
        >
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            {isLoading ? (
              <span className="flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full bg-foreground/60 animate-bounce" />
                <span className="inline-block h-2 w-2 rounded-full bg-foreground/60 animate-bounce delay-100" />
                <span className="inline-block h-2 w-2 rounded-full bg-foreground/60 animate-bounce delay-200" />
              </span>
            ) : (
              message.content
            )}
          </p>
        </Card>

        {/* 消息元数据 */}
        {!isUser && message.metadata && (
          <div className="flex flex-wrap gap-2 mt-2">
            {message.metadata.provider && (
              <Badge variant="secondary" className="text-xs bg-black text-muted-foreground">
                {message.metadata.provider}
              </Badge>
            )}
            {message.metadata.model && (
              <Badge variant="secondary" className="text-xs bg-black text-muted-foreground">
                {message.metadata.model}
              </Badge>
            )}
            {message.metadata.executionTime && (
              <Badge variant="secondary" className="text-xs bg-black text-muted-foreground">
                ⏱ {message.metadata.executionTime.toFixed(2)}s
              </Badge>
            )}
            {message.metadata.tokensUsed && (
              <Badge variant="secondary" className="text-xs bg-black text-muted-foreground">
                🔢 {message.metadata.tokensUsed} tokens
              </Badge>
            )}
          </div>
        )}

        {/* 消息操作按钮 */}
        {!isLoading && (
          <div className="flex gap-1 mt-2 opacity-0 hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-accent/50"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="h-3 w-3" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>
            {onRetry && !isUser && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-accent/50"
                onClick={onRetry}
              >
                <RotateCcw className="h-3 w-3" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-accent/50"
              onClick={() => {
                const link = document.createElement("a")
                link.href = `data:text/plain;charset=utf-8,${encodeURIComponent(message.content)}`
                link.download = `message-${Date.now()}.txt`
                link.click()
              }}
            >
              <Download className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="h-8 w-8 rounded-full bg-white flex items-center justify-center text-foreground text-sm font-semibold flex-shrink-0">
          U
        </div>
      )}

      {/* AI 头像 */}
      {!isUser && (
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-white to-white flex items-center justify-center text-foreground text-sm font-semibold flex-shrink-0">
          AI
        </div>
      )}
    </div>
  )
}

interface AIChatMessageListProps {
  messages: ChatMessage[]
  isLoading?: boolean
  onCopy?: (content: string) => void
  onRetry?: (index: number) => void
  emptyMessage?: React.ReactNode
}

export function AIChatMessageList({
  messages,
  isLoading = false,
  onCopy,
  onRetry,
  emptyMessage,
}: AIChatMessageListProps) {
  const messagesEndRef = React.useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  React.useEffect(() => {
    scrollToBottom()
  }, [messages])

  return (
    <div className="flex flex-col gap-2">
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-muted-foreground">
          {emptyMessage || (
            <div className="text-center">
              <p className="text-lg font-semibold mb-2">👋 开始对话</p>
              <p className="text-sm">请输入消息或配置 AI 提供商开始使用</p>
            </div>
          )}
        </div>
      ) : (
        messages.map((message, index) => (
          <AIChatMessage
            key={index}
            message={message}
            isLoading={isLoading && index === messages.length - 1}
            onCopy={onCopy}
            onRetry={() => onRetry?.(index)}
          />
        ))
      )}
      <div ref={messagesEndRef} />
    </div>
  )
}
