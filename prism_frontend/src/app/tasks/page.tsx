"use client"

import { useEffect, useMemo, useState } from "react"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, Clock3, RefreshCcw, XCircle, AlertCircle, Play, Trash2, Trash, Ban } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { DataTable } from "@/components/ui/data-table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { fetcher } from "@/lib/api"
import { backendBaseUrl } from "@/lib/env"
import { tasksResponseSchema, type TasksResponse } from "@/lib/schemas"
import { formatBeijingDateTime } from "@/lib/time"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"
import { type ColumnDef } from "@tanstack/react-table"

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

export default function TasksPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [activeTab, setActiveTab] = useState("auto")
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([])
  const [selectedManualIds, setSelectedManualIds] = useState<string[]>([])

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

  const scheduledCount = summary?.scheduled ?? tasks.filter((task) => task.status === "scheduled").length
  const successCount = summary?.success ?? tasks.filter((task) => task.status === "success").length
  const errorCount = summary?.error ?? tasks.filter((task) => task.status === "error").length

  const platformLabels: Record<string, string> = {
    douyin: "抖音",
    kuaishou: "快手",
    xiaohongshu: "小红书",
    bilibili: "B站",
    channels: "视频号",
    tiktok: "TikTok",
    youtube: "YouTube",
    "2": "快手",
    "3": "抖音",
    "6": "TikTok",
    "7": "YouTube",
    "platform_2": "快手",
    "platform_3": "抖音",
    "platform_6": "TikTok",
    "platform_7": "YouTube"
  }

  const getManualId = (task: any) => {
    const raw = task?.task_id || task?.id || task?.taskId || task?.taskID
    return raw ? String(raw) : ""
  }

  useEffect(() => {
    setSelectedTaskIds([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  useEffect(() => {
    setSelectedManualIds([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manualTasks.length])

  useEffect(() => {
    setSelectedTaskIds([])
    setSelectedManualIds([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  const statusLabel = (status: string) => {
    if (status === "scheduled") return "已定时"
    if (status === "success") return "成功"
    if (status === "error") return "失败"
    if (status === "running") return "运行中"
    return "等待中"
  }

  const statusBadgeClass = (status: string) => {
    if (["success", "error", "scheduled", "running"].includes(status)) return "bg-black text-white"
    return "bg-black text-foreground"
  }

  // ── 自动任务列（与素材/账号管理一致的可收窄数据表） ──
  const autoColumns: ColumnDef<any>[] = [
    {
      id: "select",
      size: 56,
      header: () => (
        <div className="flex items-center">
          <Checkbox
            checked={filteredTasks.length > 0 && filteredTasks.every(t => selectedTaskIds.includes(t.id))}
            onCheckedChange={(checked) => {
              const allIds = filteredTasks.map(t => t.id)
              if (checked) setSelectedTaskIds(Array.from(new Set([...selectedTaskIds, ...allIds])))
              else setSelectedTaskIds(selectedTaskIds.filter(id => !allIds.includes(id)))
            }}
          />
        </div>
      ),
      cell: ({ row }) => (
        <div className="flex items-center">
          <Checkbox
            checked={selectedTaskIds.includes(row.original.id)}
            onCheckedChange={(checked) => {
              if (checked) setSelectedTaskIds(Array.from(new Set([...selectedTaskIds, row.original.id])))
              else setSelectedTaskIds(selectedTaskIds.filter(id => id !== row.original.id))
            }}
          />
        </div>
      ),
    },
    {
      accessorKey: "title",
      header: "标题",
      size: 340,
      cell: ({ row }) => (
        <div className="min-w-0 max-w-[340px]">
          <div className="truncate font-medium" title={row.original.title}>{row.original.title}</div>
        </div>
      ),
    },
    {
      accessorKey: "platform",
      header: "平台",
      size: 110,
      cell: ({ row }) => <Badge className="border-border/70 bg-black">{row.original.platform}</Badge>,
    },
    {
      accessorKey: "account",
      header: "账号",
      size: 180,
      cell: ({ row }) => (
        <div className="min-w-0 max-w-[180px]">
          <div className="truncate" title={row.original.account}>{row.original.account}</div>
        </div>
      ),
    },
    {
      accessorKey: "material",
      header: "素材",
      size: 180,
      cell: ({ row }) => (
        <div className="min-w-0 max-w-[180px]">
          <div className="truncate" title={row.original.material}>{row.original.material}</div>
        </div>
      ),
    },
    {
      id: "time",
      header: "时间",
      size: 180,
      cell: ({ row }) => (
        row.original.scheduledAt
          ? <span className="text-xs text-foreground/70">定时 · {row.original.scheduledAt}</span>
          : <span className="text-xs text-foreground/70">{formatBeijingDateTime(row.original.createdAt)}</span>
      ),
    },
    {
      accessorKey: "status",
      header: "状态",
      size: 110,
      cell: ({ row }) => (
        <Badge className={statusBadgeClass(row.original.status)}>{statusLabel(row.original.status)}</Badge>
      ),
    },
    {
      id: "actions",
      header: () => <div className="text-right">操作</div>,
      size: 200,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          {row.original.status === "error" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => retryTaskMutation.mutate(row.original.id)}
              disabled={retryTaskMutation.isPending}
              title="重试任务"
            >
              <RefreshCcw className="h-4 w-4 text-white" />
            </Button>
          )}
          {(row.original.status === "pending" || row.original.status === "scheduled") && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (confirm("确定取消此任务吗？")) {
                  cancelTaskMutation.mutate({ taskId: row.original.id, force: false })
                }
              }}
              disabled={cancelTaskMutation.isPending}
              title="取消任务"
            >
              <Ban className="h-4 w-4 text-white" />
            </Button>
          )}
          {row.original.status === "running" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (confirm("⚠️ 确定强制取消正在运行的任务吗？")) {
                  cancelTaskMutation.mutate({ taskId: row.original.id, force: true })
                }
              }}
              disabled={cancelTaskMutation.isPending}
              title="强制取消运行中的任务"
            >
              <Ban className="h-4 w-4 text-white" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => deleteTaskMutation.mutate({ id: row.original.id, source: row.original.source })}
            disabled={deleteTaskMutation.isPending}
            title="删除记录"
          >
            <Trash2 className="h-4 w-4 text-white hover:text-white" />
          </Button>
        </div>
      ),
    },
  ]

  // ── 人工处理任务列 ──
  const manualColumns: ColumnDef<any>[] = [
    {
      id: "select",
      size: 56,
      header: () => (
        <div className="flex items-center">
          <Checkbox
            checked={
              manualTasks.length > 0 &&
              manualTasks.every((t: any) => {
                const id = getManualId(t)
                return id ? selectedManualIds.includes(id) : false
              })
            }
            onCheckedChange={(checked) => {
              const pageIds = manualTasks.map((t: any) => getManualId(t)).filter(Boolean)
              if (checked) setSelectedManualIds(Array.from(new Set([...selectedManualIds, ...pageIds])))
              else setSelectedManualIds(selectedManualIds.filter(id => !pageIds.includes(id)))
            }}
          />
        </div>
      ),
      cell: ({ row }) => {
        const manualId = getManualId(row.original)
        return (
          <div className="flex items-center">
            <Checkbox
              checked={manualId ? selectedManualIds.includes(manualId) : false}
              onCheckedChange={(checked) => {
                if (!manualId) return
                if (checked) setSelectedManualIds(Array.from(new Set([...selectedManualIds, manualId])))
                else setSelectedManualIds(selectedManualIds.filter(id => id !== manualId))
              }}
            />
          </div>
        )
      },
    },
    {
      accessorKey: "reason",
      header: "原因",
      size: 220,
      cell: ({ row }) => (
        <div className="flex min-w-0 items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-white" />
          <div className="min-w-0 max-w-[200px]">
            <div className="truncate" title={row.original.reason}>{row.original.reason}</div>
          </div>
        </div>
      ),
    },
    {
      accessorKey: "platform",
      header: "平台",
      size: 110,
      cell: ({ row }) => <Badge variant="outline">{platformLabels[row.original.platform] || row.original.platform}</Badge>,
    },
    {
      accessorKey: "account",
      header: "账号",
      size: 180,
      cell: ({ row }) => (
        <div className="min-w-0 max-w-[180px]">
          <div className="truncate">{row.original.account_name || row.original.account_id}</div>
        </div>
      ),
    },
    {
      accessorKey: "material",
      header: "素材",
      size: 180,
      cell: ({ row }) => (
        <div className="min-w-0 max-w-[180px]">
          <div className="truncate">{row.original.material_name || row.original.material_id || "-"}</div>
        </div>
      ),
    },
    {
      accessorKey: "created_at",
      header: "创建时间",
      size: 160,
      cell: ({ row }) => (
        <span className="text-xs text-foreground/70">{new Date(row.original.created_at).toLocaleString()}</span>
      ),
    },
    {
      id: "actions",
      header: () => <div className="text-right">操作</div>,
      size: 140,
      cell: ({ row }) => {
        const manualId = getManualId(row.original)
        return (
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => manualId && retryMutation.mutate(manualId)}
              disabled={retryMutation.isPending}
            >
              <Play className="h-4 w-4 mr-1" />
              重试
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => manualId && deleteMutation.mutate(manualId)}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <div className="mx-auto max-w-[1440px] space-y-5 px-4 py-4 md:px-6 md:py-5">
      <PageHeader
        eyebrow="PRISM / OPERATIONS"
        title="任务中心"
        actions={
          <div className="ml-auto flex flex-wrap gap-3">
            {selectedTaskIds.length > 0 && activeTab === "auto" && (
              <>
                <Button
                  variant="outline"
                  className="rounded-2xl border-white/17 bg-black text-white hover:bg-black"
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
                  className="rounded-2xl border-white/17 bg-black text-white hover:bg-black"
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
                  className="rounded-2xl border-white/17 bg-black text-white hover:bg-black"
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
                  className="rounded-2xl border-white/17 bg-black text-white hover:bg-black"
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
                  className="rounded-2xl border-white/17 bg-black text-white hover:bg-black"
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
              className="rounded-2xl border border-border/70 bg-black"
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

      <div className="grid gap-3 md:grid-cols-4">
        <Card className="bg-card border-border/70">
          <CardHeader className="flex items-center gap-3 py-3">
            <Clock3 className="h-5 w-5 text-foreground/70" />
            <div>
              <CardTitle>定时任务</CardTitle>
              <CardDescription>{scheduledCount} 条待执行</CardDescription>
            </div>
          </CardHeader>
        </Card>
        <Card className="bg-card border-border/70">
          <CardHeader className="flex items-center gap-3 py-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            <div>
              <CardTitle>发布成功</CardTitle>
              <CardDescription>{successCount} 条已完成</CardDescription>
            </div>
          </CardHeader>
        </Card>
        <Card className="bg-card border-border/70">
          <CardHeader className="flex items-center gap-3 py-3">
            <XCircle className="h-5 w-5 text-red-400" />
            <div>
              <CardTitle>失败/异常</CardTitle>
              <CardDescription>{errorCount} 条需要关注</CardDescription>
            </div>
          </CardHeader>
        </Card>
        <Card className="bg-card border-border/70">
          <CardHeader className="flex items-center gap-3 py-3">
            <AlertCircle className="h-5 w-5 text-amber-300" />
            <div>
              <CardTitle>人工处理</CardTitle>
              <CardDescription>{manualStats.pending || 0} 条待处理</CardDescription>
            </div>
          </CardHeader>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid h-9 w-full grid-cols-2 rounded-sm border border-border bg-card">
          <TabsTrigger value="auto">自动任务</TabsTrigger>
          <TabsTrigger value="manual">
            人工处理
            {manualStats.pending > 0 && (
              <Badge variant="destructive" className="ml-2">{manualStats.pending}</Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="auto">
          <Card className="bg-card border-border/70">
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
                    className="rounded-2xl border border-border/70"
                    onClick={() => setStatusFilter(tab.value)}
                  >
                    {tab.label}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="rounded-2xl border border-border/70 bg-card p-6 text-center text-sm text-muted-foreground">
                  正在加载任务数据...
                </div>
              ) : isError ? (
                <div className="rounded-2xl border border-white/17 bg-black p-6 text-center text-sm text-white">
                  加载失败: {error?.message || "未知错误"}
                  <Button variant="outline" size="sm" className="ml-4" onClick={() => refetch()}>重试</Button>
                </div>
              ) : (
                <>
                  <DataTable
                    columns={autoColumns}
                    data={filteredTasks}
                    pageSize={10}
                    emptyText="暂无符合条件的任务"
                  />
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="manual">
          <Card className="bg-card border-border/70">
            <CardHeader>
              <CardTitle>人工处理任务</CardTitle>
              <CardDescription>
                这些任务需要人工处理后才能继续发布（如短信验证）
              </CardDescription>
            </CardHeader>
            <CardContent>
              {manualLoading ? (
                <div className="rounded-2xl border border-border/70 bg-black p-6 text-center text-sm text-muted-foreground">
                  正在加载...
                </div>
              ) : manualTasks.length === 0 ? (
                <div className="text-center py-10">
                  <CheckCircle2 className="h-10 w-10 text-white mx-auto mb-4" />
                  <h3 className="text-lg font-medium">暂无待处理任务</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    所有任务都已处理完成
                  </p>
                </div>
              ) : (
                <DataTable
                  columns={manualColumns}
                  data={manualTasks}
                  pageSize={10}
                  emptyText="暂无待处理任务"
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
