"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
    Boxes,
    Download,
    Loader2,
    Trash2,
    RefreshCcw,
    Server,
    Terminal,
    Bot,
    AppWindow,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"
import { cn } from "@/lib/utils"

interface DevTool {
    id: string
    name: string
    type: string
    repo: string
    description: string
    install_path: string
    installed: boolean
}

const TYPE_META: Record<string, { label: string; icon: any; color: string }> = {
    agent: { label: "Agent", icon: Bot, color: "bg-violet-500/15 text-violet-400 border-violet-500/30" },
    mcp: { label: "MCP", icon: Server, color: "bg-sky-500/15 text-sky-400 border-sky-500/30" },
    cli: { label: "CLI", icon: Terminal, color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
    desktop: { label: "桌面", icon: AppWindow, color: "bg-amber-500/15 text-amber-400 border-amber-500/30" },
}

export default function ToolsPage() {
    const queryClient = useQueryClient()
    const { toast } = useToast()

    const { data, isLoading, refetch } = useQuery({
        queryKey: ["tools"],
        queryFn: async () => {
            const res = await fetch("/api/v1/tools")
            return res.json()
        }
    })

    const installMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/tools/${id}/install`, { method: "POST" })
            return res.json()
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["tools"] })
            toast({ title: "安装完成", description: data.result?.message })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "安装失败", description: err.message })
        }
    })

    const uninstallMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/tools/${id}/uninstall`, { method: "POST" })
            return res.json()
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["tools"] })
            toast({ title: "已卸载", description: data.result?.message })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "卸载失败", description: err.message })
        }
    })

    const tools: DevTool[] = data?.result?.tools || []

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
            <PageHeader
                title="开发者工具"
                description="按需一键安装 MCP / Agent / CLI 开发工具，克隆到 tools/ 目录"
                actions={
                    <Button
                        variant="outline"
                        className="rounded-xl border-border/70 bg-foreground/5 hover:bg-accent/50"
                        onClick={() => refetch()}
                    >
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                }
            />

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {isLoading && (
                    <div className="col-span-full py-12 text-center text-muted-foreground text-sm">
                        <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                        加载工具列表...
                    </div>
                )}

                {!isLoading && tools.length === 0 && (
                    <div className="col-span-full rounded-xl border border-border/70 bg-card/40 py-12 text-center text-muted-foreground">
                        暂无可用工具
                    </div>
                )}

                {tools.map((tool) => {
                    const meta = TYPE_META[tool.type] || TYPE_META.cli
                    const TypeIcon = meta.icon
                    const installing = installMutation.isPending && installMutation.variables === tool.id
                    return (
                        <Card key={tool.id} className="bg-card/40 border-border/70">
                            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                                <div className="flex items-start gap-3">
                                    <div className={cn("rounded-lg p-2 border", meta.color)}>
                                        <TypeIcon className="h-5 w-5" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">{tool.name}</CardTitle>
                                        <p className="text-xs text-muted-foreground mt-0.5">{tool.description}</p>
                                    </div>
                                </div>
                                <Badge
                                    variant="secondary"
                                    className={cn("text-xs shrink-0",
                                        tool.installed
                                            ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                                            : "bg-muted text-muted-foreground")}
                                >
                                    {tool.installed ? "已安装" : "未安装"}
                                </Badge>
                            </CardHeader>
                            <CardContent>
                                <div className="flex flex-col gap-3">
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <Badge variant="outline" className={cn("text-xs", meta.color)}>
                                            {meta.label}
                                        </Badge>
                                        {tool.install_path && (
                                            <code className="font-mono text-[10px]">tools/{tool.install_path}</code>
                                        )}
                                    </div>
                                    <div className="flex gap-2">
                                        {tool.installed ? (
                                            <Button
                                                size="sm"
                                                variant="destructive"
                                                className="h-8 rounded-lg text-xs"
                                                onClick={() => uninstallMutation.mutate(tool.id)}
                                                disabled={uninstallMutation.isPending}
                                            >
                                                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                                                卸载
                                            </Button>
                                        ) : (
                                            <Button
                                                size="sm"
                                                className="h-8 rounded-lg text-xs"
                                                onClick={() => installMutation.mutate(tool.id)}
                                                disabled={installing}
                                            >
                                                {installing ? (
                                                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                                ) : (
                                                    <Download className="mr-1.5 h-3.5 w-3.5" />
                                                )}
                                                {installing ? "安装中..." : "一键安装"}
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )
                })}
            </div>
        </div>
    )
}
