"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"

interface ConversationContextValue {
    scrollToBottom: () => void
}

const ConversationContext = React.createContext<ConversationContextValue | null>(null)

export function Conversation({ children, className }: { children: React.ReactNode; className?: string }) {
    const scrollRef = React.useRef<HTMLDivElement>(null)

    const scrollToBottom = React.useCallback(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [])

    return (
        <ConversationContext.Provider value={{ scrollToBottom }}>
            <div className={cn("flex flex-col h-full", className)}>
                {children}
            </div>
        </ConversationContext.Provider>
    )
}

export function ConversationContent({ children }: { children: React.ReactNode }) {
    return (
        <ScrollArea className="flex-1 p-4">
            <div className="flex flex-col gap-4">
                {children}
            </div>
        </ScrollArea>
    )
}

export function ConversationScrollButton() {
    const context = React.useContext(ConversationContext)

    return (
        <button
            onClick={() => context?.scrollToBottom()}
            className="absolute bottom-20 right-4 rounded-full bg-primary p-2 shadow-lg opacity-0 pointer-events-none"
        >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M12 5v14M19 12l-7 7-7-7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        </button>
    )
}
