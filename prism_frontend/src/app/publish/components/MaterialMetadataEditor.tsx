"use client"

import { useState, useMemo, useEffect } from "react"
import { backendBaseUrl } from "@/lib/env"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Sparkles, Save, X, Video, Info, Eye, ImageIcon, Loader2 } from "lucide-react"
import Image from "next/image"
import { cn } from "@/lib/utils"
import { useToast } from "@/components/ui/use-toast"
import {
    PlatformMetadataAdapter,
    PLATFORM_CONFIGS,
    getPlatformFieldHints,
    type PlatformKey
} from "@/lib/platform-metadata-adapter"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface MaterialMetadata {
    title?: string
    description?: string
    tags?: string[]
    cover_image?: string | null
    // legacy field name (kept for backward compatibility with older saved drafts)
    coverPath?: string | null
}

interface Material {
    id: number | string
    filename: string
    title: string
    cover_image?: string
    file_path?: string
    fileUrl?: string
    storageKey?: string
    video_width?: number
    video_height?: number
    orientation?: "portrait" | "landscape" | "square" | string
}

interface MaterialMetadataEditorProps {
    material: Material
    metadata: MaterialMetadata
    selectedPlatforms?: PlatformKey[]  // 用户选择的发布平台
    onSave: (metadata: MaterialMetadata) => void | Promise<void>
    onClose: () => void
    onAIGenerate?: (
        materialId: string,
        prompts: { titlePrompt?: string; tagsPrompt?: string }
    ) => Promise<Pick<MaterialMetadata, "title" | "tags"> | null | undefined>
}

