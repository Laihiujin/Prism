"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Calendar, Users, FileVideo, Play, CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useToast } from "@/components/ui/use-toast"
import { format } from "date-fns"

export default function CampaignDetailPage() {
    const params = useParams()
    const router = useRouter()
    const { toast } = useToast()
    const campaignId = params.id as string

    // 获取计划详情
    const { data: campaignRes, isLoading: campaignLoading } = useQuery({
        queryKey: ["campaign", campaignId],
        queryFn: async () => {
            const res = await fetch(`/api/v1/campaigns/${campaignId}`)
            if (!res.ok) throw new Error("Failed to fetch campaign")
            return res.json()
        },
    })

    // 获取任务列表
    const { data: tasksRes, isLoading: tasksLoading } = useQuery({
        queryKey: ["campaign-tasks", campaignId],
        queryFn: async () => {
            const res = await fetch(`/api/v1/campaigns/${campaignId}/tasks`)
            if (!res.ok) throw new Error("Failed to fetch tasks")
            return res.json()
        },
    })

    const campaign = campaignRes?.result?.plan
    const tasks = (tasksRes?.result?.items as any[]) || []

    if (campaignLoading || !campaign) {
        return <div className="p-10 text-center">加载中...</div>
    }

    const platformLabels: Record<string, string> = {
        douyin: "抖音",
        kuaishou: "快手",
        xiaohongshu: "小红书",
        bilibili: "B站",
        channels: "视频号",
    }

    // Group tasks by platform
    const tasksByPlatform = tasks.reduce((acc: any, task: any) => {
        const p = task.platform
        if (!acc[p]) acc[p] = []
        acc[p].push(task)
        return acc
    }, {})

    const platforms = Object.keys(tasksByPlatform)

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'finished': return <CheckCircle2 className="w-4 h-4 text-green-500" />
            case 'failed': return <XCircle className="w-4 h-4 text-red-500" />
            case 'running': return <Play className="w-4 h-4 text-blue-500 animate-pulse" />
            case 'pending': return <Clock className="w-4 h-4 text-muted-foreground" />
            default: return <AlertCircle className="w-4 h-4 text-yellow-500" />
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-xl">
                    <ArrowLeft className="h-5 w-5" />
                </Button>
                <div className="flex-1">
                    <h1 className="text-3xl font-semibold">{campaign.name}</h1>
                    <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                        <Badge variant="outline">{campaign.status}</Badge>
                        <span>{format(new Date(campaign.created_at), "yyyy-MM-dd HH:mm")} 创建</span>
                    </div>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold">{tasks.length}</div>
                        <div className="text-xs text-muted-foreground">总任务数</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-green-500">
                            {tasks.filter((t: any) => t.status === 'finished').length}
                        </div>
                        <div className="text-xs text-muted-foreground">已完成</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-blue-500">
                            {tasks.filter((t: any) => t.status === 'running' || t.status === 'pending').length}
                        </div>
                        <div className="text-xs text-muted-foreground">进行中/等待</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-red-500">
                            {tasks.filter((t: any) => t.status === 'failed').length}
                        </div>
                        <div className="text-xs text-muted-foreground">失败</div>
                    </CardContent>
                </Card>
            </div>

            {/* Task List */}
            <Card>
                <CardHeader>
                    <CardTitle>任务详情</CardTitle>
                    <CardDescription>按平台查看生成的任务执行情况</CardDescription>
                </CardHeader>
                <CardContent>
                    {platforms.length === 0 ? (
                        <div className="text-center py-10 text-muted-foreground">暂无任务</div>
                    ) : (
                        <Tabs defaultValue={platforms[0]}>
                            <TabsList>
                                {platforms.map(p => (
                                    <TabsTrigger key={p} value={p}>
                                        {platformLabels[p] || p} ({tasksByPlatform[p].length})
                                    </TabsTrigger>
                                ))}
                            </TabsList>
                            {platforms.map(p => (
                                <TabsContent key={p} value={p} className="mt-4">
                                    <div className="border rounded-md">
                                        <div className="bg-muted/50 px-4 py-3 text-sm font-medium grid grid-cols-6 gap-4">
                                            <div>状态</div>
                                            <div className="col-span-2">账号</div>
                                            <div className="col-span-2">素材</div>
                                            <div>最后更新</div>
                                        </div>
                                        <ScrollArea className="h-[500px]">
                                            {tasksByPlatform[p].map((task: any) => (
                                                <div key={task.task_id} className="px-4 py-3 text-sm grid grid-cols-6 gap-4 border-b last:border-0 hover:bg-muted/30 items-center">
                                                    <div className="flex items-center gap-2">
                                                        {getStatusIcon(task.status)}
                                                        <span className="capitalize">{task.status}</span>
                                                    </div>
                                                    <div className="col-span-2 truncate font-medium">
                                                        {task.account_id}
                                                    </div>
                                                    <div className="col-span-2 truncate text-muted-foreground">
                                                        {task.material_id}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {task.updated_at ? format(new Date(task.updated_at), "MM-dd HH:mm") : "-"}
                                                    </div>
                                                    {task.error_msg && (
                                                        <div className="col-span-6 text-xs text-red-500 mt-1 bg-red-500/10 p-2 rounded">
                                                            错误: {task.error_msg}
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </ScrollArea>
                                    </div>
                                </TabsContent>
                            ))}
                        </Tabs>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
