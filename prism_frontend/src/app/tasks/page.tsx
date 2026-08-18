"use client"

import { useEffect, useMemo, useState } from "react"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, Clock3, RefreshCcw, XCircle, AlertCircle, Play, Trash2, Trash, Ban } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { fetcher } from "@/lib/api"
import { backendBaseUrl } from "@/lib/env"
import { tasksResponseSchema, type TasksResponse } from "@/lib/schemas"
import { formatBeijingDateTime } from "@/lib/time"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"

const statusTabs = [
  { label: "全部", value: "all" },
  { label: "待执行", value: "pending" },
  { label: "定时", value: "scheduled" },
  { label: "运行中", value: "running" },
  // { label: "被取消", value: "cancelled" },
  { label: "成功", value: "success" },
  { label: "失败", value: "error" },
]

type StatusFilter = (typeof statusTabs)[number]["value"]

const ITEMS_PER_PAGE = 10

export default function TasksPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [activeTab, setActiveTab] = useState("auto")
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([])
  const [selectedManualIds, setSelectedManualIds] = useState<string[]>([])
  const [autoPage, setAutoPage] = useState(1)
  const [manualPage, setManualPage] = useState(1)

  const {
    data: tasksResponse,
    isLoading,
    isFetching,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => fetcher<TasksResponse>(`/api/tasks`, tasksResponseSchema),
  })

  // 获取人工任务
  const { data: manualTasksRes, isLoading: manualLoading } = useQuery({
    queryKey: ["manual-tasks"],
    queryFn: async () => {
      const res = await fetch(`${backendBaseUrl}/api/v1/manual-tasks/list`)
      if (!res.ok) throw new Error("Failed to fetch manual tasks")
      return res.json()
    },
    enabled: activeTab === "manual"
  })

  // 获取人工任务统计
  const { data: manualStatsRes } = useQuery({
    queryKey: ["manual-tasks-stats"],
    queryFn: async () => {
      const res = await fetch(`${backendBaseUrl}/api/v1/manual-tasks/stats`)
      if (!res.ok) throw new Error("Failed to fetch stats")
      return res.json()
    },
  })

  // 重试人工任务
  const retryMutation = useMutation({
    mutationFn: async (taskId: string) => {
      const res = await fetch(`${backendBaseUrl}/api/v1/manual-tasks/${taskId}/retry`, {
        method: "POST"
      })
      if (!res.ok) throw new Error("Failed to retry task")
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["manual-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["manual-tasks-stats"] })
      toast({ title: "任务已重新加入队列" })
    },
    onError: (error: any) => {
      toast({ variant: "destructive", title: error.message || "重试失败" })
    }
  })

  // 删除人工任务
  const deleteMutation = useMutation({
    mutationFn: async (taskId: string) => {
      const res = await fetch(`${backendBaseUrl}/api/v1/manual-tasks/${taskId}`, {
        method: "DELETE"
      })
      if (!res.ok) throw new Error("Failed to delete task")
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["manual-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["manual-tasks-stats"] })
      toast({ title: "任务已删除" })
    },
    onError: (error: any) => {
      toast({ variant: "destructive", title: error.message || "删除失败" })
    }
  })

  // 批量删除人工任务
  const manualBatchDeleteMutation = useMutation({
    mutationFn: async (taskIds: string[]) => {
      const results = await Promise.allSettled(
        taskIds.map(id =>
          fetch(`${backendBaseUrl}/api/v1/manual-tasks/${id}`, { method: "DELETE" })
            .then(res => res.ok ? res.json() : Promise.reject(new Error(`删除失败: ${id}`)))
        )
      )
      const failed = results.filter(r => r.status === "rejected").length
      return { total: taskIds.length, failed }
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["manual-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["manual-tasks-stats"] })
      setSelectedManualIds([])
      if (data.failed === 0) {
        toast({ title: `成功删除 ${data.total} 个任务` })
      } else {
        toast({
          variant: "destructive",
          title: `删除完成，${data.total - data.failed} 个成功，${data.failed} 个失败`
        })
      }
    },
    onError: (error: any) => {
      toast({ variant: "destructive", title: error.message || "批量删除失败" })
    }
  })

  // 批量删除自动任务 - 使用新的批量API
  const batchDeleteMutation = useMutation({
    mutationFn: async (taskIds: string[]) => {
      console.log("[Tasks] Batch deleting tasks:", taskIds)
      const res = await fetch(`${backendBaseUrl}/api/v1/tasks/batch/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_ids: taskIds })
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || "批量删除失败")
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      setSelectedTaskIds([])
      toast({
        title: data.message || `成功删除 ${data.success_count} 个任务`,
        description: data.failed_count > 0 ? `失败 ${data.failed_count} 个` : undefined
      })
    },
    onError: (error: any) => {
      console.error("批量删除错误:", error)
      toast({ variant: "destructive", title: error.message || "批量删除失败" })
    }
  })

  // 批量重试自动任务
  const batchRetryMutation = useMutation({
    mutationFn: async (taskIds: string[]) => {
      console.log("[Tasks] Batch retrying tasks:", taskIds)
      const res = await fetch(`${backendBaseUrl}/api/v1/tasks/batch/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_ids: taskIds })
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || "批量重试失败")
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      setSelectedTaskIds([])
      toast({
        title: data.message || `成功重试 ${data.success_count} 个任务`,
        description: data.failed_count > 0 ? `失败 ${data.failed_count} 个` : undefined
      })
    },
    onError: (error: any) => {
      console.error("批量重试错误:", error)
      toast({ variant: "destructive", title: error.message || "批量重试失败" })
    }
  })

  // 清理任务
  const clearTasksMutation = useMutation({
    mutationFn: async (type: 'pending' | 'failed' | 'success' | 'all') => {
      const res = await fetch(`${backendBaseUrl}/api/v1/tasks/clear/${type}`, {
        method: "POST"
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || "清理任务失败")
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      setSelectedTaskIds([])
      toast({
        title: data.message || `成功清理 ${data.deleted_count} 个任务`
      })
    },
    onError: (error: any) => {
      console.error("清理任务错误:", error)
      toast({ variant: "destructive", title: error.message || "清理任务失败" })
    }
  })

  // 批量取消任务（支持强制取消running状态）
  const batchCancelMutation = useMutation({
    mutationFn: async ({ taskIds, force }: { taskIds: string[], force: boolean }) => {
      console.log(`[Tasks] Batch cancelling tasks (force=${force}):`, taskIds)
      const res = await fetch(`${backendBaseUrl}/api/v1/tasks/batch/cancel?force=${force}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_ids: taskIds })
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || "批量取消失败")
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      setSelectedTaskIds([])
      toast({
        title: data.message || `成功取消 ${data.success_count} 个任务`,
        description: data.failed_count > 0 ? `失败 ${data.failed_count} 个` : undefined
      })
    },
    onError: (error: any) => {
      console.error("批量取消错误:", error)
      toast({ variant: "destructive", title: error.message || "批量取消失败" })
    }
  })

  // 单个任务取消
  const cancelTaskMutation = useMutation({
    mutationFn: async ({ taskId, force }: { taskId: string, force: boolean }) => {
      const res = await fetch(`${backendBaseUrl}/api/v1/tasks/cancel/${taskId}?force=${force}`, {
        method: "POST"
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || "取消失败")
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      toast({
        title: data.message || "任务已取消"
      })
    },
    onError: (error: any) => {
      console.error("取消任务错误:", error)
      toast({ variant: "destructive", title: error.message || "取消失败" })
    }
  })

  console.log("[Tasks] Current Backend URL:", backendBaseUrl)

  // 单个任务删除（自动任务）
  const deleteTaskMutation = useMutation({
    mutationFn: async (task: { id: string; source?: "queue" | "history" }) => {
      console.log("[Tasks] Deleting task:", task)

      // 根据任务来源选择正确的API端点
      const endpoint = task.source === "history"
        ? `${backendBaseUrl}/api/v1/publish/history/${task.id}`
        : `${backendBaseUrl}/api/v1/tasks/${task.id}`

      const res = await fetch(endpoint, {
        method: "DELETE"
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || "删除失败")
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      toast({ title: data.message || "任务已删除" })
    },
    onError: (error: any) => {
      console.error("删除任务错误:", error)
      toast({ variant: "destructive", title: error.message || "删除失败" })
    }
  })

  // 单个任务重试（自动任务）
  const retryTaskMutation = useMutation({
    mutationFn: async (taskId: string) => {
      console.log("[Tasks] Retrying task:", taskId)
      const res = await fetch(`${backendBaseUrl}/api/v1/tasks/retry/${taskId}`, {
        method: "POST"
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || "重试失败")
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      toast({ title: data.message || "任务已开始重试" })
    },
    onError: (error: any) => {
      console.error("重试任务错误:", error)
      toast({ variant: "destructive", title: error.message || "重试失败" })
    }
  })

  const tasks = tasksResponse?.data ?? []
  const summary = tasksResponse?.summary
  const manualTasks = manualTasksRes?.data?.items || []
  const manualStats = manualStatsRes?.data || {}

  const filteredTasks = useMemo(() => {
    if (statusFilter === "all") return tasks
    return tasks.filter((task) => task.status === statusFilter)
  }, [tasks, statusFilter])

  const autoTotalPages = Math.max(1, Math.ceil(filteredTasks.length / ITEMS_PER_PAGE))
  const manualTotalPages = Math.max(1, Math.ceil(manualTasks.length / ITEMS_PER_PAGE))
  const safeAutoPage = Math.min(autoPage, autoTotalPages)
  const safeManualPage = Math.min(manualPage, manualTotalPages)

  const paginatedTasks = useMemo(() => {
    const start = (safeAutoPage - 1) * ITEMS_PER_PAGE
    return filteredTasks.slice(start, start + ITEMS_PER_PAGE)
  }, [filteredTasks, safeAutoPage])

  const paginatedManualTasks = useMemo(() => {
    const start = (safeManualPage - 1) * ITEMS_PER_PAGE
    return manualTasks.slice(start, start + ITEMS_PER_PAGE)
  }, [manualTasks, safeManualPage])

  const scheduledCount = summary?.scheduled ?? tasks.filter((task) => task.status === "scheduled").length
  const successCount = summary?.success ?? tasks.filter((task) => task.status === "success").length
  const errorCount = summary?.error ?? tasks.filter((task) => task.status === "error").length

  const platformLabels: Record<string, string> = {
    douyin: "抖音",
    kuaishou: "快手",
    xiaohongshu: "小红书",
    bilibili: "B站",
    channels: "视频号",
    "2": "快手",
    "3": "抖音",
    "platform_2": "快手",
    "platform_3": "抖音"
  }

  const renderPagination = (
    currentPage: number,
    totalPages: number,
    totalItems: number,
    onChange: (page: number) => void
  ) => {
    if (totalItems <= ITEMS_PER_PAGE) return null
    return (
      <div className="mt-4 flex items-center justify-between text-sm text-white/60">
        <div>共 {totalItems} 条 · 第 {currentPage} / {totalPages} 页</div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            className="border border-white/10 bg-white/5"
          >
            上一页
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
            className="border border-white/10 bg-white/5"
          >
            下一页
          </Button>
        </div>
      </div>
    )
  }

  const getManualId = (task: any) => {
    const raw = task?.task_id || task?.id || task?.taskId || task?.taskID
    return raw ? String(raw) : ""
  }

  useEffect(() => {
    setAutoPage(1)
    setSelectedTaskIds([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  useEffect(() => {
    setAutoPage(prev => Math.min(prev, autoTotalPages))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoTotalPages])

  useEffect(() => {
    setManualPage(1)
    setSelectedManualIds([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manualTasks.length])

  useEffect(() => {
    setManualPage(prev => Math.min(prev, manualTotalPages))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manualTotalPages])

  useEffect(() => {
    setSelectedTaskIds([])
    setSelectedManualIds([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  return (
    <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="任务中心"
        actions={
          <div className="ml-auto flex flex-wrap gap-3">
            {selectedTaskIds.length > 0 && activeTab === "auto" && (
              <>
                <Button
                  variant="outline"
                  className="rounded-2xl border-orange-500/50 bg-orange-500/10 text-orange-200 hover:bg-orange-500/20"
                  onClick={() => {
                    console.log("[Tasks] Batch cancel button clicked", selectedTaskIds)
                    batchCancelMutation.mutate({ taskIds: selectedTaskIds, force: false })
                  }}
                  disabled={batchCancelMutation.isPending}
                >
                  <Ban className="h-4 w-4 mr-2" />
                  取消任务 ({selectedTaskIds.length})
                </Button>
                <Button
                  variant="outline"
                  className="rounded-2xl border-red-500/50 bg-red-500/10 text-red-200 hover:bg-red-500/20"
                  onClick={() => {
                    console.log("[Tasks] Batch force cancel button clicked", selectedTaskIds)
                    batchCancelMutation.mutate({ taskIds: selectedTaskIds, force: true })
                  }}
                  disabled={batchCancelMutation.isPending}
                >
                  <Ban className="h-4 w-4 mr-2" />
                  强制取消 ({selectedTaskIds.length})
                </Button>
                <Button
                  variant="outline"
                  className="rounded-2xl border-blue-500/50 bg-blue-500/10 text-blue-200 hover:bg-blue-500/20"
                  onClick={() => {
                    console.log("[Tasks] Batch retry button clicked", selectedTaskIds)
                    batchRetryMutation.mutate(selectedTaskIds)
                  }}
                  disabled={batchRetryMutation.isPending}
                >
                  <RefreshCcw className="h-4 w-4 mr-2" />
                  重试选中 ({selectedTaskIds.length})
                </Button>
                <Button
                  variant="destructive"
                  className="rounded-2xl"
                  onClick={() => {
                    console.log("[Tasks] Batch delete button clicked", selectedTaskIds)
                    batchDeleteMutation.mutate(selectedTaskIds)
                  }}
                  disabled={batchDeleteMutation.isPending}
                >
                  <Trash className="h-4 w-4 mr-2" />
                  删除选中 ({selectedTaskIds.length})
                </Button>
              </>
            )}
            {activeTab === "auto" && selectedTaskIds.length === 0 && (
              <>
                <Button
                  variant="outline"
                  className="rounded-2xl border-red-500/50 bg-red-500/10 text-red-200 hover:bg-red-500/20"
                  onClick={() => {
                    console.log("[Tasks] Clear failed button clicked")
                    try {
                      clearTasksMutation.mutate('failed')
                    } catch (err) {
                      console.error("[Tasks] Error:", err)
                    }
                  }}
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  清理失败
                </Button>
                <Button
                  variant="outline"
                  className="rounded-2xl border-green-500/50 bg-green-500/10 text-green-200 hover:bg-green-500/20"
                  onClick={() => {
                    console.log("[Tasks] Clear success button clicked")
                    try {
                      clearTasksMutation.mutate('success')
                    } catch (err) {
                      console.error("[Tasks] Error:", err)
                    }
                  }}
                >
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  清理成功
                </Button>
              </>
            )}
            {selectedManualIds.length > 0 && activeTab === "manual" && (
              <Button
                variant="destructive"
                className="rounded-2xl"
                onClick={() => {
                  console.log("[Tasks] Manual batch delete clicked", selectedManualIds)
                  manualBatchDeleteMutation.mutate(selectedManualIds)
                }}
                disabled={manualBatchDeleteMutation.isPending}
              >
                <Trash className="h-4 w-4 mr-2" />
                删除选中 ({selectedManualIds.length})
              </Button>
            )}
            <Button
              variant="ghost"
              className="rounded-2xl border border-white/10 bg-white/5"
              onClick={() => {
                refetch()
                queryClient.invalidateQueries({ queryKey: ["manual-tasks"] })
                queryClient.invalidateQueries({ queryKey: ["manual-tasks-stats"] })
                setSelectedTaskIds([])
                setSelectedManualIds([])
              }}
              disabled={isFetching}
            >
              <RefreshCcw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
              {isFetching ? "刷新中..." : "刷新数据"}
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-4">
        <Card className="bg-black border-white/10">
          <CardHeader className="flex items-center gap-3">
            <Clock3 className="h-8 w-8 text-white" />
            <div>
              <CardTitle>定时任务</CardTitle>
              <CardDescription>{scheduledCount} 条待执行</CardDescription>
            </div>
          </CardHeader>
        </Card>
        <Card className="bg-black border-white/10">
          <CardHeader className="flex items-center gap-3">
            <CheckCircle2 className="h-8 w-8 text-emerald-400" />
            <div>
              <CardTitle>发布成功</CardTitle>
              <CardDescription>{successCount} 条已完成</CardDescription>
            </div>
          </CardHeader>
        </Card>
        <Card className="bg-black border-white/10">
          <CardHeader className="flex items-center gap-3">
            <XCircle className="h-8 w-8 text-red-400" />
            <div>
              <CardTitle>失败/异常</CardTitle>
              <CardDescription>{errorCount} 条需要关注</CardDescription>
            </div>
          </CardHeader>
        </Card>
        <Card className="bg-black border-white/10">
          <CardHeader className="flex items-center gap-3">
            <AlertCircle className="h-8 w-8 text-yellow-400" />
            <div>
              <CardTitle>人工处理</CardTitle>
              <CardDescription>{manualStats.pending || 0} 条待处理</CardDescription>
            </div>
          </CardHeader>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="auto">自动任务</TabsTrigger>
          <TabsTrigger value="manual">
            人工处理
            {manualStats.pending > 0 && (
              <Badge variant="destructive" className="ml-2">{manualStats.pending}</Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="auto">
          <Card className="bg-black border-white/10">
            <CardHeader className="flex flex-wrap items-center gap-3">
              <div>
                <CardTitle>任务列表</CardTitle>
                <CardDescription>展示最近 200 条任务记录</CardDescription>
              </div>
              <div className="ml-auto flex flex-wrap gap-2">
                {statusTabs.map((tab) => (
                  <Button
                    key={tab.value}
                    variant={statusFilter === tab.value ? "default" : "ghost"}
                    className="rounded-2xl border border-white/10"
                    onClick={() => setStatusFilter(tab.value)}
                  >
                    {tab.label}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="rounded-2xl border border-white/10 bg-black p-6 text-center text-sm text-white/60">
                  正在加载任务数据...
                </div>
              ) : isError ? (
                <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-6 text-center text-sm text-red-400">
                  加载失败: {error?.message || "未知错误"}
                  <Button variant="outline" size="sm" className="ml-4" onClick={() => refetch()}>重试</Button>
                </div>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow className="border-white/10">
                        <TableHead className="w-12">
                          <Checkbox
                            checked={
                              paginatedTasks.length > 0 &&
                              paginatedTasks.every(t => selectedTaskIds.includes(t.id))
                            }
                            onCheckedChange={(checked) => {
                              const pageIds = paginatedTasks.map(t => t.id)
                              if (checked) {
                                setSelectedTaskIds(Array.from(new Set([...selectedTaskIds, ...pageIds])))
                                return
                              }
                              setSelectedTaskIds(selectedTaskIds.filter(id => !pageIds.includes(id)))
                            }}
                          />
                        </TableHead>
                        <TableHead className="text-white/60">标题</TableHead>
                        <TableHead className="text-white/60">平台</TableHead>
                        <TableHead className="text-white/60">账号</TableHead>
                        <TableHead className="text-white/60">素材</TableHead>
                        <TableHead className="text-white/60">时间</TableHead>
                        <TableHead className="text-white/60">状态</TableHead>
                        <TableHead className="text-right text-white/60">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredTasks.length === 0 && (
                        <TableRow className="border-white/5">
                          <TableCell colSpan={8} className="text-center text-sm text-white/60">
                            暂无符合条件的任务
                          </TableCell>
                        </TableRow>
                      )}
                      {paginatedTasks.map((task) => (
                        <TableRow key={task.id} className="border-white/10">
                          <TableCell>
                            <Checkbox
                              checked={selectedTaskIds.includes(task.id)}
                              onCheckedChange={(checked) => {
                                if (checked) {
                                  setSelectedTaskIds([...selectedTaskIds, task.id])
                                } else {
                                  setSelectedTaskIds(selectedTaskIds.filter(id => id !== task.id))
                                }
                              }}
                            />
                          </TableCell>
                          <TableCell className="font-medium">{task.title}</TableCell>
                          <TableCell>
                            <Badge className="border-white/10 bg-white/10">{task.platform}</Badge>
                          </TableCell>
                          <TableCell>{task.account}</TableCell>
                          <TableCell>{task.material}</TableCell>
                          <TableCell>
                            {task.scheduledAt ? (
                              <span className="text-xs text-white/70">定时 · {task.scheduledAt}</span>
                            ) : (
                              <span className="text-xs text-white/70">{formatBeijingDateTime(task.createdAt)}</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge
                              className={
                                task.status === "success"
                                  ? "bg-emerald-500/20 text-emerald-200"
                                  : task.status === "error"
                                    ? "bg-red-500/20 text-red-200"
                                    : task.status === "scheduled"
                                      ? "bg-amber-500/20 text-amber-200"
                                      : task.status === "running"
                                        ? "bg-blue-500/20 text-blue-200"
                                        : "bg-white/10 text-white"
                              }
                            >
                              {task.status === "scheduled"
                                ? "已定时"
                                : task.status === "success"
                                  ? "成功"
                                  : task.status === "error"
                                    ? "失败"
                                    : task.status === "running"
                                      ? "运行中"
                                      : "等待中"}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-2">
                              {task.status === "error" && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    console.log("[Tasks] Single retry clicked", task.id, task)
                                    retryTaskMutation.mutate(task.id)
                                  }}
                                  disabled={retryTaskMutation.isPending}
                                  title="重试任务"
                                >
                                  <RefreshCcw className="h-4 w-4 text-blue-400" />
                                </Button>
                              )}
                              {(task.status === "pending" || task.status === "scheduled") && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    console.log("[Tasks] Single cancel clicked", task.id, task)
                                    if (confirm("确定取消此任务吗？")) {
                                      cancelTaskMutation.mutate({ taskId: task.id, force: false })
                                    }
                                  }}
                                  disabled={cancelTaskMutation.isPending}
                                  title="取消任务"
                                >
                                  <Ban className="h-4 w-4 text-orange-400" />
                                </Button>
                              )}
                              {task.status === "running" && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    console.log("[Tasks] Force cancel clicked", task.id, task)
                                    console.log("[Tasks] cancelTaskMutation object:", cancelTaskMutation)
                                    console.log("[Tasks] About to call mutate")
                                    try {
                                      cancelTaskMutation.mutate({ taskId: task.id, force: true })
                                      console.log("[Tasks] mutate called successfully")
                                    } catch (err) {
                                      console.error("[Tasks] Error calling mutate:", err)
                                    }
                                    // Temporarily removed confirm for testing
                                    // const confirmed = confirm("⚠️ 确定强制取消正在运行的任务吗？")
                                    // console.log("[Tasks] Confirm result:", confirmed)
                                    // if (confirmed) {
                                    //   console.log("[Tasks] Calling cancelTaskMutation with force=true", task.id)
                                    //   cancelTaskMutation.mutate({ taskId: task.id, force: true })
                                    // } else {
                                    //   console.log("[Tasks] User cancelled force cancel action")
                                    // }
                                  }}
                                  disabled={cancelTaskMutation.isPending}
                                  title="强制取消运行中的任务（测试版-无确认）"
                                >
                                  <Ban className="h-4 w-4 text-red-400" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  console.log("[Tasks] Single delete clicked", task.id, task)
                                  deleteTaskMutation.mutate({ id: task.id, source: task.source })
                                }}
                                disabled={deleteTaskMutation.isPending}
                                title="删除记录（无确认-测试版）"
                              >
                                <Trash2 className="h-4 w-4 text-gray-400 hover:text-red-400" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {renderPagination(safeAutoPage, autoTotalPages, filteredTasks.length, setAutoPage)}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="manual">
          <Card className="bg-black border-white/10">
            <CardHeader>
              <CardTitle>人工处理任务</CardTitle>
              <CardDescription>
                这些任务需要人工处理后才能继续发布（如短信验证）
              </CardDescription>
            </CardHeader>
            <CardContent>
              {manualLoading ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center text-sm text-white/60">
                  正在加载...
                </div>
              ) : manualTasks.length === 0 ? (
                <div className="text-center py-10">
                  <CheckCircle2 className="h-10 w-10 text-green-500 mx-auto mb-4" />
                  <h3 className="text-lg font-medium">暂无待处理任务</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    所有任务都已处理完成
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/5">
                      <TableHead className="w-12">
                        <Checkbox
                          checked={
                            paginatedManualTasks.length > 0 &&
                            paginatedManualTasks.every((task: any) => selectedManualIds.includes(getManualId(task)))
                          }
                          onCheckedChange={(checked) => {
                            const pageIds = paginatedManualTasks.map((task: any) => getManualId(task)).filter(Boolean)
                            if (checked) {
                              setSelectedManualIds(Array.from(new Set([...selectedManualIds, ...pageIds])))
                              return
                            }
                            setSelectedManualIds(selectedManualIds.filter(id => !pageIds.includes(id)))
                          }}
                        />
                      </TableHead>
                      <TableHead className="text-white/60">原因</TableHead>
                      <TableHead className="text-white/60">平台</TableHead>
                      <TableHead className="text-white/60">账号</TableHead>
                      <TableHead className="text-white/60">素材</TableHead>
                      <TableHead className="text-white/60">创建时间</TableHead>
                      <TableHead className="text-right text-white/60">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedManualTasks.map((task: any, index: number) => {
                      const manualId = getManualId(task)
                      return (
                        <TableRow key={manualId || `manual-${index}`} className="border-white/5">
                          <TableCell>
                            <Checkbox
                              checked={manualId ? selectedManualIds.includes(manualId) : false}
                              onCheckedChange={(checked) => {
                                if (!manualId) return
                                if (checked) {
                                  setSelectedManualIds(Array.from(new Set([...selectedManualIds, manualId])))
                                } else {
                                  setSelectedManualIds(selectedManualIds.filter(id => id !== manualId))
                                }
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <AlertCircle className="h-4 w-4 text-yellow-500" />
                              <span>{task.reason}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {platformLabels[task.platform] || task.platform}
                            </Badge>
                          </TableCell>
                          <TableCell>{task.account_name || task.account_id}</TableCell>
                          <TableCell className="max-w-[200px] truncate">
                            {task.material_name || task.material_id || "-"}
                          </TableCell>
                          <TableCell className="text-xs text-white/70">
                            {new Date(task.created_at).toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                  console.log("[Tasks] Manual retry clicked", manualId)
                                  if (manualId) {
                                    retryMutation.mutate(manualId)
                                  }
                                }}
                                disabled={retryMutation.isPending}
                              >
                                <Play className="h-4 w-4 mr-1" />
                                重试
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  console.log("[Tasks] Manual delete clicked", manualId)
                                  if (manualId) {
                                    deleteMutation.mutate(manualId)
                                  }
                                }}
                                disabled={deleteMutation.isPending}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              )}
              {renderPagination(safeManualPage, manualTotalPages, manualTasks.length, setManualPage)}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
