"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { Loader2, Send, Code, CheckCircle2, XCircle, Wrench } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/env"

interface ToolCall {
    name: string
    arguments: Record<string, any>
    result: any
}

export function FunctionCallingTester() {
    const { toast } = useToast()
    const [loading, setLoading] = useState(false)
    const [userInput, setUserInput] = useState("")
    const [result, setResult] = useState<any>(null)
    const [tools, setTools] = useState<any[]>([])
    const [toolsLoading, setToolsLoading] = useState(false)

    // 加载可用工具
    const loadTools = async () => {
        setToolsLoading(true)
        try {
            const response = await fetch(`${API_ENDPOINTS.base}/api/v1/ai/function-calling/tools`)
            const data = await response.json()

            if (data.status === "success") {
                setTools(data.data.tools)
            }
        } catch (error) {
            console.error("加载工具列表失败:", error)
        } finally {
            setToolsLoading(false)
        }
    }

    // 执行 Function Calling
    const handleSubmit = async () => {
        if (!userInput.trim()) {
            toast({
                title: "请输入任务",
                variant: "destructive"
            })
            return
        }

        setLoading(true)
        setResult(null)

        try {
            const response = await fetch(`${API_ENDPOINTS.base}/api/v1/ai/function-calling`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    messages: [
                        { role: "user", content: userInput }
                    ],
                    max_iterations: 3,
                    auto_execute: true
                })
            })

            const data = await response.json()

            if (data.status === "success") {
                setResult(data.data)

                if (data.data.success) {
                    toast({
                        title: "✅ 执行成功",
                        description: `共执行 ${data.data.iterations} 轮迭代`
                    })
                } else {
                    toast({
                        title: "⚠️ 执行失败",
                        description: data.data.message,
                        variant: "destructive"
                    })
                }
            } else {
                throw new Error(data.detail || "执行失败")
            }
        } catch (error: any) {
            toast({
                title: "请求失败",
                description: error.message,
                variant: "destructive"
            })
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="space-y-6">
            {/* 输入区域 */}
            <Card className="bg-white/5 border-white/10">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Code className="w-5 h-5 text-primary" />
                        Function Calling 测试
                    </CardTitle>
                    <CardDescription className="text-white/60">
                        输入任务描述，AI 将自动调用相应的工具函数完成任务
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Textarea
                        value={userInput}
                        onChange={(e) => setUserInput(e.target.value)}
                        placeholder="例如：帮我列出所有抖音账号"
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/40 min-h-[100px]"
                    />

                    <div className="flex gap-3">
                        <Button
                            onClick={handleSubmit}
                            disabled={loading || !userInput.trim()}
                            className="flex-1"
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    执行中...
                                </>
                            ) : (
                                <>
                                    <Send className="w-4 h-4 mr-2" />
                                    执行任务
                                </>
                            )}
                        </Button>

                        <Button
                            onClick={loadTools}
                            disabled={toolsLoading}
                            variant="outline"
                            className="bg-white/5 border-white/10"
                        >
                            {toolsLoading ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                                <Wrench className="w-4 h-4 mr-2" />
                            )}
                            查看工具
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* 可用工具列表 */}
            {tools.length > 0 && (
                <Card className="bg-white/5 border-white/10">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Wrench className="w-4 h-4" />
                            可用工具 ({tools.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {tools.map((tool, index) => (
                            <div
                                key={index}
                                className="p-3 bg-white/5 rounded-lg border border-white/10"
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <Badge variant="outline" className="bg-primary/20 text-primary border-primary/30">
                                        {tool.name}
                                    </Badge>
                                </div>
                                <p className="text-sm text-white/60">{tool.description}</p>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}

            {/* 执行结果 */}
            {result && (
                <Card className="bg-white/5 border-white/10">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            {result.success ? (
                                <CheckCircle2 className="w-5 h-5 text-green-400" />
                            ) : (
                                <XCircle className="w-5 h-5 text-red-400" />
                            )}
                            执行结果
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* 状态信息 */}
                        <div className="flex items-center gap-4 text-sm text-white/70">
                            <Badge variant="outline" className={result.success ? "bg-green-500/20 text-green-400 border-green-500/30" : "bg-red-500/20 text-red-400 border-red-500/30"}>
                                {result.success ? "成功" : "失败"}
                            </Badge>
                            <span>迭代次数: {result.iterations}</span>
                            <span>工具调用: {result.tool_calls?.length || 0}</span>
                        </div>

                        {/* AI 回复 */}
                        {result.message && (
                            <div className="p-4 bg-white/5 rounded-lg border border-white/10">
                                <p className="text-sm text-white/60 mb-2">AI 回复：</p>
                                <p className="text-white whitespace-pre-wrap">{result.message}</p>
                            </div>
                        )}

                        {/* 工具调用记录 */}
                        {result.tool_calls && result.tool_calls.length > 0 && (
                            <div className="space-y-3">
                                <p className="text-sm text-white/60">工具调用记录：</p>
                                {result.tool_calls.map((call: ToolCall, index: number) => (
                                    <div
                                        key={index}
                                        className="p-4 bg-white/5 rounded-lg border border-white/10"
                                    >
                                        <div className="flex items-center gap-2 mb-2">
                                            <Badge variant="outline" className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                                                {index + 1}
                                            </Badge>
                                            <span className="font-mono text-sm text-primary">{call.name}</span>
                                        </div>

                                        {/* 参数 */}
                                        <div className="mb-2">
                                            <p className="text-xs text-white/60 mb-1">参数:</p>
                                            <pre className="text-xs bg-black/30 p-2 rounded overflow-x-auto">
                                                {JSON.stringify(call.arguments, null, 2)}
                                            </pre>
                                        </div>

                                        {/* 结果 */}
                                        <div>
                                            <p className="text-xs text-white/60 mb-1">结果:</p>
                                            <pre className="text-xs bg-black/30 p-2 rounded overflow-x-auto max-h-[200px] overflow-y-auto">
                                                {JSON.stringify(call.result, null, 2)}
                                            </pre>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            
        </div>
    )
}
