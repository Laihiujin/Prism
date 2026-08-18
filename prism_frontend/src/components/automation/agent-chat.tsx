"use client"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Send, Bot, User, Loader2, FileCode, CheckCircle2, Play, Eye } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"
import { API_ENDPOINTS } from "@/lib/env"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"

interface Message {
  role: "user" | "assistant" | "system"
  content: string
  timestamp: Date
  scriptData?: any
}

interface GeneratedScript {
  content: string
  plan_name: string
  description: string
}

export function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [context, setContext] = useState<any>(null)
  const [generatedScript, setGeneratedScript] = useState<GeneratedScript | null>(null)
  const [showScriptDialog, setShowScriptDialog] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  useEffect(() => {
    // 初始化：获取系统上下文
    fetchContext()

    // 添加欢迎消息
    setMessages([
      {
        role: "system",
        content: "欢迎使用AI智能自动化助手！我可以帮你：\n\n1. 生成智能发布计划\n2. 分析账号和素材情况\n3. 自动创建任务并执行\n\n请告诉我你想要做什么？",
        timestamp: new Date()
      }
    ])
  }, [])

  useEffect(() => {
    // 自动滚动到底部
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const fetchContext = async () => {
    try {
      const response = await fetch(`${API_ENDPOINTS.agentContext || 'http://localhost:7000/api/v1/agent/context'}`)
      const data = await response.json()
      if (data.success) {
        setContext(data.data)
      }
    } catch (error) {
      console.error("Failed to fetch context:", error)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      role: "user",
      content: input.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput("")
    setLoading(true)

    try {
      // 模拟AI响应（实际应该调用AI API）
      await simulateAIResponse(userMessage.content)
    } catch (error: any) {
      toast({
        title: "错误",
        description: error.message || "AI响应失败",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const simulateAIResponse = async (userInput: string) => {
    // 这是一个示例实现，实际应该调用AI API
    // 这里我们模拟生成一个发布计划

    await new Promise(resolve => setTimeout(resolve, 1500))

    const lowerInput = userInput.toLowerCase()

    if (lowerInput.includes("发布") || lowerInput.includes("计划") || lowerInput.includes("生成")) {
      // 生成发布计划
      const script = generateSampleScript(context)

      const assistantMessage: Message = {
        role: "assistant",
        content: `我已经为你生成了一个发布计划！\n\n**计划概览：**\n- 计划名称：${script.plan_name}\n- 任务数量：${JSON.parse(script.content).tasks.length} 个\n- 涉及账号：${getUniqueAccounts(JSON.parse(script.content)).length} 个\n\n点击下方按钮查看和执行计划。`,
        timestamp: new Date(),
        scriptData: script
      }

      setMessages(prev => [...prev, assistantMessage])
      setGeneratedScript(script)
    } else if (lowerInput.includes("账号") || lowerInput.includes("素材")) {
      // 展示上下文信息
      const assistantMessage: Message = {
        role: "assistant",
        content: `**系统状态概览：**\n\n📊 **账号统计：**\n- 总账号数：${context?.accounts?.length || 0}\n- 抖音账号：${context?.accounts?.filter((a: any) => a.platform === 'douyin').length || 0}\n- 快手账号：${context?.accounts?.filter((a: any) => a.platform === 'kuaishou').length || 0}\n- 小红书账号：${context?.accounts?.filter((a: any) => a.platform === 'xiaohongshu').length || 0}\n- 视频号账号：${context?.accounts?.filter((a: any) => a.platform === 'channels').length || 0}\n\n📹 **素材统计：**\n- 可用视频：${context?.videos?.length || 0} 个\n\n你想要做什么操作？`,
        timestamp: new Date()
      }

      setMessages(prev => [...prev, assistantMessage])
    } else {
      // 通用响应
      const assistantMessage: Message = {
        role: "assistant",
        content: `我可以帮你：\n\n1️⃣ **生成发布计划** - 说“帮我生成一个发布计划”\n2️⃣ **查看账号状态** - 说“查看账号情况”\n3️⃣ **智能分发** - 说“将最新10条视频分发到所有账号”\n\n请告诉我你想要做什么？`,
        timestamp: new Date()
      }

      setMessages(prev => [...prev, assistantMessage])
    }
  }

  const generateSampleScript = (ctx: any) => {
    const accounts = ctx?.accounts || []
    const availableAccounts = accounts.slice(0, Math.min(3, accounts.length))

    const plan = {
      plan_name: "AI生成的智能发布计划",
      version: "1.0",
      tasks: availableAccounts.map((account: any, index: number) => ({
        video_id: index + 1,
        account_id: account.id,
        platform: account.platform,
        title: `AI生成标题 #${index + 1} - ${account.platform}专属`,
        description: `这是为${account.platform}平台自动生成的视频描述`,
        tags: ["AI发布", account.platform],
        publish_at: "immediate",
        delay_range: [60, 180],
        strategy: {
          avoid_duplicate: true,
          platform_unique: true,
          random_interval: true
        }
      }))
    }

    return {
      content: JSON.stringify(plan, null, 2),
      plan_name: plan.plan_name,
      description: "AI自动生成的发布计划"
    }
  }

  const getUniqueAccounts = (plan: any) => {
    const accountIds = new Set(plan.tasks.map((t: any) => t.account_id))
    return Array.from(accountIds)
  }

  const handleViewScript = () => {
    if (generatedScript) {
      setShowScriptDialog(true)
    }
  }

  const handleSaveAndExecute = async (mode: "dry-run" | "execute") => {
    if (!generatedScript) return

    try {
      setLoading(true)

      // 1. 保存脚本
      const saveResponse = await fetch(`${API_ENDPOINTS.agentSaveScript || 'http://localhost:7000/api/v1/agent/save-script'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: `ai-plan-${Date.now()}.json`,
          content: generatedScript.content,
          script_type: "json",
          meta: {
            generated_by: "AI",
            plan_name: generatedScript.plan_name,
            description: generatedScript.description
          }
        })
      })

      const saveData = await saveResponse.json()
      if (!saveData.success) {
        throw new Error("保存脚本失败")
      }

      const scriptId = saveData.data.script_id

      // 2. 执行脚本
      const executeResponse = await fetch(`${API_ENDPOINTS.agentExecuteScript || 'http://localhost:7000/api/v1/agent/execute-script'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_id: scriptId,
          mode: mode,
          options: {
            priority: 5,
            validate_only: false
          }
        })
      })

      const executeData = await executeResponse.json()
      if (!executeData.success) {
        throw new Error("执行脚本失败")
      }

      const result = executeData.data

      toast({
        title: mode === "dry-run" ? "模拟执行成功" : "执行成功",
        description: `创建了 ${result.tasks_created} 个任务，批次ID: ${result.task_batch_id}`
      })

      // 添加成功消息
      const successMessage: Message = {
        role: "assistant",
        content: `✅ ${mode === "dry-run" ? "模拟执行" : "执行"}完成！\n\n**结果：**\n- 批次ID：${result.task_batch_id}\n- 创建任务：${result.tasks_created} 个\n- 预计耗时：${result.estimated_time}\n\n${mode === "execute" ? "任务已加入队列，正在执行中..." : "这是模拟执行，未创建真实任务。"}`,
        timestamp: new Date()
      }

      setMessages(prev => [...prev, successMessage])
      setShowScriptDialog(false)
      setGeneratedScript(null)

    } catch (error: any) {
      toast({
        title: "错误",
        description: error.message,
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* 主对话区 */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            AI助手对话
          </CardTitle>
          <CardDescription>
            与AI助手对话，自动生成发布计划
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 消息列表 */}
          <ScrollArea className="h-[500px] pr-4" ref={scrollRef}>
            <div className="space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex gap-3 ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {message.role !== "user" && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary">
                      <Bot className="h-4 w-4 text-primary-foreground" />
                    </div>
                  )}

                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-2 ${
                      message.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : message.role === "system"
                        ? "bg-muted"
                        : "bg-muted"
                    }`}
                  >
                    <div className="whitespace-pre-wrap text-sm">{message.content}</div>
                    <div className="mt-1 text-xs opacity-60">
                      {message.timestamp.toLocaleTimeString()}
                    </div>

                    {/* 如果有脚本数据，显示操作按钮 */}
                    {message.scriptData && (
                      <div className="mt-3 flex gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={handleViewScript}
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          查看计划
                        </Button>
                      </div>
                    )}
                  </div>

                  {message.role === "user" && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary">
                    <Bot className="h-4 w-4 text-primary-foreground" />
                  </div>
                  <div className="flex items-center gap-2 rounded-lg bg-muted px-4 py-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">AI正在思考...</span>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>

          <Separator />

          {/* 输入区 */}
          <div className="flex gap-2">
            <Textarea
              placeholder="输入你的需求，例如：帮我生成一个发布计划..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              className="min-h-[60px]"
            />
            <Button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="shrink-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 系统状态 */}
      <Card>
        <CardHeader>
          <CardTitle>系统状态</CardTitle>
          <CardDescription>当前账号和素材概览</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">总账号数</span>
              <Badge variant="secondary">{context?.accounts?.length || 0}</Badge>
            </div>
            <Separator className="my-2" />

            {["douyin", "kuaishou", "xiaohongshu", "channels", "bilibili"].map(platform => {
              const count = context?.accounts?.filter((a: any) => a.platform === platform).length || 0
              if (count === 0) return null

              return (
                <div key={platform} className="flex items-center justify-between py-1">
                  <span className="text-sm text-muted-foreground">
                    {platform === "douyin" ? "抖音" :
                     platform === "kuaishou" ? "快手" :
                     platform === "xiaohongshu" ? "小红书" :
                     platform === "channels" ? "视频号" : "B站"}
                  </span>
                  <span className="text-sm">{count}</span>
                </div>
              )
            })}
          </div>

          <Separator />

          <div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">可用视频</span>
              <Badge variant="secondary">{context?.videos?.length || 0}</Badge>
            </div>
          </div>

          <Separator />

          <Button
            variant="outline"
            className="w-full"
            onClick={fetchContext}
            size="sm"
          >
            刷新状态
          </Button>
        </CardContent>
      </Card>

      {/* 脚本查看对话框 */}
      <Dialog open={showScriptDialog} onOpenChange={setShowScriptDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>发布计划详情</DialogTitle>
            <DialogDescription>
              查看AI生成的发布计划，确认后可执行
            </DialogDescription>
          </DialogHeader>

          <ScrollArea className="h-[400px] rounded-md border p-4">
            <pre className="text-sm">
              {generatedScript?.content}
            </pre>
          </ScrollArea>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowScriptDialog(false)}
            >
              取消
            </Button>
            <Button
              variant="secondary"
              onClick={() => handleSaveAndExecute("dry-run")}
              disabled={loading}
            >
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Eye className="mr-2 h-4 w-4" />}
              模拟执行
            </Button>
            <Button
              onClick={() => handleSaveAndExecute("execute")}
              disabled={loading}
            >
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
              立即执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
