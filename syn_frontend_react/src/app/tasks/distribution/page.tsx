"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, QrCode, RefreshCcw, Loader2 } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/components/ui/use-toast"
import { Badge } from "@/components/ui/badge"
import { fetcher } from "@/lib/api"
import { NaturalDatePicker } from "@/components/ui/natural-date-picker"
import type { Material } from "@/lib/mock-data"
import { TaskDrawer } from "./components/task-drawer"
import { Progress } from "@/components/ui/progress"
import { PublishOtpDialog } from "@/components/publish/publish-otp-dialog"

interface DistributionTask {
    task_id: number
    qr_token: string
    platform: string
    poi_location: string
    expire_time: string
    title_template: string
    created_at: string
    total_videos: number
    available_count: number
    distributed_count: number
}

interface CreateTaskParams {
    platform: string
    title_template: string
    poi_location: string
    expire_time: string
    video_files: string[] // file paths
}

export default function DistributionPage() {
    const { toast } = useToast()
    const queryClient = useQueryClient()
    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [selectedTask, setSelectedTask] = useState<{
        id: string
        platform: string
        title: string
        tags: string[]
        poi?: string
        expiryDate?: string
        materials: string[]
        status: 'pending' | 'dispatched' | 'published'
        assignedAccounts: number
        createdAt: string
    } | null>(null)
    const [drawerOpen, setDrawerOpen] = useState(false)
    const [createProgress, setCreateProgress] = useState(0)
    const [isCreating, setIsCreating] = useState(false)
    const [formData, setFormData] = useState<CreateTaskParams>({
        platform: "douyin",
        title_template: "",
        poi_location: "",
        expire_time: "",
        video_files: []
    })

    // Fetch tasks
    const { data: tasksResponse, isLoading, refetch } = useQuery({
        queryKey: ["distribution-tasks"],
        queryFn: () => fetcher("/api/tasks/distribution"),
    })

    const tasks = (tasksResponse as DistributionTask[]) || []
    const normalizedTasks = useMemo(() => {
        return tasks.map((task) => ({
            ...task,
            status: task.distributed_count > 0 ? "dispatched" : "pending",
        }))
    }, [tasks])

    const [statusFilter, setStatusFilter] = useState<"pending" | "dispatched">("pending")
    const [page, setPage] = useState(1)
    const pageSize = 10

    const filteredTasks = useMemo(() => {
        return normalizedTasks.filter((task) =>
            statusFilter === "pending"
                ? task.distributed_count === 0 || task.available_count > 0
                : task.distributed_count > 0
        )
    }, [normalizedTasks, statusFilter])

    const totalPages = Math.max(1, Math.ceil(filteredTasks.length / pageSize))
    const currentPage = Math.min(page, totalPages)
    const start = (currentPage - 1) * pageSize
    const end = start + pageSize
    const paginatedTasks = filteredTasks.slice(start, end)

    const pendingCount = normalizedTasks.filter((t) => t.status === "pending").length
    const dispatchedCount = normalizedTasks.filter((t) => t.status === "dispatched").length

    // Fetch materials
    const { data: materialsResponse } = useQuery({
        queryKey: ["materials"],
        queryFn: () => fetcher("/api/materials"),
    })
    const materials = useMemo(() => {
        const raw = materialsResponse as any
        if (Array.isArray(raw)) return raw as Material[]
        if (Array.isArray(raw?.data?.data)) return raw.data.data as Material[]
        if (Array.isArray(raw?.data)) return raw.data as Material[]
        return []
    }, [materialsResponse])

    // Create task mutation
    const createMutation = useMutation({
        mutationFn: async (data: CreateTaskParams) => {
            // Start progress simulation
            setIsCreating(true)
            setCreateProgress(0)

            // Simulate progress
            const progressInterval = setInterval(() => {
                setCreateProgress(prev => {
                    if (prev >= 90) {
                        clearInterval(progressInterval)
                        return 90
                    }
                    return prev + 15
                })
            }, 200)

            const response = await fetch("/api/task/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            })

            clearInterval(progressInterval)

            const payload = await response.json().catch(() => ({}))
            if (!response.ok || payload?.code !== 200) {
                throw new Error(payload?.msg || "创建失败")
            }
            return payload
        },
        onSuccess: () => {
            setCreateProgress(100)
            toast({ title: "任务创建成功" })

            setTimeout(() => {
                setIsCreateOpen(false)
                setCreateProgress(0)
                setIsCreating(false)
            }, 500)

            queryClient.invalidateQueries({ queryKey: ["distribution-tasks"] })
            setFormData({
                platform: "douyin",
                title_template: "",
                poi_location: "",
                expire_time: "",
                video_files: []
            })
        },
        onError: (error) => {
            setCreateProgress(0)
            setIsCreating(false)
            toast({ variant: "destructive", title: "创建失败", description: String(error) })
        }
    })

    const handleCreate = () => {
        if (!formData.title_template) {
            toast({ variant: "destructive", title: "请输入标题模板" })
            return
        }
        if (formData.video_files.length !== 1) {
            toast({ variant: "destructive", title: "单个派发任务只能选择 1 条素材" })
            return
        }
        createMutation.mutate(formData)
    }

    const toggleMaterial = (filePath: string) => {
        // 单个派发任务只允许一条素材，点击新的素材会替换之前的选择
        setFormData(prev => {
            const exists = prev.video_files.includes(filePath)
            if (exists) {
                return { ...prev, video_files: [] }
            } else {
                return { ...prev, video_files: [filePath] }
            }
        })
    }

    const handleDelete = async (taskId: number) => {
        try {
            const res = await fetch(`/api/task/delete?task_id=${taskId}`, { method: "DELETE" })
            const payload = await res.json().catch(() => ({}))
            if (!res.ok || payload?.code !== 200) {
                throw new Error(payload?.msg || "删除失败")
            }
            toast({ title: "任务已删除" })
            refetch()
        } catch (error) {
            toast({ variant: "destructive", title: "删除失败", description: String(error) })
        }
    }

    return (
        <div className="space-y-6 p-6">
            <div className="flex flex-wrap items-center gap-4">
                <div>
                    <p className="text-sm uppercase tracking-[0.3em] text-white/50">任务分发</p>
                    <h1 className="mt-2 text-3xl font-semibold">扫码派发管理</h1>
                    <p className="text-sm text-white/60">管理二维码扫码领视频任务，监控库存与分发状态</p>
                </div>
                <div className="ml-auto flex gap-3">
                    <Button variant="ghost" onClick={() => refetch()} disabled={isLoading}>
                        <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                        刷新
                    </Button>

                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="mr-2 h-4 w-4" />
                                创建派发任务
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[600px]">
                            <DialogHeader>
                                <DialogTitle>创建新派发任务</DialogTitle>
                                <DialogDescription>
                                    配置任务基本信息，并选择要分发的视频素材。
                                </DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="platform" className="text-right">
                                        平台
                                    </Label>
                                    <Select
                                        value={formData.platform}
                                        onValueChange={(v) => setFormData({ ...formData, platform: v })}
                                    >
                                        <SelectTrigger className="col-span-3">
                                            <SelectValue placeholder="选择平台" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="douyin">抖音</SelectItem>
                                            <SelectItem value="kuaishou">快手</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="title" className="text-right">
                                        标题模板
                                    </Label>
                                    <Input
                                        id="title"
                                        value={formData.title_template}
                                        onChange={(e) => setFormData({ ...formData, title_template: e.target.value })}
                                        className="col-span-3"
                                        placeholder="例如：今天去{poi}打卡了！"
                                    />
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="poi" className="text-right">
                                        POI 位置
                                    </Label>
                                    <Input
                                        id="poi"
                                        value={formData.poi_location}
                                        onChange={(e) => setFormData({ ...formData, poi_location: e.target.value })}
                                        className="col-span-3"
                                        placeholder="可选，例如：某某餐厅"
                                    />
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <div className="col-span-4">
                                        <NaturalDatePicker
                                            value={formData.expire_time}
                                            onChange={(v) => setFormData({ ...formData, expire_time: v })}
                                            label="过期时间"
                                            placeholder="明天 或 下周"
                                        />
                                    </div>
                                </div>

                                <div className="grid grid-cols-4 gap-4">
                                    <Label className="text-right pt-2">
                                        选择素材
                                        <span className="block text-xs text-white/50 mt-1">
                                            已选: {formData.video_files.length} / 1
                                        </span>
                                    </Label>
                                    <div className="col-span-3 border border-white/10 rounded-md h-[200px] overflow-y-auto p-2 space-y-1">
                                        {materials.length === 0 ? (
                                            <p className="text-sm text-white/50 text-center py-4">暂无素材，请先上传</p>
                                        ) : (
                                            materials.map((file) => {
                                                const fileKey = file.storageKey || file.fileUrl
                                                if (!fileKey) return null
                                                const checked = formData.video_files.includes(fileKey)
                                                return (
                                                    <div
                                                        key={file.id}
                                                        className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm ${checked
                                                            ? "bg-primary/20 text-primary"
                                                            : "hover:bg-white/5"
                                                            }`}
                                                        onClick={() => toggleMaterial(fileKey)}
                                                    >
                                                        <div className={`w-4 h-4 rounded border flex items-center justify-center ${checked
                                                            ? "border-primary bg-primary text-primary-foreground"
                                                            : "border-white/30"
                                                            }`}>
                                                            {checked && <Plus className="w-3 h-3" />}
                                                        </div>
                                                        <span className="truncate flex-1">{file.filename}</span>
                                                    </div>
                                                )
                                            })
                                        )}
                                    </div>
                                </div>
                            </div>
                            <DialogFooter>
                                {isCreating && (
                                    <div className="w-full space-y-2 mb-4">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-white/60">创建进度</span>
                                            <span className="text-white">{createProgress}%</span>
                                        </div>
                                        <Progress value={createProgress} className="h-2" />
                                        <p className="text-xs text-white/50 text-center">
                                            {createProgress < 30 && "正在准备..."}
                                            {createProgress >= 30 && createProgress < 60 && "正在创建任务..."}
                                            {createProgress >= 60 && createProgress < 90 && "正在配置素材..."}
                                            {createProgress >= 90 && createProgress < 100 && "即将完成..."}
                                            {createProgress === 100 && "创建成功！"}
                                        </p>
                                    </div>
                                )}
                                <Button type="submit" onClick={handleCreate} disabled={createMutation.isPending}>
                                    {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    创建任务
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            <Card className="border-white/10 bg-black">
                <CardHeader>
                    <CardTitle>任务列表</CardTitle>
                    <CardDescription>查看所有已创建的扫码派发任务</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-wrap items-center gap-3 mb-4">
                        <div className="inline-flex rounded-full bg-white/5 p-1 border border-white/10">
                            <Button
                                variant={statusFilter === "pending" ? "default" : "ghost"}
                                size="sm"
                                className="rounded-full"
                                onClick={() => {
                                    setStatusFilter("pending")
                                    setPage(1)
                                }}
                            >
                                待派发 ({pendingCount})
                            </Button>
                            <Button
                                variant={statusFilter === "dispatched" ? "default" : "ghost"}
                                size="sm"
                                className="rounded-full"
                                onClick={() => {
                                    setStatusFilter("dispatched")
                                    setPage(1)
                                }}
                            >
                                已派发 ({dispatchedCount})
                            </Button>
                        </div>
                        <p className="text-sm text-white/60">
                            共 {filteredTasks.length} 条记录，每页 10 条，当前第 {currentPage} / {totalPages} 页
                        </p>
                    </div>

                    <Table>
                        <TableHeader>
                            <TableRow className="border-white/10 hover:bg-white/5">
                                <TableHead>ID</TableHead>
                                <TableHead>平台</TableHead>
                                <TableHead>标题模板</TableHead>
                                <TableHead>库存 (可用/总数)</TableHead>
                                <TableHead>已派发</TableHead>
                                <TableHead>创建时间</TableHead>
                                <TableHead>操作</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {paginatedTasks.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="text-center text-white/50">
                                        暂无任务
                                    </TableCell>
                                </TableRow>
                            ) : (
                                paginatedTasks.map((task) => (
                                    <TableRow
                                        key={task.task_id}
                                        className="border-white/10 hover:bg-white/5 cursor-pointer"
                                        onClick={() => {
                                            setSelectedTask({
                                                id: String(task.task_id),
                                                platform: task.platform,
                                                title: task.title_template,
                                                tags: [],
                                                poi: task.poi_location,
                                                expiryDate: task.expire_time,
                                                materials: [],
                                                status: task.distributed_count > 0 ? 'dispatched' : 'pending',
                                                assignedAccounts: task.distributed_count,
                                                createdAt: task.created_at,
                                            })
                                            setDrawerOpen(true)
                                        }}
                                    >
                                        <TableCell>{task.task_id}</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{task.platform}</Badge>
                                        </TableCell>
                                        <TableCell className="max-w-[200px] truncate" title={task.title_template}>
                                            {task.title_template}
                                        </TableCell>
                                        <TableCell>
                                            <span className="text-emerald-400">{task.available_count}</span> / {task.total_videos}
                                        </TableCell>
                                        <TableCell>{task.distributed_count}</TableCell>
                                        <TableCell className="text-sm text-white/50">
                                            {new Date(task.created_at).toLocaleString()}
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-3">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        setSelectedTask({
                                                            id: String(task.task_id),
                                                            platform: task.platform,
                                                            title: task.title_template,
                                                            tags: [],
                                                            poi: task.poi_location,
                                                            expiryDate: task.expire_time,
                                                            materials: [],
                                                            status: task.distributed_count > 0 ? 'dispatched' : 'pending',
                                                            assignedAccounts: task.distributed_count,
                                                            createdAt: task.created_at,
                                                        })
                                                        setDrawerOpen(true)
                                                    }}
                                                    className="rounded-xl border border-white/10"
                                                >
                                                    <QrCode className="mr-2 h-4 w-4" />
                                                    QR派发
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="rounded-xl border border-red-500/30 text-red-200 hover:bg-red-500/20"
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        handleDelete(task.task_id)
                                                    }}
                                                >
                                                    删除
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>

                    <div className="flex items-center justify-between mt-4 text-sm text-white/70">
                        <span>
                            显示 {filteredTasks.length === 0 ? 0 : start + 1}-{Math.min(end, filteredTasks.length)} / {filteredTasks.length}
                        </span>
                        <div className="space-x-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setPage((p) => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                            >
                                上一页
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                            >
                                下一页
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Task Drawer */}
            {selectedTask && (
                <TaskDrawer
                    task={selectedTask}
                    open={drawerOpen}
                    onOpenChange={setDrawerOpen}
                    onTaskUpdate={() => refetch()}
                />
            )}

            <PublishOtpDialog />
        </div>
    )
}
