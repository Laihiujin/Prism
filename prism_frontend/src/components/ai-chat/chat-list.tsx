"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import { User } from "lucide-react"

import { HermesLogoIcon } from "@/components/hermes-logo-icon"

interface UIMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  metadata?: Record<string, any>
}

interface ChatListProps {
  messages: UIMessage[]
  isLoading?: boolean
  showTypingIndicator?: boolean
}

export function ChatList({
  messages,
  isLoading,
  showTypingIndicator = true,
}: ChatListProps) {
  const bottomRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isLoading])

  if (messages.length === 0) {
    return (
      <div className="flex min-h-[420px] flex-col items-center justify-center gap-5 rounded-[28px] border border-dashed border-white/10 bg-black px-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-3xl border border-white/10 bg-white/5 text-white">
          <HermesLogoIcon className="h-7 w-7" />
        </div>
        <div className="space-y-2">
          <h3 className="text-xl font-semibold text-white">Hermes 已就绪</h3>
          <p className="max-w-xl text-sm leading-7 text-white/60">
            直接描述目标、脚本、接口或本地文件路径。Hermes 会按当前系统设置页保存的模型提供商执行。
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {messages.map((message, index) => {
        const isUser = message.role === "user"
        const isThinking = message.metadata?.type === "thinking"

        return (
          <div
            key={message.id || index}
            className={`flex items-start gap-3 ${isUser ? "justify-end" : "justify-start"}`}
          >
            {!isUser && (
              <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-white">
                <HermesLogoIcon className={`h-4 w-4 ${isThinking ? "opacity-80" : ""}`} />
              </div>
            )}

            <div
              className={`max-w-[min(820px,82%)] rounded-[26px] border px-5 py-4 shadow-[0_18px_60px_-40px_rgba(0,0,0,0.9)] ${
                isUser
                    ? "rounded-tr-md border-white/10 bg-white text-neutral-950"
                    : isThinking
                    ? "rounded-tl-md border-white/10 bg-neutral-950 text-white"
                    : "rounded-tl-md border-white/10 bg-black text-white"
              }`}
            >
              {!isUser && (
                <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-white/45">
                  {isThinking ? "Reasoning" : "Hermes"}
                </div>
              )}

              {isUser ? (
                <div className="whitespace-pre-wrap text-sm leading-7">{message.content}</div>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-4 leading-7 text-inherit">{children}</p>,
                      ul: ({ children }) => <ul className="mb-4 ml-6 list-disc text-inherit">{children}</ul>,
                      ol: ({ children }) => <ol className="mb-4 ml-6 list-decimal text-inherit">{children}</ol>,
                      li: ({ children }) => <li className="mb-1">{children}</li>,
                      code: ({ children, className }) => {
                        const isInline = !className
                        return isInline ? (
                          <code className="rounded-lg bg-white/10 px-1.5 py-0.5 font-mono text-[13px] text-white">
                            {children}
                          </code>
                        ) : (
                          <code className="block rounded-2xl border border-white/10 bg-black/40 p-4 font-mono text-[13px] text-white/90">
                            {children}
                          </code>
                        )
                      },
                      pre: ({ children }) => <pre className="mb-4 overflow-x-auto">{children}</pre>,
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>

            {isUser && (
              <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-neutral-800 bg-neutral-900 text-white">
                <User className="h-4 w-4" />
              </div>
            )}
          </div>
        )
      })}

      {isLoading && showTypingIndicator && (
        <div className="flex items-start gap-3">
          <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-white">
            <HermesLogoIcon className="h-4 w-4" />
          </div>
          <div className="rounded-[26px] rounded-tl-md border border-white/10 bg-black px-5 py-4 text-white shadow-[0_18px_60px_-40px_rgba(0,0,0,0.9)]">
            <div className="mb-2 text-[11px] uppercase tracking-[0.28em] text-white/45">Hermes</div>
            <div className="flex items-center gap-3 text-sm text-white/70">
              <div className="flex gap-1">
                <div className="h-2 w-2 animate-bounce rounded-full bg-white [animation-delay:-0.3s]" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-white/80 [animation-delay:-0.15s]" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-white/65" />
              </div>
              正在规划下一步
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
