"use client"

import { useMemo, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
    Boxes,
    Download,
    Loader2,
    Trash2,
    RefreshCcw,
    Server,
    Sparkles,
    Puzzle,
    Component,
    Hammer,
    Power,
    ExternalLink,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"
import { cn } from "@/lib/utils"
import CatalogToolsSection from "./catalog-tools"

interface DevTool {
    id: string
    name: string
    type: string
    repo: string
    description: string
    install_path: string
    installed: boolean
    launchable?: boolean
    buildable?: boolean
    enabled?: boolean
    category?: string
    install_url?: string
    note?: string
}

const TYPE_META: Record<string, { label: string; icon: any; color: string }> = {
    skill: { label: "Skill", icon: Sparkles, color: "bg-black text-white border-border" },
    mcp: { label: "MCP", icon: Server, color: "bg-black text-white border-border" },
    plugin: { label: "插件", icon: Puzzle, color: "bg-black text-white border-border" },
    component: { label: "组件", icon: Component, color: "bg-black text-white border-border" },
}

const CATEGORY_TABS = [
    { key: "all", label: "全部" },
    { key: "skill", label: "Skill" },
    { key: "mcp", label: "MCP" },
    { key: "plugin", label: "插件" },
    { key: "component", label: "组件" },
    { key: "catalog", label: "业务工具" },
]

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

    const launchMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/tools/${id}/launch`, { method: "POST" })
            return res.json()
        },
        onSuccess: (data) => {
            toast({ title: "已打开", description: data.result?.message })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "打开失败", description: err.message })
        }
    })

    const buildMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/tools/${id}/build`, { method: "POST" })
            return res.json()
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["tools"] })
            toast({ title: "构建完成", description: data.result?.message })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "构建失败", description: err.message })
        }
    })

    const toggleSkillMutation = useMutation({
        mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
            const res = await fetch(`/api/v1/tools/${id}/toggle`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enabled }),
            })
            return res.json()
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["tools"] })
            toast({ title: data.result?.message || "已更新" })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "操作失败", description: err.message })
        }
    })

    const [category, setCategory] = useState<string>("all")
    const tools: DevTool[] = data?.result?.tools || []
    const visibleTools = useMemo(
        () => (category === "all" ? tools : tools.filter((t) => t.type === category)),
        [tools, category]
    )
    const skillGroups = useMemo(() => {
        const groups: Record<string, DevTool[]> = {}
        for (const t of visibleTools) {
            if (t.type !== "skill") continue
            const cat = t.category || "未分类"
            ;(groups[cat] = groups[cat] || []).push(t)
        }
        return Object.entries(groups)
    }, [visibleTools])

    const renderToolCard = (tool: DevTool) => {
        const meta = TYPE_META[tool.type] || TYPE_META.component
        const TypeIcon = meta.icon
        const installing = installMutation.isPending && installMutation.variables === tool.id
        const isSkill = tool.type === "skill"
        const enabled = tool.enabled !== false
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
                            {tool.note && (
                                <p className="text-[11px] text-muted-foreground/70 mt-1 leading-relaxed">{tool.note}</p>
                            )}
                        </div>
                    </div>
                    <Badge
                        variant="secondary"
                        className={cn("text-xs shrink-0",
                            isSkill ? (enabled ? "bg-black text-white border-border" : "bg-muted text-muted-foreground")
                                : (tool.installed ? "bg-black text-white border-border" : "bg-muted text-muted-foreground"))}
                    >
                        {isSkill ? (enabled ? "已启用" : "已停用") : (tool.installed ? "已安装" : "未安装")}
                    </Badge>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-col gap-3">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Badge variant="outline" className={cn("text-xs", meta.color)}>
                                {meta.label}
                            </Badge>
                            {tool.install_path && (
                                <code className="font-mono text-[10px]">{tool.install_path}</code>
                            )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {!isSkill && tool.install_url && (
                                <a href={tool.install_url} target="_blank" rel="noreferrer" className="inline-flex">
                                    <Button size="sm" variant="secondary" className="h-8 rounded-lg text-xs bg-foreground/10">
                                        <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                                        安装链接
                                    </Button>
                                </a>
                            )}
                            {isSkill ? (
                                <Button
                                    size="sm"
                                    className="h-8 rounded-lg text-xs"
                                    onClick={() => toggleSkillMutation.mutate({ id: tool.id, enabled: !enabled })}
                                    disabled={toggleSkillMutation.isPending}
                                >
                                    {toggleSkillMutation.isPending && toggleSkillMutation.variables?.id === tool.id ? (
                                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                        <Power className="mr-1.5 h-3.5 w-3.5" />
                                    )}
                                    {toggleSkillMutation.isPending && toggleSkillMutation.variables?.id === tool.id
                                        ? "切换中..."
                                        : enabled ? "停用" : "启用"}
                                </Button>
                            ) : tool.installed ? (
                                <>
                                    {tool.launchable && (
                                        <Button
                                            size="sm"
                                            className="h-8 rounded-lg text-xs"
                                            onClick={() => launchMutation.mutate(tool.id)}
                                            disabled={launchMutation.isPending}
                                        >
                                            {launchMutation.isPending && launchMutation.variables === tool.id ? (
                                                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                                            )}
                                            {launchMutation.isPending && launchMutation.variables === tool.id ? "打开中..." : "打开"}
                                        </Button>
                                    )}
                                    {tool.buildable && (
                                        <Button
                                            size="sm"
                                            className="h-8 rounded-lg text-xs"
                                            onClick={() => buildMutation.mutate(tool.id)}
                                            disabled={buildMutation.isPending}
                                        >
                                            {buildMutation.isPending && buildMutation.variables === tool.id ? (
                                                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <Hammer className="mr-1.5 h-3.5 w-3.5" />
                                            )}
                                            {buildMutation.isPending && buildMutation.variables === tool.id
                                                ? "构建中..."
                                                : tool.id === "persona-studio"
                                                    ? "构建 Dashboard"
                                                    : "构建"}
                                        </Button>
                                    )}
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
                                </>
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
    }

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
            <PageHeader
                title="开发者工具"
                description="按 Skill / MCP / 插件 / 组件 分类管理开发工具，可一键安装、构建、打开或卸载"
                actions={
                    <Button
                        variant="outline"
                        className="rounded-xl border-border/70 bg-black hover:bg-accent/50"
                        onClick={() => refetch()}
                    >
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                }
            />

            <div className="flex flex-wrap items-center gap-2">
                {CATEGORY_TABS.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setCategory(tab.key)}
                        className={cn(
                            "rounded-xl border px-3 py-1.5 text-sm transition",
                            category === tab.key
                                ? "border-border/80 bg-black text-foreground"
                                : "border-border/70 bg-card/40 text-muted-foreground hover:bg-accent/40"
                        )}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {isLoading && (
                <div className="py-12 text-center text-muted-foreground text-sm">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                    加载工具列表...
                </div>
            )}

            {!isLoading && category === "skill" && skillGroups.length > 0 && (
                <div className="space-y-8">
                    {skillGroups.map(([cat, skills]) => (
                        <div key={cat} className="space-y-3">
                            <h3 className="text-sm font-semibold text-foreground">{cat}</h3>
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {skills.map(renderToolCard)}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {!isLoading && category === "catalog" && <CatalogToolsSection />}

            {!isLoading && category !== "skill" && category !== "catalog" && (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {visibleTools.length === 0 ? (
                        <div className="col-span-full rounded-xl border border-border/70 bg-card/40 py-12 text-center text-muted-foreground">
                            该分类下暂无可用工具
                        </div>
                    ) : (
                        visibleTools.map(renderToolCard)
                    )}
                </div>
            )}

            {!isLoading && category === "skill" && skillGroups.length === 0 && (
                <div className="rounded-xl border border-border/70 bg-card/40 py-12 text-center text-muted-foreground">
                    暂无可用技能
                </div>
            )}
        </div>
    )
}
