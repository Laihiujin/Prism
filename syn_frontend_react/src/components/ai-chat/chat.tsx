"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { ChatList } from "./chat-list"
import { ChatInput } from "./chat-input"
import { ModelSettingsDialog } from "./model-settings-dialog"
import { Link2, Settings, MessageSquare } from "lucide-react"
import { HermesLogoIcon } from "@/components/hermes-logo-icon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

export function Chat() {
    const router = useRouter()
    const [mode, setMode] = React.useState<"chat" | "agent">("chat")
    const [messages, setMessages] = React.useState<any[]>([
        {
            id: "welcome",
            role: "assistant",
            content: "你好",
        }
    ])
    const [input, setInput] = React.useState("")
    const [isLoading, setIsLoading] = React.useState(false)
    const [settingsOpen, setSettingsOpen] = React.useState(false)
    const [isConnected, setIsConnected] = React.useState(false)

    // Check connection status
    React.useEffect(() => {
        const checkStatus = async () => {
            try {
                const response = await fetch("/api/v1/ai/status")
                const data = await response.json()
                setIsConnected(data.connected || false)
            } catch (error) {
                console.error("Failed to check AI status:", error)
                setIsConnected(false)
            }
        }

        checkStatus()
        // Check every 30s
        const interval = setInterval(checkStatus, 30000)
        return () => clearInterval(interval)
    }, [])

    // 鍒囨崲妯″紡鏃舵竻绌烘秷鎭紙鍙€夛紝鎴栬€呬繚鐣欏巻鍙诧級
    const handleModeChange = (newMode: string) => {
        setMode(newMode as "chat" | "agent")
        if (newMode === "agent") {
            setMessages([
                {
                    id: "agent-welcome",
                    role: "assistant",
                    content: "馃 宸插垏鎹㈠埌 Agent 妯″紡銆俓n\n鎴戝彲浠ュ府浣犳墽琛屽鏉傜殑鑷姩鍖栦换鍔★紒"
                }
            ])
        } else {
            setMessages([
                {
                    id: "chat-welcome",
                    role: "assistant",
                    content: "馃挰 宸插垏鎹㈠洖瀵硅瘽妯″紡銆傛湁浠€涔堝彲浠ュ府浣犵殑鍚楋紵"
                }
            ])
        }
    }

    const handleSubmit = async (value: string) => {
        if (!value.trim() || isLoading) return

        const userMsg = { id: Date.now().toString(), role: "user", content: value }
        setMessages(prev => [...prev, userMsg])
        setInput("")
        setIsLoading(true)

        try {
            if (mode === "chat") {
                // Chat 妯″紡锛氭祦寮忓搷搴?
                const apiMessages = [...messages, userMsg].map(m => ({
                    role: m.role,
                    content: m.content
                }))

                const response = await fetch("/api/v1/ai/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ messages: apiMessages })
                })

                if (!response.ok) throw new Error(`API Error: ${response.statusText}`)
                if (!response.body) throw new Error("No response body")

                const assistantMsgId = (Date.now() + 1).toString()
                const assistantMsg = { id: assistantMsgId, role: "assistant", content: "" }
                setMessages(prev => [...prev, assistantMsg])

                const reader = response.body.getReader()
                const decoder = new TextDecoder()
                let done = false

                while (!done) {
                    const { value, done: doneReading } = await reader.read()
                    done = doneReading
                    if (value) {
                        const chunk = decoder.decode(value, { stream: true })
                        setMessages(prev => prev.map(m =>
                            m.id === assistantMsgId
                                ? { ...m, content: m.content + chunk }
                                : m
                        ))
                    }
                }
            } else {
                // Agent 妯″紡锛歄penManus (闈炴祦寮忥紝鏃犲崰浣嶆皵娉?
                const response = await fetch("/api/v1/agent/openclaw-run", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        goal: value,
                        context: {}
                    })
                })

                // 妫€鏌?HTTP 鐘舵€?
                if (!response.ok) {
                    const errorText = await response.text()
                    throw new Error(`HTTP ${response.status}: ${errorText.substring(0, 200)}`)
                }

                // 灏濊瘯瑙ｆ瀽 JSON
                let result
                try {
                    result = await response.json()
                } catch (jsonError) {
                    const text = await response.text()
                    throw new Error(`鏈嶅姟鍣ㄨ繑鍥炰簡闈?JSON 鍝嶅簲: ${text.substring(0, 200)}`)
                }

                if (result.success && result.data) {
                    const data = result.data
                    let resultText = `**缁撴灉**: ${data.result}\n\n`

                    if (data.steps && Array.isArray(data.steps)) {
                        data.steps.forEach((step: any, index: number) => {
                            resultText += `${index + 1}. ${step.tool || 'Action'}: ${step.thought || ''}\n`
                        })
                    }

                    setMessages(prev => [...prev, {
                        id: (Date.now() + 1).toString(),
                        role: "assistant",
                        content: resultText
                    }])
                } else {
                    const errorMsg = result.data?.error || result.error || "鏈煡閿欒"
                    setMessages(prev => [...prev, {
                        id: (Date.now() + 1).toString(),
                        role: "assistant",
                        content: `鉂?**浠诲姟鎵ц澶辫触**\n\n${errorMsg}`
                    }])
                }
            }
        } catch (error) {
            console.error("鉂?Failed to send message:", error)
            const errorMessage = error instanceof Error ? error.message : String(error)
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: "assistant",
                content: `鉂?鍙戦€佸け璐? ${errorMessage}`
            }])
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="flex h-[85vh] w-full flex-col overflow-hidden rounded-3xl border border-white/10 bg-black shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/5 bg-neutral-900/50 px-6 py-4 backdrop-blur-md">
                <div className="flex items-center gap-4">
                    <div>
                        <h2 className="text-base font-bold text-white">SynapseAutomation </h2>
                        <p className="text-xs font-medium text-white/50">Ai</p>
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
                        閰嶇疆
                    </Button>
                    <Badge
                        variant="outline"
                        className={`gap-1 text-xs font-normal ${isConnected
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                            : "border-white/10 bg-white/5 text-white/40"
                            }`}
                    >
                        <HermesLogoIcon className="h-3 w-3" />
                        {isConnected ? "鍦ㄧ嚎" : "绂荤嚎"}
                    </Badge>
                </div>
            </div>

            {/* Mode Switch */}
            <div className="border-b border-white/5 bg-neutral-900/40 px-6 py-3 flex justify-center">
                <Tabs value={mode} onValueChange={handleModeChange}>
                    <TabsList className="grid w-[200px] grid-cols-2 bg-white/5">
                        <TabsTrigger value="chat" className="text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                            <MessageSquare className="mr-2 h-3 w-3" />
                            瀵硅瘽
                        </TabsTrigger>
                        <TabsTrigger value="agent" className="text-xs data-[state=active]:bg-purple-600 data-[state=active]:text-white">
                            <HermesLogoIcon className="mr-2 h-3 w-3" />
                            Agent
                        </TabsTrigger>
                    </TabsList>
                </Tabs>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto bg-gradient-to-b from-black to-neutral-950 p-4 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
                <div className="mx-auto max-w-3xl">
                    <ChatList
                        messages={messages}
                        isLoading={false}
                        showTypingIndicator={false}
                        showAvatars={false}
                    />
                </div>
            </div>

            {/* Input Area */}
            <div className="bg-black pb-4 pt-2">
                <ChatInput
                    isLoading={isLoading}
                    onSubmit={handleSubmit}
                    input={input}
                    setInput={setInput}
                    disabled={!isConnected}
                    placeholder={mode === "agent" ? "鎻忚堪浣犵殑浠诲姟锛屼緥濡傦細甯垜鍒嗘瀽鏈€杩戠殑鍙戝竷鏁版嵁..." : "杈撳叆娑堟伅..."}
                />
            </div>

            <ModelSettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
        </div>
    )
}

