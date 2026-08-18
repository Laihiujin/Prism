
"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Image from "next/image"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useToast } from "@/components/ui/use-toast"
import { Loader2, Sparkles, Wand2, ImageIcon } from "lucide-react"
import { backendBaseUrl } from "@/lib/env"
import { cn } from "@/lib/utils"

interface Material {
    id: string
    filename: string
    title?: string
    description?: string
    tags?: string
    note?: string
    group?: string
    cover_image?: string
    fileUrl?: string
    video_width?: number
    video_height?: number
    aspect_ratio?: string
    orientation?: "portrait" | "landscape" | "square" | string
}

export interface MaterialEditorSaveData extends Partial<Material> {
    scheduleTime?: Date
    updateDiskFile?: boolean
}

interface MaterialEditorSheetProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    material: Material | null
    groupOptions: string[]
    onSave: (data: MaterialEditorSaveData) => Promise<void>
    mode?: "edit" | "create" | "batch"
    showGroupSelector?: boolean
}

export function MaterialEditorContent({
    material,
    groupOptions,
    onSave,
    mode = "edit",
    initialData,
    isSaving: externalIsSaving,
    onChange,
    hideFooter = false,
    showGroupSelector = true,
    className
}: {
    material: Material | null
    groupOptions: string[]
    onSave: (data: any) => Promise<void>
    mode?: "edit" | "create" | "batch"
    initialData?: any
    isSaving?: boolean
    onChange?: (data: MaterialEditorSaveData) => void
    hideFooter?: boolean
    showGroupSelector?: boolean
    className?: string
}) {
    const { toast } = useToast()
    const [localIsSaving, setLocalIsSaving] = useState(false)
    const isSaving = externalIsSaving || localIsSaving
    const [aiGenerating, setAiGenerating] = useState<string | null>(null)
    const [coverPrompt, setCoverPrompt] = useState("")
    const [coverJobId, setCoverJobId] = useState<string | null>(null)
    const [coverJobStatus, setCoverJobStatus] = useState<"idle" | "pending" | "running" | "succeeded" | "failed">("idle")
    const [coverJobError, setCoverJobError] = useState("")
    const coverPollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [referenceImage, setReferenceImage] = useState<File | null>(null)

    const inferredCoverAspect = useMemo<"3:4" | "4:3">(() => {
        const o = material?.orientation
        if (o === "landscape") return "4:3"
        if (o === "portrait") return "3:4"
        const w = Number(material?.video_width || 0)
        const h = Number(material?.video_height || 0)
        if (w > 0 && h > 0) return w >= h ? "4:3" : "3:4"
        return "3:4"
    }, [material?.id, material?.orientation, material?.video_width, material?.video_height])

    const [editForm, setEditForm] = useState({
        filename: "",
        title: "",
        description: "",
        tags: "",
        note: "",
        group: "",
        cover_image: "",
        scheduleTime: undefined as Date | undefined
    })

    const [updateDiskFile, setUpdateDiskFile] = useState(true)

    useEffect(() => {
        if (initialData) {
            setEditForm(prev => ({ ...prev, ...initialData }))
        } else if (material) {
            setEditForm({
                filename: material.filename || "",
                title: material.title || material.filename.split('.').slice(0, -1).join('.') || "",
                description: material.description || "",
                tags: material.tags || "",
                note: material.note || "",
                group: material.group || "none",
                cover_image: material.cover_image || "",
                scheduleTime: undefined
            })
            setCoverPrompt("生成一张吸引人的封面，风格现代，高清晰度")
        } else if (mode === 'batch') {
            setEditForm(prev => ({ ...prev, group: "none" }))
        }
    }, [material?.id, mode, initialData])

    const coverSrc = useMemo(() => {
        const raw = (editForm.cover_image || "").trim()
        if (!raw) return ""
        if (raw.startsWith("http")) return raw
        return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
    }, [editForm.cover_image])

    const coverAspectStyle = useMemo(() => {
        return { aspectRatio: inferredCoverAspect === "4:3" ? "4 / 3" : "3 / 4" }
    }, [inferredCoverAspect])

    const coverJobStorageKey = useMemo(() => {
        return material?.id ? `aiCoverJob:${material.id}` : ""
    }, [material?.id])

    const stopCoverPolling = useCallback(() => {
        if (coverPollTimerRef.current) {
            clearTimeout(coverPollTimerRef.current)
            coverPollTimerRef.current = null
        }
    }, [])

    const pollCoverJob = useCallback(async (jobId: string) => {
        if (!jobId) return
        stopCoverPolling()

        const tick = async () => {
            try {
                const response = await fetch(`/api/v1/files/ai-cover-jobs/${encodeURIComponent(jobId)}`)
                const payload = await response.json().catch(() => ({}))
                const status = payload?.data?.status as typeof coverJobStatus | undefined
                const coverPath = payload?.data?.cover_path as string | undefined
                const error = payload?.data?.error as string | undefined

                if (status) setCoverJobStatus(status)

                if (status === "succeeded" && coverPath) {
                    setEditForm(prev => ({ ...prev, cover_image: coverPath }))
                    setCoverPrompt("")
                    setCoverJobError("")
                    stopCoverPolling()
                    setCoverJobId(null)
                    if (coverJobStorageKey) localStorage.removeItem(coverJobStorageKey)
                    toast({ title: "封面已生成", description: "AI 封面生成成功，保存后生效" })
                    return
                }

                if (status === "failed") {
                    setCoverJobError(error || "封面生成失败")
                    stopCoverPolling()
                    setCoverJobId(null)
                    if (coverJobStorageKey) localStorage.removeItem(coverJobStorageKey)
                    toast({ variant: "destructive", title: "封面生成失败", description: error || "请稍后重试" })
                    return
                }
            } catch (e) {
                setCoverJobError(e instanceof Error ? e.message : "封面生成失败")
            }

            coverPollTimerRef.current = setTimeout(tick, 1200)
        }

        tick()
    }, [coverJobStorageKey, stopCoverPolling, toast])

    useEffect(() => {
        if (!coverJobStorageKey) return
        const stored = localStorage.getItem(coverJobStorageKey)
        if (stored) {
            setCoverJobId(stored)
            setCoverJobStatus("pending")
            pollCoverJob(stored)
        } else {
            setCoverJobId(null)
            setCoverJobStatus("idle")
            setCoverJobError("")
        }

        return () => {
            stopCoverPolling()
        }
    }, [coverJobStorageKey, pollCoverJob, stopCoverPolling])

    useEffect(() => {
        if (onChange) {
            const timer = setTimeout(() => {
                onChange({
                    ...editForm,
                    group: editForm.group === 'none' ? '' : editForm.group
                })
            }, 300)
            return () => clearTimeout(timer)
        }
    }, [editForm, onChange])

    const handleAIGenerate = async (field: 'title' | 'desc' | 'tags') => {
        setAiGenerating(field)

        try {
            let prompt = ''
            const filename = material?.filename || "视频素材"
            const baseName = filename.replace(/\.[^.]+$/, "")

            // 优先使用用户输入的内容作为提示词
            if (field === 'title') {
                const userInput = editForm.title?.trim()
                if (userInput) {
                    // 用户已填写内容，必须深度二创重构
                    prompt = `你是专业的短视频标题二创专家。请对用户输入的标题进行深度重构改写。

⚠️ 严禁行为：
- ❌ 严禁直接复制或仅改动1-2个字
- ❌ 严禁使用表情符号
- ❌ 严禁使用引号包裹
- ❌ 禁止营销敏感词：领取、金币、福利、礼包、首充

✅ 二创要求：
- 必须用完全不同的句式和视角重新表达
- 提炼核心亮点，加入悬念、惊喜、好奇等情感元素
- 长度控制在10-27字之间
- 符合短视频平台调性

文件名参考：${filename}
用户输入标题：${userInput}

只输出二创后的标题，不要任何解释。`
                } else {
                    // 用户未填写，根据文件名生成
                    prompt = `你是专业的短视频标题创作专家。请根据文件名生成吸引人的标题。

要求：
- 提炼文件名中的核心亮点
- 加入悬念或情感元素
- 长度10-27字
- 不使用表情符号和引号
- 如有英文请翻译（专有名词可保留）

文件名：${filename}

只输出标题，不要解释。`
                }
            } else if (field === 'desc') {
                const userInput = editForm.description?.trim()
                if (userInput) {
                    // 用户已填写内容，必须深度二创
                    prompt = `你是专业的短视频文案二创大师。请将用户的描述改写成引人入胜的文案。

⚠️ 严禁行为：
- ❌ 严禁照抄用户输入
- ❌ 严禁仅改动几个字
- ❌ 严禁使用Emoji
- ❌ 禁止营销词：领取、金币、福利、礼包、首充

✅ 二创要求：
- 将内容改写成故事化、场景化表达
- 用疑问、惊叹、悬念引发好奇心
- 结构：开头抓眼球 → 中间展开 → 结尾引导互动
- 标点规范，不要空格分隔

用户描述：
${userInput}

只返回文案，不要其他说明。`
                } else {
                    // 用户未填写，根据文件名生成
                    prompt = `为视频"${filename}"生成吸引人的描述文案，要求故事化表达，2-3个话题标签，适合抖音等短视频平台。不要表情符号。`
                }
            } else if (field === 'tags') {
                const userInput = editForm.tags?.trim()
                if (userInput) {
                    // 用户已填写内容，必须深度提炼扩展
                    prompt = `你是话题标签二创专家。请从用户输入中提炼精准且有流量的标签。

⚠️ 严禁行为：
- ❌ 严禁直接照搬用户标签
- ❌ 严禁只改个别字
- ❌ 严禁使用Emoji
- ❌ 禁止营销词：领取、金币、福利、礼包、首充

✅ 二创要求：
- 从用户输入提炼核心主题
- 扩展为精准的长尾关键词
- 游戏相关时包含：芒果斗地主、开运麻将、乐鸿捕鱼
- 输出1-4个标签，空格分隔，不带#

文件名：${filename}
用户输入标签：${userInput}

只输出标签列表（空格分隔，不带#），不要解释。`
                } else {
                    // 用户未填写，根据文件名生成
                    prompt = `请根据文件名生成短视频标签。

要求：
- 输出1-4个标签，空格分隔
- 不带#（系统会自动加）
- 如有英文请翻译（专有名词可保留）

文件名：${filename}

只输出标签，不要解释。`
                }
            }

            const response = await fetch(`${backendBaseUrl}/api/v1/ai/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: [{ role: 'user', content: prompt }],
                    stream: false
                })
            })

            if (!response.ok) throw new Error('AI generation failed')
            const data = await response.json()
            const content = data.content || data.message || ''

            const normalizeTags = (value: string) => {
                const items = value
                    .split(/[\s,，]+/)
                    .map(tag => tag.trim().replace(/^#/, ""))
                    .filter(Boolean)
                const unique: string[] = []
                for (const item of items) {
                    if (!unique.includes(item)) unique.push(item)
                }
                return unique.slice(0, 4)
            }

            if (field === 'title') {
                setEditForm(prev => ({ ...prev, title: content.trim() }))
            } else if (field === 'desc') {
                setEditForm(prev => ({ ...prev, description: content.trim() }))
            } else if (field === 'tags') {
                const tags = normalizeTags(content.trim())
                setEditForm(prev => ({ ...prev, tags: tags.join(" ") }))
            }

            toast({ title: "AI 生成完成", description: "内容已自动填充" })
        } catch (error) {
            console.error('AI generation error:', error)
            toast({ variant: "destructive", title: "AI 生成失败", description: "请稍后重试" })
        } finally {
            setAiGenerating(null)
        }
    }

    const handleGenerateCover = async () => {
        if (!coverPrompt.trim()) {
            toast({ variant: "destructive", title: "请输入提示词", description: "封面生成需要描述提示词" })
            return
        }
        if (!material?.id) {
            toast({ variant: "destructive", title: "无法生成封面", description: "请先保存素材后再生成封面" })
            return
        }

        setCoverJobError("")
        setCoverJobStatus("pending")

        try {
            const formData = new FormData()
            formData.append("platform_name", "全平台")
            formData.append("aspect_ratio", inferredCoverAspect)
            formData.append("prompt", coverPrompt.trim())
            if (referenceImage) {
                formData.append("ref_image", referenceImage)
            }

            const response = await fetch(`/api/v1/files/${encodeURIComponent(material.id)}/ai-cover-job`, {
                method: "POST",
                body: formData
            })
            const data = await response.json().catch(() => ({}))
            const jobId = data?.data?.job_id as string | undefined

            if (!response.ok || !jobId) {
                throw new Error(data?.detail || data?.message || "封面生成失败")
            }

            setCoverJobId(jobId)
            if (coverJobStorageKey) localStorage.setItem(coverJobStorageKey, jobId)
            pollCoverJob(jobId)
            toast({ title: "已开始生成封面", description: "生成中可关闭侧边栏，完成后会自动回填" })
        } catch (error) {
            console.error('Cover generation error:', error)
            setCoverJobStatus("failed")
            setCoverJobError(error instanceof Error ? error.message : "封面生成失败")
            toast({ variant: "destructive", title: "封面生成失败", description: "请稍后重试" })
        }
    }

    const handleSave = async () => {
        setLocalIsSaving(true)
        try {
            await onSave({
                ...editForm,
                group: editForm.group === 'none' ? '' : editForm.group,
                updateDiskFile // 传递磁盘更新标志
            })
        } catch (error) {
            console.error(error)
        } finally {
            setLocalIsSaving(false)
        }
    }

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {!hideFooter && (
                <div className="px-6 py-4 border-b border-white/10 bg-[#0A0A0A] flex justify-end">
                    <Button onClick={handleSave} disabled={isSaving} className="min-w-[100px]">
                        {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : (mode === 'create' ? "确认发布" : "保存更改")}
                    </Button>
                </div>
            )}

            <ScrollArea className="flex-1 px-6 py-6">
                <div className="space-y-8 pb-10">

                    {/* Content Info - 内容设置 */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-medium text-white/50 uppercase tracking-wider">内容设置</h3>
                            <Badge variant="secondary" className="bg-purple-500/10 text-purple-400 border-purple-500/20">
                                <Sparkles className="w-3 h-3 mr-1" /> AI Ready
                            </Badge>
                        </div>

                        <div className="grid gap-5">
                            <div className="grid gap-2">
                                <div className="flex justify-between items-center">
                                    <Label>文件名</Label>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            id="update-disk-file"
                                            checked={updateDiskFile}
                                            onChange={(e) => setUpdateDiskFile(e.target.checked)}
                                            className="h-3.5 w-3.5 rounded border-white/20 bg-white/5 text-primary focus:ring-2 focus:ring-primary cursor-pointer"
                                        />
                                        <label htmlFor="update-disk-file" className="text-xs text-white/60 cursor-pointer">
                                            同步修改磁盘文件名
                                        </label>
                                    </div>
                                </div>
                                <Input
                                    value={editForm.filename}
                                    onChange={e => setEditForm(prev => ({ ...prev, filename: e.target.value }))}
                                    className="bg-black border-white/10"
                                    placeholder="输入文件名（含扩展名）"
                                />
                                {/* <p className="text-xs text-white/40">
                                    {updateDiskFile
                                        ? "✓ 将同时修改数据库和磁盘文件名"
                                        : "仅修改显示名称，不改变磁盘文件"}
                                </p> */}
                            </div>

                            <div className="grid gap-2">
                                <div className="flex justify-between items-center">
                                    <Label>标题</Label>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-6 text-xs text-purple-400 hover:text-purple-300 hover:bg-purple-500/10"
                                        onClick={() => handleAIGenerate('title')}
                                        disabled={!!aiGenerating}
                                    >
                                        {aiGenerating === 'title' ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Wand2 className="w-3 h-3 mr-1" />}
                                        AI 生成
                                    </Button>
                                </div>
                                <Input
                                    value={editForm.title}
                                    onChange={e => setEditForm(prev => ({ ...prev, title: e.target.value }))}
                                    className="bg-black border-white/10 font-medium"
                                    placeholder="输入想要的标题"
                                />
                            </div>

                            {/* <div className="grid gap-2">
                                <div className="flex justify-between items-center">
                                    <Label>描述</Label>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-6 text-xs text-purple-400 hover:text-purple-300 hover:bg-purple-500/10"
                                        onClick={() => handleAIGenerate('desc')}
                                        disabled={!!aiGenerating}
                                    >
                                        {aiGenerating === 'desc' ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Wand2 className="w-3 h-3 mr-1" />}
                                        AI 润色
                                    </Button>
                                </div>
                                <Textarea
                                    value={editForm.description}
                                    onChange={e => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                                    className="bg-white/5 border-white/10 min-h-[100px]"
                                    placeholder="输入视频描述或脚本..."
                                />
                            </div> */}

                            <div className="grid gap-2">
                                <div className="flex justify-between items-center">
                                    <Label>标签</Label>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-6 text-xs text-purple-400 hover:text-purple-300 hover:bg-purple-500/10"
                                        onClick={() => handleAIGenerate('tags')}
                                        disabled={!!aiGenerating}
                                    >
                                        {aiGenerating === 'tags' ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Wand2 className="w-3 h-3 mr-1" />}
                                        AI 推荐
                                    </Button>
                                </div>
                                <Input
                                    value={editForm.tags}
                                    onChange={e => setEditForm(prev => ({ ...prev, tags: e.target.value }))}
                                    className="bg-black border-white/10"
                                    placeholder="输入想要的标签"
                                />
                            </div>

                            {/* 分组选择器 - 仅在素材管理页面显示 */}
                            {showGroupSelector && (
                                <div className="grid gap-2">
                                    <Label>分组</Label>
                                    <Select
                                        value={editForm.group}
                                        onValueChange={value => setEditForm(prev => ({ ...prev, group: value }))}
                                    >
                                        <SelectTrigger className="bg-black border-white/10">
                                            <SelectValue placeholder="选择分组" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#1A1A1A] border-white/10 text-white">
                                            <SelectItem value="none">无分组</SelectItem>
                                            {groupOptions.map(group => (
                                                <SelectItem key={group} value={group}>{group}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Reference image uploader */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label className="text-xs text-white/60">上传/拖拽参考图（可选）</Label>
                            {referenceImage && (
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-6 text-xs text-white/60 hover:text-white hover:bg-black/10"
                                    onClick={() => setReferenceImage(null)}
                                >
                                    移除
                                </Button>
                            )}
                        </div>
                        <div
                            className="relative w-full mt-2 max-w-xl mx-auto"
                            onDragOver={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                            }}
                            onDrop={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                const file = e.dataTransfer.files?.[0]
                                if (!file) return
                                if (!file.type.startsWith("image/")) {
                                    toast({ variant: "destructive", title: "文件类型不支持", description: "请上传图片（jpg/png/webp）" })
                                    return
                                }
                                setReferenceImage(file)
                            }}
                            onClick={() => {
                                const input = document.getElementById(`ai-cover-ref-upload-${material?.id ?? "temp"}`) as HTMLInputElement | null
                                input?.click()
                            }}
                        >
                            <div className="relative group-hover/file:shadow-2xl z-40 bg-black dark:bg-neutral-900 flex items-center justify-center h-32 mt-1 w-full mx-auto rounded-md shadow-[0px_10px_50px_rgba(0,0,0,0.1)]">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="tabler-icon tabler-icon-upload h-4 w-4 text-neutral-600 dark:text-neutral-300">
                                    <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2"></path>
                                    <path d="M7 9l5 -5l5 5"></path>
                                    <path d="M12 4l0 12"></path>
                                </svg>
                            </div>
                            <div className="absolute opacity-0 border border-dashed border-sky-400 inset-0 z-30 bg-transparent flex items-center justify-center h-32 mt-4 w-full mx-auto rounded-md" />
                            <input
                                id={`ai-cover-ref-upload-${material?.id ?? "temp"}`}
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => {
                                    const file = e.target.files?.[0]
                                    if (!file) return
                                    setReferenceImage(file)
                                }}
                            />
                        </div>
                    </div>

                    {/* Cover Generator - AI 封面工坊 */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-medium text-white/50 uppercase tracking-wider">封面工坊</h3>
                            {(coverJobStatus === "pending" || coverJobStatus === "running") && (
                                <Badge variant="secondary" className="bg-purple-500/10 text-purple-300 border-purple-500/20">
                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" /> 生成中
                                </Badge>
                            )}
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            {/* Left: AI cover preview */}
                            <div className="space-y-2">
                                <div
                                    className="w-full rounded-lg border border-white/10 bg-black overflow-hidden relative group"
                                    style={coverAspectStyle}
                                >
                                    {coverSrc ? (
                                        <Image src={coverSrc} alt="Cover" fill className="object-cover" unoptimized />
                                    ) : (
                                        <div className="absolute inset-0 flex items-center justify-center text-white/20">
                                            <ImageIcon className="w-8 h-8" />
                                        </div>
                                    )}
                                    {!!coverSrc && (
                                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="text-white hover:text-white"
                                                onClick={() => setEditForm(prev => ({ ...prev, cover_image: "" }))}
                                            >
                                                清除
                                            </Button>
                                        </div>
                                    )}
                                </div>
                                <div className="text-center text-xs text-white/40">{inferredCoverAspect} 预览</div>
                            </div>

                            {/* Right: prompt box (same height as preview) */}
                            <div className="space-y-2">
                                <div
                                    className="flex flex-col rounded-lg border border-white/10 bg-black p-3"
                                    style={coverAspectStyle}
                                >
                                    <Label className="text-xs text-white/60">AI 封面 Prompt</Label>
                                    <Textarea
                                        value={coverPrompt}
                                        onChange={e => setCoverPrompt(e.target.value)}
                                        className="mt-2 flex-1 bg-transparent border-white/10 text-sm resize-none"
                                        placeholder="描述想要的封面画面..."
                                    />
                                    <div className="mt-3 flex items-center justify-between gap-2">
                                        <div className="text-xs text-white/40 truncate">
                                            {referenceImage ? `参考图：${referenceImage.name}` : "参考图：未选择（可选）"}
                                        </div>
                                        <Button
                                            className="bg-gradient-to-br from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 border-0"
                                            onClick={handleGenerateCover}
                                            disabled={!!aiGenerating || coverJobStatus === "pending" || coverJobStatus === "running"}
                                        >
                                            {(coverJobStatus === "pending" || coverJobStatus === "running") ? (
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <Wand2 className="w-4 h-4" />
                                            )}
                                            <span className="ml-2 text-sm">生成</span>
                                        </Button>
                                    </div>
                                </div>
                                {coverJobError && (
                                    <p className="text-xs text-red-400">{coverJobError}</p>
                                )}
                            </div>
                        </div>


                    </div>

                </div>
            </ScrollArea>

        </div>
    )
}

export function MaterialEditorSheet({
    open,
    onOpenChange,
    material,
    groupOptions,
    onSave,
    mode = "edit",
    showGroupSelector = true
}: MaterialEditorSheetProps) {
    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full sm:max-w-[770px] border-l border-white/10 bg-[#0A0A0A] p-0 flex flex-col shadow-2xl">
                <SheetHeader className="px-6 py-4 border-b border-white/10">
                    <SheetTitle>{mode === 'batch' ? '批量编辑素材' : '编辑素材详情'}</SheetTitle>
                    <SheetDescription>配置标题、描述与封面，支持 AI 一键生成。</SheetDescription>
                </SheetHeader>
                <MaterialEditorContent
                    material={material}
                    groupOptions={groupOptions}
                    onSave={async (data) => {
                        await onSave(data)
                        onOpenChange(false)
                    }}
                    mode={mode}
                    showGroupSelector={showGroupSelector}
                />
            </SheetContent>
        </Sheet>
    )
}
