import * as React from "react"
import { SendHorizontal, StopCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

interface ChatInputProps {
    isLoading?: boolean
    onSubmit: (value: string) => void
    input: string
    setInput: (value: string) => void
    disabled?: boolean
    placeholder?: string
    onStop?: () => void
    showStopButton?: boolean
}

export function ChatInput({ isLoading, onSubmit, input, setInput, disabled, placeholder, onStop, showStopButton }: ChatInputProps) {
    const textareaRef = React.useRef<HTMLTextAreaElement>(null)

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.isComposing) {
            return
        }
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            if (input?.trim() && !isLoading && !disabled) {
                onSubmit(input)
            }
        }
    }

    // Auto-resize textarea
    React.useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto"
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
        }
    }, [input])

    return (
        <div className="relative mx-auto w-full max-w-3xl p-4">
            <div className={`relative flex flex-col rounded-3xl border border-white/10 bg-neutral-900/50 shadow-2xl backdrop-blur-xl transition-all focus-within:border-white/20 focus-within:bg-neutral-900/80 ${disabled ? 'opacity-50' : ''}`}>
                {/* Input Area */}
                <div className="relative px-4 pt-4">
                    <Textarea
                        ref={textareaRef}
                        tabIndex={0}
                        rows={1}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={placeholder || (disabled ? "AI 服务未连接" : "输入您的问题...")}
                        spellCheck={false}
                        disabled={disabled}
                        className="min-h-[60px] w-full resize-none border-none bg-transparent px-0 py-2 text-base text-white placeholder:text-white/30 focus-visible:ring-0 scrollbar-hide"
                        style={{ maxHeight: "200px" }}
                    />
                </div>

                {/* Toolbar */}
                <div className="flex items-center justify-end px-2 pb-2">
                    <div className="flex items-center gap-2">
                        {/* Stop Button - 只在流式执行时显示 */}
                        {showStopButton && onStop && (
                            <Button
                                size="icon"
                                variant="destructive"
                                className="h-8 w-8 rounded-full bg-red-600 hover:bg-red-700 text-white"
                                onClick={onStop}
                            >
                                <StopCircle className="h-4 w-4" />
                                <span className="sr-only">停止</span>
                            </Button>
                        )}

                        {/* Send Button */}
                        <Button
                            size="icon"
                            className={`h-8 w-8 rounded-full transition-all ${input?.trim()
                                ? "bg-white text-black hover:bg-white/90"
                                : "bg-white/10 text-white/30 hover:bg-white/20"
                                }`}
                            onClick={() => {
                                if (input?.trim() && !isLoading && !disabled) {
                                    onSubmit(input)
                                }
                            }}
                            disabled={isLoading || !input?.trim() || disabled}
                        >
                            <SendHorizontal className="h-4 w-4" />
                            <span className="sr-only">发送</span>
                        </Button>
                    </div>
                </div>
            </div>

            {/* Footer Text */}
            <div className="mt-2 text-center text-xs text-white/20">
                AI 生成的内容可能不准确，请核对重要信息。
            </div>
        </div>
    )
}
