"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { FileCode, Play, Eye, Trash2, Loader2, RefreshCw } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

interface Script {
  script_id: string
  filename: string
  script_type: string
  plan_name: string
  description: string
  generated_by: string
  created_at: string
  status: string
}

export function ScriptManager() {
  const [scripts, setScripts] = useState<Script[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedScript, setSelectedScript] = useState<Script | null>(null)
  const [scriptContent, setScriptContent] = useState("")
  const [showDialog, setShowDialog] = useState(false)
  const [executing, setExecuting] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    fetchScripts()
  }, [])

  const fetchScripts = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:7000/api/v1/agent/scripts')
      const data = await response.json()

      if (data.success) {
        setScripts(data.data.items)
      }
    } catch (error) {
      console.error("Failed to fetch scripts:", error)
      toast({
        title: "错误",
        description: "获取脚本列表失败",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleView = async (script: Script) => {
    try {
      const response = await fetch(`http://localhost:7000/api/v1/agent/scripts/${script.script_id}`)
      const data = await response.json()

      if (data.success) {
        setSelectedScript(script)
        setScriptContent(data.data.content)
        setShowDialog(true)
      }
    } catch (error) {
      toast({
        title: "错误",
        description: "获取脚本详情失败",
        variant: "destructive"
      })
    }
  }

  const handleExecute = async (mode: "dry-run" | "execute") => {
    if (!selectedScript) return

    setExecuting(true)
    try {
      const response = await fetch('http://localhost:7000/api/v1/agent/execute-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_id: selectedScript.script_id,
          mode: mode,
          options: {
            priority: 5,
            validate_only: false
          }
        })
      })

      const data = await response.json()

      if (data.success) {
        const result = data.data
        toast({
          title: mode === "dry-run" ? "模拟执行成功" : "执行成功",
          description: `创建了 ${result.tasks_created} 个任务，批次ID: ${result.task_batch_id}`
        })

        setShowDialog(false)
        fetchScripts()
      } else {
        throw new Error(data.message || "执行失败")
      }
    } catch (error: any) {
      toast({
        title: "错误",
        description: error.message || "执行脚本失败",
        variant: "destructive"
      })
    } finally {
      setExecuting(false)
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <FileCode className="h-5 w-5" />
              脚本管理
            </CardTitle>
            <CardDescription>
              查看和管理所有AI生成的发布脚本
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchScripts}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            刷新
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {scripts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <FileCode className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-sm text-muted-foreground">
              暂无脚本，使用AI助手生成发布计划
            </p>
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>计划名称</TableHead>
                  <TableHead>文件名</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scripts.map((script) => (
                  <TableRow key={script.script_id}>
                    <TableCell className="font-medium">
                      {script.plan_name}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {script.filename}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {script.script_type.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={script.status === "saved" ? "secondary" : "default"}>
                        {script.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(script.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleView(script)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* 脚本详情对话框 */}
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogContent className="max-w-4xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle>{selectedScript?.plan_name}</DialogTitle>
              <DialogDescription>
                {selectedScript?.description}
              </DialogDescription>
            </DialogHeader>

            <ScrollArea className="h-[500px] rounded-md border p-4">
              <pre className="text-sm">
                {scriptContent}
              </pre>
            </ScrollArea>

            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => setShowDialog(false)}
              >
                关闭
              </Button>
              <Button
                variant="secondary"
                onClick={() => handleExecute("dry-run")}
                disabled={executing}
              >
                {executing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Eye className="mr-2 h-4 w-4" />
                )}
                模拟执行
              </Button>
              <Button
                onClick={() => handleExecute("execute")}
                disabled={executing}
              >
                {executing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                立即执行
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}
