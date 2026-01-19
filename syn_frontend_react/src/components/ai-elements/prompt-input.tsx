"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"

export type PromptInputMessage = {
    text: string
    files?: File[]
}

interface PromptInputProps {
    onSubmit: (message: PromptInputMessage) => void
    children: React.ReactNode
    globalDrop?: boolean
    multiple?: boolean
    value?: string
    onValueChange?: (value: string) => void
}

const PromptInputContext = React.createContext<{
    files: File[]
    setFiles: (files: File[]) => void
    text: string
    setText: (text: string) => void
} | null>(null)

export function PromptInput({ onSubmit, children, globalDrop, multiple, value, onValueChange }: PromptInputProps) {
    const [files, setFiles] = React.useState<File[]>([])
    const [text, setText] = React.useState(value ?? "")

    React.useEffect(() => {
        if (value !== undefined) {
            setText(value)
        }
    }, [value])

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        const messageText = value !== undefined ? value : text
        onSubmit({ text: messageText, files })
        if (onValueChange) {
            onValueChange("")
        }
        setText("")
        setFiles([])
    }

    return (
        <PromptInputContext.Provider value={{ files, setFiles, text, setText }}>
            <form onSubmit={handleSubmit} className="space-y-2">
                {children}
            </form>
        </PromptInputContext.Provider>
    )
}

export function PromptInputHeader({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center gap-2">{children}</div>
}

export function PromptInputBody({ children }: { children: React.ReactNode }) {
    return <div className="flex-1">{children}</div>
}

export function PromptInputFooter({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center gap-2 justify-between">{children}</div>
}

export function PromptInputTextarea({
    value,
    onChange,
    placeholder,
    className
}: {
    value: string
    onChange: (e: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => void
    placeholder?: string
    className?: string
}) {
    return (
        <Textarea
            value={value}
            onChange={onChange}
            placeholder={placeholder}
            rows={3}
            className={cn("flex-1 min-h-[96px] resize-none", className)}
        />
    )
}

export function PromptInputSubmit({
    disabled,
    status
}: {
    disabled?: boolean
    status?: string
}) {
    return (
        <Button type="submit" disabled={disabled}>
            发送
        </Button>
    )
}

export function PromptInputTools({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center gap-2">{children}</div>
}

export function PromptInputButton({
    children,
    onClick,
    variant
}: {
    children: React.ReactNode
    onClick?: () => void
    variant?: "default" | "ghost"
}) {
    return (
        <Button type="button" variant={variant || "ghost"} size="sm" onClick={onClick}>
            {children}
        </Button>
    )
}

export function PromptInputAttachments({ children }: { children: (file: File) => React.ReactNode }) {
    return null
}

export function PromptInputAttachment({ data }: { data: File }) {
    return null
}

export function PromptInputActionMenu({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>
}

export function PromptInputActionMenuTrigger() {
    return <Button type="button" variant="ghost" size="sm">⋮</Button>
}

export function PromptInputActionMenuContent({ children }: { children: React.ReactNode }) {
    return <div className="absolute bottom-full mb-2">{children}</div>
}

export function PromptInputActionAddAttachments() {
    return <Button type="button" variant="ghost" size="sm">附件</Button>
}
