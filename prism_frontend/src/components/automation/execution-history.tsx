"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { History, Loader2, RefreshCw, CheckCircle2, XCircle, Clock } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

interface Execution {
  execution_id: string
  script_id: string
  task_batch_id: string
  mode: string
  tasks_created: number
  status: string
  started_at: string
  completed_at: string
  result: string | null
  filename: string
  plan_name: string
}

export function ExecutionHistory() {
  const [executions, setExecutions] = useState<Execution[]>([])
  const [loading, setLoading] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    fetchExecutions()
  }, [])

  const fetchExecutions = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:7000/api/v1/agent/executions')
      const data = await response.json()

      if (data.success) {
        setExecutions(data.data.items)
      }
    } catch (error) {
      console.error("Failed to fetch executions:", error)
      toast({
        title: "错误",
        description: "获取执行历史失败",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "-"
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "running":
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, any> = {
      completed: "default",
      failed: "destructive",
      running: "secondary",
      pending: "outline"
    }

    return (
      <Badge variant={variants[status] || "outline"}>
        {status === "completed" ? "已完成" :
         status === "failed" ? "失败" :
         status === "running" ? "运行中" : "等待中"}
      </Badge>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              执行历史
            </CardTitle>
            <CardDescription>
              查看所有脚本执行记录
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchExecutions}
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
        {executions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <History className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-sm text-muted-foreground">
              暂无执行记录
            </p>
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>计划名称</TableHead>
                  <TableHead>批次ID</TableHead>
                  <TableHead>模式</TableHead>
                  <TableHead>任务数</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>开始时间</TableHead>
                  <TableHead>完成时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {executions.map((execution) => (
                  <TableRow key={execution.execution_id}>
                    <TableCell className="font-medium">
                      {execution.plan_name}
                    </TableCell>
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      {execution.task_batch_id}
                    </TableCell>
                    <TableCell>
                      <Badge variant={execution.mode === "execute" ? "default" : "secondary"}>
                        {execution.mode === "execute" ? "执行" : "模拟"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">{execution.tasks_created}</span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(execution.status)}
                        {getStatusBadge(execution.status)}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(execution.started_at)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(execution.completed_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
