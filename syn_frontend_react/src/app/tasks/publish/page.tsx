"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { RefreshCcw, CheckCircle2, XCircle, Clock, Loader2, AlertCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { Progress } from "@/components/ui/progress"

interface TaskStatus {
    task_id: string
    task_type: string
    status: string
    priority: number
    created_at: string
    started_at?: string
    completed_at?: string
    retry_count: number
    data: any
    result?: any
}

interface QueueStats {
    pending: number
    running: number
    completed: number
    failed: number
    total: number
}

const STATUS_BADGE_MAP = {
    pending: { label: "等待中", variant: "secondary" as const, icon: Clock },
    running: { label: "执行中", variant: "default" as const, icon: Loader2 },
    success: { label: "成功", variant: "outline" as const, icon: CheckCircle2 },
    failed: { label: "失败", variant: "destructive" as const, icon: XCircle },
}

const PLATFORM_MAP: Record<number, string> = {
    1: "小红书",
    2: "视频号",
    3: "抖音",
    4: "快手",
    5: "B站",
}

export default function PublishTasksPage() {
    const { toast } = useToast()
    const [autoRefresh, setAutoRefresh] = useState(true)

    // 获取队列统计
    const { data: statsData, refetch: refetchStats } = useQuery({
        queryKey: ['task-stats'],
        queryFn: async () => {
            const res = await fetch('/api/tasks/stats')
            if (!res.ok) throw new Error('Failed to fetch stats')
            const result = await res.json()
            return result.data as QueueStats
        },
        refetchInterval: autoRefresh ? 3000 : false,
    })

    // 获取任务列表
    const { data: tasksData, isLoading, refetch: refetchTasks } = useQuery({
        queryKey: ['publish-tasks'],
        queryFn: async () => {
            const res = await fetch('/api/tasks/list?limit=500')
            if (!res.ok) throw new Error('Failed to fetch tasks')
            const result = await res.json()
            return result.data as TaskStatus[]
        },
        refetchInterval: autoRefresh ? 5000 : false,
    })

    const stats = statsData || { pending: 0, running: 0, completed: 0, failed: 0, total: 0 }
    const tasks = tasksData || []

    const handleRefresh = () => {
        refetchStats()
        refetchTasks()
        toast({ title: "已刷新" })
    }

    const handleCancelTask = async (taskId: string) => {
        try {
            const res = await fetch(`/api/tasks/${taskId}/cancel`, {
                method: 'POST',
            })
            const result = await res.json()

            if (result.success) {
                toast({ title: "任务已取消" })
                refetchTasks()
            } else {
                toast({
                    variant: "destructive",
                    title: "取消失败",
                    description: result.error,
                })
            }
        } catch (error) {
            toast({
                variant: "destructive",
                title: "操作失败",
                description: String(error),
            })
        }
    }

    const getTaskProgress = (task: TaskStatus) => {
        if (task.status === 'success') return 100
        if (task.status === 'failed') return 100
        if (task.status === 'running') return 50
        return 0
    }

    const formatDuration = (task: TaskStatus) => {
        if (!task.started_at) return '-'

        const start = new Date(task.started_at).getTime()
        const end = task.completed_at ? new Date(task.completed_at).getTime() : Date.now()
        const duration = Math.floor((end - start) / 1000)

        if (duration < 60) return `${duration}秒`
        return `${Math.floor(duration / 60)}分${duration % 60}秒`
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-semibold">发布任务管理</h1>
                    <p className="text-sm text-white/60 mt-1">
                        监控发布任务状态和日志
                    </p>
                </div>
                <div className="flex gap-2 items-center">
                    <label className="flex items-center gap-2 text-sm">
                        <input
                            type="checkbox"
                            checked={autoRefresh}
                            onChange={(e) => setAutoRefresh(e.target.checked)}
                            className="rounded"
                        />
                        自动刷新
                    </label>
                    <Button
                        variant="outline"
                        className="rounded-2xl"
                        onClick={handleRefresh}
                    >
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                </div>
            </div>

            {/* Statistics Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">
                            总任务
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats.total}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">
                            等待中
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-gray-400">{stats.pending}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">
                            执行中
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-blue-400">{stats.running}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">
                            已完成
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-green-400">{stats.completed}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">
                            失败
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-red-400">{stats.failed}</div>
                    </CardContent>
                </Card>
            </div>

            {/* Tasks Table */}
            <Card>
                <CardHeader>
                    <CardTitle>任务列表</CardTitle>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <div className="flex justify-center items-center py-8">
                            <Loader2 className="h-8 w-8 animate-spin text-white/60" />
                        </div>
                    ) : tasks.length === 0 ? (
                        <div className="text-center py-8 text-white/60">
                            暂无任务
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>任务ID</TableHead>
                                    <TableHead>平台</TableHead>
                                    <TableHead>账号</TableHead>
                                    <TableHead>标题</TableHead>
                                    <TableHead>状态</TableHead>
                                    <TableHead>进度</TableHead>
                                    <TableHead>耗时</TableHead>
                                    <TableHead>重试</TableHead>
                                    <TableHead>创建时间</TableHead>
                                    <TableHead>操作</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {tasks.map((task) => {
                                    const statusConfig = STATUS_BADGE_MAP[task.status as keyof typeof STATUS_BADGE_MAP]
                                    const Icon = statusConfig?.icon || AlertCircle
                                    const platform = PLATFORM_MAP[task.data?.platform] || '未知'

                                    return (
                                        <TableRow key={task.task_id}>
                                            <TableCell className="font-mono text-xs">
                                                {task.task_id.slice(0, 8)}...
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant="outline">{platform}</Badge>
                                            </TableCell>
                                            <TableCell className="max-w-[100px] truncate">
                                                {task.data?.account_id || '-'}
                                            </TableCell>
                                            <TableCell className="max-w-[200px] truncate">
                                                {task.data?.title || '-'}
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant={statusConfig?.variant || "secondary"}>
                                                    <Icon className="mr-1 h-3 w-3" />
                                                    {statusConfig?.label || task.status}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <div className="w-24">
                                                    <Progress value={getTaskProgress(task)} />
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-xs">
                                                {formatDuration(task)}
                                            </TableCell>
                                            <TableCell>
                                                {task.retry_count > 0 && (
                                                    <Badge variant="outline" className="text-xs">
                                                        {task.retry_count}次
                                                    </Badge>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-xs text-white/60">
                                                {new Date(task.created_at).toLocaleString('zh-CN', {
                                                    month: '2-digit',
                                                    day: '2-digit',
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                })}
                                            </TableCell>
                                            <TableCell>
                                                {task.status === 'pending' || task.status === 'running' ? (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => handleCancelTask(task.task_id)}
                                                    >
                                                        取消
                                                    </Button>
                                                ) : task.status === 'failed' && task.result?.error ? (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => {
                                                            toast({
                                                                variant: "destructive",
                                                                title: "错误详情",
                                                                description: task.result.error,
                                                            })
                                                        }}
                                                    >
                                                        查看错误
                                                    </Button>
                                                ) : null}
                                            </TableCell>
                                        </TableRow>
                                    )
                                })}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
