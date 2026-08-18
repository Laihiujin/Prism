"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Edit, Trash2, Copy, Settings } from "lucide-react"

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
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { fetcher } from "@/lib/api"

interface PresetManagementProps {
    onSelect?: (preset: any) => void
}

export function PresetManagement({ onSelect }: PresetManagementProps) {
    const { toast } = useToast()
    const queryClient = useQueryClient()
    const [createDialogOpen, setCreateDialogOpen] = useState(false)
    const [formData, setFormData] = useState({
        name: "",
        description: "",
        platforms: [] as string[],
        default_title: "",
        default_tags: "",
    })

    // 获取所有预设 
    const { data: response, isLoading } = useQuery({
        queryKey: ["publish-presets"],
        queryFn: () => fetcher("/api/publish-presets", {} as any),
    })

    const presets = (response?.data as any[]) || []

    // 创建预设
    const createMutation = useMutation({
        mutationFn: async (data: any) => {
            const res = await fetch("/api/publish-presets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
            })
            if (!res.ok) throw new Error("Failed to create preset")
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["publish-presets"] })
            toast({ title: "预设创建成功" })
            setCreateDialogOpen(false)
            setFormData({
                name: "",
                description: "",
                platforms: [],
                default_title: "",
                default_tags: "",
            })
        },
        onError: () => {
            toast({ variant: "destructive", title: "创建失败" })
        },
    })

    // 删除预设
    const deleteMutation = useMutation({
        mutationFn: async (presetId: number) => {
            const res = await fetch(`/api/publish-presets/${presetId}`, { method: "DELETE" })
            if (!res.ok) throw new Error("Failed to delete")
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["publish-presets"] })
            toast({ title: "预设已删除" })
        },
    })

    const handleCreate = () => {
        if (!formData.name) {
            toast({ variant: "destructive", title: "请输入预设名称" })
            return
        }
        createMutation.mutate({
            ...formData,
            default_tags: formData.default_tags.split(",").map((t) => t.trim()).filter(Boolean),
        })
    }

    const togglePlatform = (platform: string) => {
        setFormData((prev) => ({
            ...prev,
            platforms: prev.platforms.includes(platform)
                ? prev.platforms.filter((p) => p !== platform)
                : [...prev.platforms, platform],
        }))
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">发布预设</h2>
                    <p className="text-sm text-white/60 mt-1">快速配置常用发布模板</p>
                </div>
                <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                    <DialogTrigger asChild>
                        <Button className="rounded-2xl bg-white/10 hover:bg-white/20 text-white border-0">
                            <Plus className="w-4 h-4 mr-2" />
                            新建预设
                        </Button>
                    </DialogTrigger>
                    <DialogContent className=" sm:max-w-[600px] border-white/10 bg-[#0A0A0A] text-white">
                        <DialogHeader>
                            <DialogTitle>新建发布预设</DialogTitle>
                            <DialogDescription>创建一个新的发布模板，用于快速配置发布任务</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                            <div>
                                <Label>预设名称 *</Label>
                                <Input
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="例如：日常发布模板"
                                    className="rounded-2xl bg-white/5"
                                />
                            </div>
                            <div>
                                <Label>说明</Label>
                                <Textarea
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    placeholder="选填，描述这个预设的用途"
                                    className="rounded-2xl min-h-[60px] bg-white/5"
                                />
                            </div>
                            <div>
                                <Label>适用平台</Label>
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {["douyin", "kuaishou", "xiaohongshu", "bilibili", "channels"].map((platform) => (
                                        <Button
                                            key={platform}
                                            variant={formData.platforms.includes(platform) ? "secondary" : "outline"}
                                            size="sm"
                                            className="rounded-xl"
                                            onClick={() => togglePlatform(platform)}
                                        >
                                            {platform === "douyin" && "抖音"}
                                            {platform === "kuaishou" && "快手"}
                                            {platform === "xiaohongshu" && "小红书"}
                                            {platform === "bilibili" && "B站"}
                                            {platform === "channels" && "视频号"}
                                        </Button>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <Label>默认标题</Label>
                                <Input
                                    value={formData.default_title}
                                    onChange={(e) => setFormData({ ...formData, default_title: e.target.value })}
                                    placeholder="选填，预设的默认标题"
                                    className="rounded-2xl bg-white/5"
                                />
                            </div>
                            <div>
                                <Label>默认标签</Label>
                                <Input
                                    value={formData.default_tags}
                                    onChange={(e) => setFormData({ ...formData, default_tags: e.target.value })}
                                    placeholder="多个标签用逗号分隔，如：生活,记录,日常"
                                    className="rounded-2xl bg-white/5"
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="ghost" onClick={() => setCreateDialogOpen(false)} className="rounded-2xl">
                                取消
                            </Button>
                            <Button onClick={handleCreate} disabled={createMutation.isPending} className="rounded-2xl">
                                {createMutation.isPending ? "创建中..." : "创建预设"}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {isLoading ? (
                <div className="p-6 text-white/60">加载中...</div>
            ) : presets.length === 0 ? (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-10 text-center">
                        <div className="mx-auto w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-4">
                            <Settings className="h-6 w-6 text-white/40" />
                        </div>
                        <h3 className="font-medium mb-2">暂无预设</h3>
                        <p className="text-sm text-white/60 mb-4">创建发布预设，快速配置发布任务</p>
                        <Button onClick={() => setCreateDialogOpen(true)} className="rounded-2xl">
                            <Plus className="mr-2 h-4 w-4" />
                            新建预设
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {presets.map((preset: any) => (
                        <Card key={preset.id} className="bg-white/5 border-white/10 hover:bg-white/[0.07] transition-colors">
                            <CardHeader>
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <CardTitle className="text-lg">{preset.name}</CardTitle>
                                        {preset.description && (
                                            <CardDescription className="mt-1">{preset.description}</CardDescription>
                                        )}
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {preset.platforms && JSON.parse(preset.platforms).length > 0 && (
                                        <div className="flex flex-wrap gap-1">
                                            {JSON.parse(preset.platforms).map((p: string) => (
                                                <Badge key={p} variant="outline" className="text-xs">
                                                    {p === "douyin" && "抖音"}
                                                    {p === "kuaishou" && "快手"}
                                                    {p === "xiaohongshu" && "小红书"}
                                                    {p === "bilibili" && "B站"}
                                                    {p === "channels" && "视频号"}
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                    {preset.default_title && (
                                        <p className="text-sm text-white/60 line-clamp-1">标题: {preset.default_title}</p>
                                    )}
                                    <div className="flex gap-2 pt-3 border-t border-white/10">
                                        <Button
                                            variant="secondary"
                                            size="sm"
                                            className="flex-1 rounded-xl"
                                            onClick={() => {
                                                if (onSelect) {
                                                    onSelect(preset)
                                                    toast({ title: "已应用预设", description: `已加载预设: ${preset.name}` })
                                                } else {
                                                    toast({ title: "功能开发中", description: "即将支持一键应用预设" })
                                                }
                                            }}
                                        >
                                            <Copy className="mr-2 h-4 w-4" />
                                            使用
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="rounded-xl"
                                            onClick={() => {
                                                toast({ title: "功能开发中" })
                                            }}
                                        >
                                            <Edit className="h-4 w-4" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="rounded-xl text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                            onClick={() => {
                                                if (confirm("确定要删除这个预设吗？")) {
                                                    deleteMutation.mutate(preset.id)
                                                }
                                            }}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    )
}
