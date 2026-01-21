"use client"

import * as React from "react"
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message"
import { Bot, User } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import ReactMarkdown from "react-markdown"

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
    showAvatars?: boolean
}

export function ChatList({
    messages,
    isLoading,
    showTypingIndicator = true,
    showAvatars = true
}: ChatListProps) {
    const bottomRef = React.useRef<HTMLDivElement>(null)

    React.useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages])

    if (messages.length === 0) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">

                <div>
                    <h3 className="text-lg font-semibold text-white">开始对话吧~</h3>
                    <p className="mt-2 text-sm text-white/60">
                        向 AI 提问，获取智能建议
                    </p>
                </div>
            </div>
        )
    }

    return (
        <div className="flex flex-col gap-6">
            {messages.map((message, index) => (
                <Message
                    key={message.id || index}
                    from={message.role === "user" ? "user" : "assistant"}
                    className={showAvatars ? undefined : "gap-0"}
                >
                    {showAvatars && (
                        <Avatar className="h-8 w-8 rounded-lg border border-white/10">
                            <AvatarFallback className={message.role === "user" ? "bg-blue-500 rounded-lg" : "bg-neutral-800 rounded-lg"}>
                                {message.role === "user" ? (
                                    <User className="h-4 w-4 text-white" />
                                ) : (
                                    <Bot className="h-4 w-4 text-white" />
                                )}
                            </AvatarFallback>
                        </Avatar>
                    )}
                    <MessageContent>
                        <MessageResponse>
                            {message.role === "user" ? (
                                <div className="rounded-2xl rounded-tr-sm bg-neutral-800 px-4 py-3 text-white shadow-lg">
                                    {message.content}
                                </div>
                            ) : (
                                message.metadata?.type === "thinking" ? (
                                    <div className="rounded-2xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white/80">
                                        <div className="mb-1 text-xs text-white/50">思考</div>
                                        <div className="whitespace-pre-wrap leading-6">{message.content}</div>
                                    </div>
                                ) : (
                                    <div className="prose prose-invert prose-sm max-w-none">
                                        <ReactMarkdown
                                            components={{
                                                p: ({ children }) => <p className="mb-4 leading-7 text-white/90">{children}</p>,
                                                ul: ({ children }) => <ul className="mb-4 ml-6 list-disc text-white/90">{children}</ul>,
                                                ol: ({ children }) => <ol className="mb-4 ml-6 list-decimal text-white/90">{children}</ol>,
                                                li: ({ children }) => <li className="mb-1">{children}</li>,
                                                code: ({ children, className }) => {
                                                    const isInline = !className
                                                    return isInline ? (
                                                        <code className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-sm text-emerald-400">
                                                            {children}
                                                        </code>
                                                    ) : (
                                                        <code className="block rounded-lg bg-black/50 p-4 font-mono text-sm text-white/90">
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
                                )
                            )}
                        </MessageResponse>
                    </MessageContent>
                </Message>
            ))}

            {isLoading && showTypingIndicator && (
                <Message from="assistant">
                    {showAvatars && (
                        <Avatar className="h-8 w-8 rounded-lg border border-white/10">
                            <AvatarFallback className="bg-neutral-800 rounded-lg">
                                <Bot className="h-4 w-4 text-white" />
                            </AvatarFallback>
                        </Avatar>
                    )}
                    <MessageContent>
                        <div className="flex items-center gap-2 text-white/60">
                            <div className="flex gap-1">
                                <div className="h-2 w-2 animate-bounce rounded-full bg-white/40 [animation-delay:-0.3s]"></div>
                                <div className="h-2 w-2 animate-bounce rounded-full bg-white/40 [animation-delay:-0.15s]"></div>
                                <div className="h-2 w-2 animate-bounce rounded-full bg-white/40"></div>
                            </div>
                            <span className="text-sm">正在思考</span>
                        </div>
                    </MessageContent>
                </Message>
            )}

            <div ref={bottomRef} />
        </div>
    )
}