export function MaterialMetadataEditor({
    material,
    metadata,
    selectedPlatforms = [],
    onSave,
    onClose,
    onAIGenerate
}: MaterialMetadataEditorProps) {
    const { toast } = useToast()
    const [localMetadata, setLocalMetadata] = useState<MaterialMetadata>(metadata)
    const [dirty, setDirty] = useState(false)
    const [isGenerating, setIsGenerating] = useState(false)
    const [isGeneratingCover, setIsGeneratingCover] = useState(false)
    const [coverPrompt, setCoverPrompt] = useState("")
    const [tagInput, setTagInput] = useState("")
    const [previewPlatform, setPreviewPlatform] = useState<PlatformKey | null>(
        selectedPlatforms.length > 0 ? selectedPlatforms[0] : null
    )
    const inferCoverAspect = (): "3:4" | "4:3" => {
        const o = material?.orientation
        if (o === "landscape") return "4:3"
        if (o === "portrait") return "3:4"
        const w = Number(material?.video_width || 0)
        const h = Number(material?.video_height || 0)
        if (w > 0 && h > 0) return w >= h ? "4:3" : "3:4"
        return "3:4"
    }

    const [aspectRatio, setAspectRatio] = useState<"3:4" | "4:3">(inferCoverAspect())

    const previewAspectClass = useMemo(() => {
        const o = material?.orientation
        if (o === "landscape") return "aspect-[16/9]"
        if (o === "square") return "aspect-[1/1]"
        return "aspect-[9/16]"
    }, [material?.orientation])

    // 初始化/切换素材时重置编辑态
    useEffect(() => {
        setLocalMetadata(metadata || {})
        setDirty(false)
        setTagInput("")
        setCoverPrompt("")
        setAspectRatio(inferCoverAspect())
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [material?.id])

    // 外部元数据更新（例如 AI 自动填充）时同步；本地已编辑则不覆盖
    useEffect(() => {
        if (dirty) return
        setLocalMetadata(metadata || {})
    }, [metadata, dirty])

    const [firstFramePath, setFirstFramePath] = useState<string>("")

    const firstFrameSrc = useMemo(() => {
        const raw = (firstFramePath || "").trim()
        if (!raw) return ""
        if (raw.startsWith("http")) return raw
        if (raw.startsWith("/getFile")) return `${backendBaseUrl}${raw}`
        return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
    }, [firstFramePath])

    const videoSrc = useMemo(() => {
        const raw = String(material.fileUrl || material.file_path || "").trim()
        if (!raw) return ""
        if (raw.startsWith("http")) return raw
        if (raw.startsWith("/getFile")) return `${backendBaseUrl}${raw}`
        return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
    }, [material.fileUrl, material.file_path])

    const coverSrc = useMemo(() => {
        const hasLocalCover = ("cover_image" in localMetadata) || ("coverPath" in localMetadata)
        const raw = hasLocalCover
            ? (localMetadata.cover_image ?? localMetadata.coverPath ?? "")
            : (material.cover_image || "")
        if (!raw) return ""
        if (raw.startsWith("http")) return raw
        return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
    }, [localMetadata, material.cover_image])

    // Always fetch first-frame for preview; do NOT store it into `cover_image` (cover_image is reserved for AI/user cover).
    useEffect(() => {
        let aborted = false
        const run = async () => {
            if (!material?.id) return
            try {
                const resp = await fetch(`/api/v1/files/${material.id}/first-frame`)
                if (!resp.ok) return
                const result = await resp.json()
                const firstFramePath = result?.data?.first_frame_path
                if (!aborted && firstFramePath) {
                    setFirstFramePath(String(firstFramePath))
                }
            } catch {
                // ignore
            }
        }
        run()
        return () => {
            aborted = true
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [material?.id])

    // 获取平台预览数据
    const platformPreviews = useMemo(() => {
        return selectedPlatforms.map(platform => {
            const formatted = PlatformMetadataAdapter.format(platform, localMetadata)
            const config = PLATFORM_CONFIGS[platform]
            return {
                platform,
                config,
                formatted
            }
        })
    }, [selectedPlatforms, localMetadata])

    const handleSave = async () => {
        const sanitized = { ...localMetadata }
        if (sanitized.cover_image === null) delete sanitized.cover_image
        if (sanitized.coverPath === null) delete sanitized.coverPath
        // @ts-ignore
        await onSave(sanitized)
        onClose()
    }

    const handleAIGenerate = async () => {
        if (!onAIGenerate) return
        setIsGenerating(true)
        try {
            const titlePrompt = (localMetadata.title || "").trim()
            const tagsPrompt = (tagInput.trim() || (localMetadata.tags || []).join(" ")).trim()
            const result = await onAIGenerate(String(material.id), { titlePrompt, tagsPrompt })
            if (result && (result.title || result.tags)) {
                setLocalMetadata(prev => ({
                    ...prev,
                    ...(result.title ? { title: result.title } : {}),
                    ...(result.tags ? { tags: result.tags } : {})
                }))
                setDirty(true)
                if (result.tags) setTagInput("")
            }
        } finally {
            setIsGenerating(false)
        }
    }

    const handleGenerateCover = async () => {
        if (!material?.id) return
        setIsGeneratingCover(true)
        try {
            const response = await fetch(`/api/v1/files/${material.id}/ai-cover`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    platform_name: previewPlatform ? PLATFORM_CONFIGS[previewPlatform]?.name : "全平台",
                    aspect_ratio: aspectRatio,
                    prompt: coverPrompt.trim()
                })
            })

            const data = await response.json()

            const coverPath = data?.data?.cover_path
            if (coverPath) {
                setLocalMetadata(prev => ({
                    ...prev,
                    cover_image: coverPath
                }))
                setDirty(true)
                setCoverPrompt("")
                toast({
                    title: "封面已生成",
                    description: "AI 封面生成成功，点击保存后生效"
                })
            } else {
                throw new Error(data?.detail || data?.message || "封面生成失败")
            }
        } catch (e) {
            console.error("Cover generation failed", e)
            toast({
                title: "生成失败",
                description: String(e),
                variant: "destructive"
            })
        } finally {
            setIsGeneratingCover(false)
        }
    }

    const addTag = (tag: string) => {
        if (!tag.trim()) return
        const currentTags = localMetadata.tags || []
        if (!currentTags.includes(tag.trim())) {
            setLocalMetadata({
                ...localMetadata,
                tags: [...currentTags, tag.trim()]
            })
        }
        setDirty(true)
        setTagInput("")
    }

    const removeTag = (tagToRemove: string) => {
        setLocalMetadata({
            ...localMetadata,
            tags: (localMetadata.tags || []).filter(tag => tag !== tagToRemove)
        })
        setDirty(true)
    }

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="max-w-4xl bg-black border-black text-white max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Video className="w-5 h-5" />
                        编辑素材元数据
                    </DialogTitle>
                </DialogHeader>

                <div className="grid grid-cols-2 gap-6">
                    {/* 左侧：预览 */}
                    <div className="space-y-4">
                        <div className={cn("relative rounded-xl overflow-hidden border border-black bg-black", previewAspectClass)}>
                            {videoSrc ? (
                                <video
                                    src={videoSrc}
                                    poster={firstFrameSrc || undefined}
                                    preload="metadata"
                                    controls
                                    className="absolute inset-0 h-full w-full object-cover"
                                />
                            ) : firstFrameSrc ? (
                                <Image
                                    src={firstFrameSrc}
                                    alt={material.filename}
                                    fill
                                    className="object-cover"
                                    unoptimized
                                />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center">
                                    <Video className="w-16 h-16 text-white/20" />
                                </div>
                            )}
                        </div>
                        <div className="space-y-2">
                            <p className="text-xs text-white/60">文件名</p>
                            <p className="text-sm text-white truncate">{material.filename}</p>
                        </div>
                    </div>

                    {/* 右侧：编辑表单 */}
                    <div className="space-y-6">
                        {/* AI 生成按钮 */}
                        {onAIGenerate && (
                            <div className="space-y-2">
                                <Button
                                    onClick={handleAIGenerate}
                                    disabled={isGenerating}
                                    className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white"
                                >
                                    <Sparkles className={cn("w-4 h-4 mr-2", isGenerating && "animate-spin")} />
                                    {isGenerating ? "AI 生成中..." : "AI 智能生成"}
                                </Button>
                            </div>
                        )}

                        {/* 标题 */}
                        <div className="space-y-2">
                            <Label className="text-sm text-white/80">标题</Label>
                            <Input
                                value={localMetadata.title || ""}
                                onChange={(e) => {
                                    setDirty(true)
                                    setLocalMetadata({ ...localMetadata, title: e.target.value })
                                }}
                                placeholder="请入视频标题（30字内）"
                                maxLength={30}
                                className="bg-black border-black text-white"
                            />
                        </div>

                        {/* 标签 */}
                        <div className="space-y-2">
                            <Label className="text-sm text-white/80">标签</Label>
                            <div className="flex gap-2">
                                <Input
                                    value={tagInput}
                                    onChange={(e) => setTagInput(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                            e.preventDefault()
                                            addTag(tagInput)
                                        }
                                    }}
                                    placeholder="输入标签后按回车"
                                    className="bg-black border-black text-white"
                                />
                                <Button
                                    onClick={() => addTag(tagInput)}
                                    size="sm"
                                    variant="outline"
                                    className="border-black hover:bg-white/5"
                                >
                                    添加
                                </Button>
                            </div>
                            {localMetadata.tags && localMetadata.tags.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-3">
                                    {localMetadata.tags.map((tag, index) => (
                                        <Badge
                                            key={index}
                                            variant="secondary"
                                            className="bg-white/10 text-white hover:bg-white/20 flex items-center gap-1"
                                        >
                                            {tag}
                                            <button
                                                onClick={() => removeTag(tag)}
                                                className="ml-1 hover:text-red-400"
                                            >
                                                <X className="w-3 h-3" />
                                            </button>
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* AI 封面生成 (替换原平台预览) */}
                        <div className="space-y-2 pt-4 border-t border-black">
                            <Label className="text-sm text-white/80 flex items-center gap-2">
                                <ImageIcon className="w-3 h-3" />
                                AI 生成封面
                            </Label>

                            <div className="flex gap-2">
                                <Input
                                    value={coverPrompt}
                                    onChange={(e) => setCoverPrompt(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" && !isGeneratingCover) {
                                            e.preventDefault()
                                            handleGenerateCover()
                                        }
                                    }}
                                    placeholder="描述你想要的封面画面..."
                                    className="bg-black border-black text-white"
                                />
                                <Button
                                    onClick={handleGenerateCover}
                                    disabled={isGeneratingCover}
                                    size="sm"
                                    className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                                >
                                    {isGeneratingCover ? (
                                        <Loader2 className="w-3 h-3 animate-spin" />
                                    ) : (
                                        <Sparkles className="w-3 h-3" />
                                    )}
                                </Button>
                            </div>
                            {coverSrc && (
                                <div
                                    className={cn(
                                        "relative w-full rounded-lg overflow-hidden border border-black mt-2",
                                        aspectRatio === "4:3" ? "aspect-[4/3]" : "aspect-[3/4]"
                                    )}
                                >
                                    <Image
                                        src={coverSrc}
                                        alt="封面预览"
                                        fill
                                        className="object-cover"
                                        unoptimized
                                    />
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        className="absolute top-2 right-2 h-6 w-6 bg-black/50 hover:bg-black/70"
                                        onClick={() => {
                                            setDirty(true)
                                            setLocalMetadata(prev => ({ ...prev, cover_image: null, coverPath: null }))
                                        }}
                                    >
                                        <X className="w-3 h-3" />
                                    </Button>
                                </div>
                            )}
                        </div>

                        {/* 操作按钮 */}
                        <div className="flex gap-3 pt-4">
                            <Button
                                onClick={handleSave}
                                className="flex-1 bg-white hover:bg-white/90 text-black"
                            >
                                <Save className="w-4 h-4 mr-2" />
                                保存
                            </Button>
                            <Button
                                onClick={onClose}
                                variant="outline"
                                className="flex-1 border-black hover:bg-white/5"
                            >
                                取消
                            </Button>
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}
