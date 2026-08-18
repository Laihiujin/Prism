"use client"

import { useMemo, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Search, Package, MoreHorizontal, Pause, Play, Trash2 } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { useToast } from "@/components/ui/use-toast"
import { useRouter } from "next/navigation"
import { CreateCampaignDialog } from "@/components/campaigns/create-campaign-dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { PageHeader } from "@/components/layout/page-scaffold"

export default function CampaignsPage() {
    const router = useRouter()
    const { toast } = useToast()
    const queryClient = useQueryClient()
    const [createDialogOpen, setCreateDialogOpen] = useState(false)
    const [searchKeyword, setSearchKeyword] = useState("")

    // 获取所有计划 (使用新API)
    const { data: response, isLoading } = useQuery({
        queryKey: ["campaigns"],
        queryFn: async () => {
            const res = await fetch("/api/v1/campaigns/list")
            if (!res.ok) throw new Error("Failed to fetch campaigns")
            return res.json()
        },
    })

    const campaigns = (response?.result?.items as any[]) || []

    // 删除计划
    const deleteMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/campaigns/${id}`, { method: "DELETE" })
            if (!res.ok) throw new Error("Failed to delete")
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["campaigns"] })
            toast({ title: "计划已删除" })
        },
    })

    // 暂停/恢复计划
    const toggleStatusMutation = useMutation({
        mutationFn: async ({ id, action }: { id: string, action: 'pause' | 'resume' }) => {
            const res = await fetch(`/api/v1/campaigns/${id}/${action}`, { method: "POST" })
            if (!res.ok) throw new Error(`Failed to ${action}`)
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["campaigns"] })
            toast({ title: "状态已更新" })
        }
    })

    const executeMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/campaigns/${id}/execute`, { method: "POST" })
            if (!res.ok) throw new Error("Failed to execute")
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["campaigns"] })
            toast({ title: "Campaign executed" })
        }
    })

    const filteredCampaigns = useMemo(() => {
        if (!searchKeyword.trim()) return campaigns
        return campaigns.filter((c: any) => {
            const target = `${c.name ?? ""} ${c.remark ?? ""}`.toLowerCase()
            return target.includes(searchKeyword.toLowerCase())
        })
    }, [campaigns, searchKeyword])

    const getStatusBadge = (status: string) => {
        const variants: Record<string, string> = {
            draft: "secondary",
            running: "default",
            paused: "outline",
            finished: "secondary",
        }
        const labels: Record<string, string> = {
            draft: "草稿",
            running: "运行中",
            paused: "已暂停",
            finished: "已完成",
        }
        return (
            <Badge variant={variants[status] as any} className={status === 'running' ? 'bg-green-500 hover:bg-green-600' : ''}>
                {labels[status] || status}
            </Badge>
        )
    }

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
            <PageHeader
                title="投放计划"
                description="管理多账号、多素材、多日的矩阵投放"
                actions={
                    <Button className="rounded-2xl" onClick={() => setCreateDialogOpen(true)}>
                        <Plus className="mr-2 h-4 w-4" />
                        新建计划
                    </Button>
                }
            />

            <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="搜索计划名称..."
                        className="pl-9 rounded-xl bg-black border-white/10"
                        value={searchKeyword}
                        onChange={e => setSearchKeyword(e.target.value)}
                    />
                </div>
            </div>

            {isLoading ? (
                <div className="text-center py-10 text-muted-foreground">加载中...</div>
            ) : filteredCampaigns.length === 0 ? (
                <Card className="border-dashed border-white/10 bg-transparent">
                    <CardContent className="flex flex-col items-center justify-center py-10 text-center">
                        <Package className="h-10 w-10 text-muted-foreground mb-4" />
                        <h3 className="text-lg font-medium">暂无投放计划</h3>
                        <p className="text-sm text-muted-foreground mt-1 mb-4">
                            创建一个新的矩阵计划来开始自动化投放
                        </p>
                        <Button variant="outline" onClick={() => setCreateDialogOpen(true)}>
                            创建计划
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {filteredCampaigns.map((campaign: any) => (
                        <Card key={campaign.id} className="bg-black border-white/10 hover:bg-white/[0.07] transition-all group">
                            <CardHeader className="pb-3">
                                <div className="flex justify-between items-start gap-2">
                                    <div className="space-y-1">
                                        <CardTitle className="text-lg leading-tight">{campaign.name}</CardTitle>
                                        <div className="text-xs text-muted-foreground">
                                            {format(new Date(campaign.created_at), "yyyy-MM-dd HH:mm")}
                                        </div>
                                    </div>
                                    {getStatusBadge(campaign.status)}
                                </div>
                            </CardHeader>
                            <CardContent className="pb-3 space-y-4">
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                                    <div className="bg-black border border-white/10 rounded-lg p-2">
                                        <div className="text-xl font-bold">{campaign.task_count}</div>
                                        <div className="text-xs text-muted-foreground">Tasks</div>
                                    </div>
                                    <div className="bg-black border border-white/10 rounded-lg p-2">
                                        <div className="text-xl font-bold">{campaign.platforms?.length || 0}</div>
                                        <div className="text-xs text-muted-foreground">Platforms</div>
                                    </div>
                                    <div className="bg-black border border-white/10 rounded-lg p-2">
                                        <div className="text-xl font-bold">{campaign.account_ids?.length || 0}</div>
                                        <div className="text-xs text-muted-foreground">Accounts</div>
                                    </div>
                                    <div className="bg-black border border-white/10 rounded-lg p-2">
                                        <div className="text-xl font-bold">{campaign.material_ids?.length || 0}</div>
                                        <div className="text-xs text-muted-foreground">Materials</div>
                                    </div>
                                </div>

                                <div className="flex flex-wrap gap-2 text-xs">
                                    <Badge variant="outline" className="bg-white/5 border-white/10 text-white/70">
                                        schedule: {campaign.schedule_type || "n/a"}
                                    </Badge>
                                    <Badge variant="outline" className="bg-white/5 border-white/10 text-white/70">
                                        interval: {campaign.interval_enabled ? `${campaign.interval_mode} ${campaign.interval_minutes}m` : "off"}
                                    </Badge>
                                </div>

                                <div className="space-y-1.5">
                                    <div className="flex justify-between text-xs">
                                        <span className="text-muted-foreground">执行进度</span>
                                        <span>0%</span> {/* TODO: Real progress */}
                                    </div>
                                    <Progress value={0} className="h-1.5" />
                                </div>
                            </CardContent>
                            <CardFooter className="pt-0 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Button variant="ghost" size="sm" className="text-xs" onClick={() => router.push(`/campaigns/${campaign.id}`)}>
                                        Details
                                    </Button>
                                    {campaign.status === 'draft' && (
                                        <Button
                                            size="sm"
                                            onClick={() => executeMutation.mutate(campaign.id)}
                                            disabled={executeMutation.isPending}
                                        >
                                            Execute
                                        </Button>
                                    )}
                                    {campaign.status === 'paused' && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => toggleStatusMutation.mutate({ id: campaign.id, action: 'resume' })}
                                            disabled={toggleStatusMutation.isPending}
                                        >
                                            Resume
                                        </Button>
                                    )}
                                </div>
                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button variant="ghost" size="icon" className="h-8 w-8">
                                            <MoreHorizontal className="h-4 w-4" />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                        <DropdownMenuLabel>操作</DropdownMenuLabel>
                                        <DropdownMenuItem onClick={() => router.push(`/campaigns/${campaign.id}`)}>
                                            查看详情
                                        </DropdownMenuItem>
                                        <DropdownMenuSeparator />
                                        {campaign.status === 'draft' ? (
                                            <DropdownMenuItem onClick={() => executeMutation.mutate(campaign.id)} >
                                                <Play className="mr-2 h-4 w-4" /> Execute
                                            </DropdownMenuItem>
                                        ) : null}
                                        {campaign.status === 'running' ? (
                                            <DropdownMenuItem onClick={() => toggleStatusMutation.mutate({ id: campaign.id, action: 'pause' })}>
                                                <Pause className="mr-2 h-4 w-4" /> 暂停投放
                                            </DropdownMenuItem>
                                        ) : campaign.status === 'paused' ? (
                                            <DropdownMenuItem onClick={() => toggleStatusMutation.mutate({ id: campaign.id, action: 'resume' })}>
                                                <Play className="mr-2 h-4 w-4" /> 恢复投放
                                            </DropdownMenuItem>
                                        ) : null}
                                        <DropdownMenuSeparator />
                                        <DropdownMenuItem
                                            className="text-red-500 focus:text-red-500"
                                            onClick={() => {
                                                if (confirm('确定删除此计划吗？')) deleteMutation.mutate(campaign.id)
                                            }}
                                        >
                                            <Trash2 className="mr-2 h-4 w-4" /> 删除计划
                                        </DropdownMenuItem>
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </CardFooter>
                        </Card>
                    ))}
                </div>
            )}

            <CreateCampaignDialog
                open={createDialogOpen}
                onOpenChange={setCreateDialogOpen}
                onSuccess={() => queryClient.invalidateQueries({ queryKey: ["campaigns"] })}
            />
        </div>
    )
}