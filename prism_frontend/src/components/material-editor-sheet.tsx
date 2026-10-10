
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
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog"
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ChevronDown } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useToast } from "@/components/ui/use-toast"
import { Loader2, Sparkles, Wand2, ImageIcon, X, UploadCloud } from "lucide-react"
import { EditableHistoryInput } from "@/components/editable-history-input"
import { parseMaterialAIResult } from "@/lib/material-ai-result"
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
    autoSave?: boolean
}

interface MaterialEditorSheetProps {
    initialPresetId?: string
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
    className,
    initialPresetId = "default"
}: {
    initialPresetId?: string
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
    const aiFillBusyRef = useRef(false)
    const appliedPresetRef = useRef("")
    const initializedFormRef = useRef("")
    const [textHistory, setTextHistory] = useState<{ titles: string[]; tags: string[] }>({ titles: [], tags: [] })
    useEffect(() => {
        setTextHistory({ titles: [], tags: [] })
        if (!material?.id) return
        const controller = new AbortController()
        void fetch(`${backendBaseUrl}/api/v1/files/${material.id}/text-history`, { signal: controller.signal }).then(response => response.json()).then(payload => setTextHistory(payload.data || { titles: [], tags: [] })).catch(() => {})
        return () => controller.abort()
    }, [material?.id])

    const recordTextHistory = async (candidate: { title?: string; tags?: string }) => {
        setTextHistory(prev => ({ titles: candidate.title ? [candidate.title, ...prev.titles.filter(value => value !== candidate.title)] : prev.titles, tags: candidate.tags ? [candidate.tags, ...prev.tags.filter(value => value !== candidate.tags)] : prev.tags }))
        if (!material?.id) return
        const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/text-history`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(candidate) })
        if (!response.ok) throw new Error("候选已回填，但生成历史保存失败，请重试")
    }

    const deleteTextHistory = async (field: "titles" | "tags", value: string) => {
        try {
            if (!material?.id) throw new Error("素材不存在")
            const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/text-history`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ field, value }) })
            if (!response.ok) throw new Error("删除失败，请重试")
            const payload = await response.json()
            setTextHistory(payload.data)
        } catch (error) {
            toast({ title: "删除候选失败", description: error instanceof Error ? error.message : "请检查网络连接", variant: "destructive" })
            throw error
        }
    }

    const [coverPreviewOpen, setCoverPreviewOpen] = useState(false)
    const [coverToDelete, setCoverToDelete] = useState<{ id: string; path: string } | null>(null)
    const [deletingCover, setDeletingCover] = useState(false)
    type MaterialPreset = { name: string; platform: string; data: { form?: Partial<typeof editForm>; coverPrompt?: string; coverAspect?: "3:4" | "4:3" | null } }
    const [presets, setPresets] = useState<Record<string, MaterialPreset>>({})
    const [activePreset, setActivePreset] = useState("default")
    const [presetName, setPresetName] = useState("")
    const [presetPlatform, setPresetPlatform] = useState("all")
    useEffect(() => {
        setActivePreset("default")
        setPresets({})
        if (!material?.id) return
        const controller = new AbortController()
        void fetch(`${backendBaseUrl}/api/v1/files/${material.id}/presets`, { signal: controller.signal }).then(response => response.json()).then(payload => setPresets(payload.data || {})).catch(() => {})
        return () => controller.abort()
    }, [material?.id])

    const [coverPrompt, setCoverPrompt] = useState("")
    const [generationTargets, setGenerationTargets] = useState<string[]>([])
    const [adaptPlatforms, setAdaptPlatforms] = useState(false)
    const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([])
    const platformContext = adaptPlatforms && selectedPlatforms.length ? `适配平台：${selectedPlatforms.join("、")}。根据平台受众和表达风格调整措辞，保持事实准确。` : ""

    const [coverJobId, setCoverJobId] = useState<string | null>(null)
    const coverPollGenerationRef = useRef(0)
    const [coverJobStatus, setCoverJobStatus] = useState<"idle" | "pending" | "running" | "succeeded" | "failed">("idle")
    const [coverJobError, setCoverJobError] = useState("")
    const [coverStage, setCoverStage] = useState("pending")
    const [coverStartedAt, setCoverStartedAt] = useState<number | null>(null)
    const [coverElapsed, setCoverElapsed] = useState(0)
    const coverBusy = coverJobStatus === "pending" || coverJobStatus === "running"

    useEffect(() => {
        if (!coverBusy || !coverStartedAt) return
        const tick = () => setCoverElapsed(Math.max(0, Math.floor((Date.now() - coverStartedAt) / 1000)))
        tick()
        const timer = setInterval(tick, 1000)
        return () => clearInterval(timer)
    }, [coverBusy, coverStartedAt])

    const coverPollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [referenceImage, setReferenceImage] = useState<File | null>(null)
    const [useFirstFrame, setUseFirstFrame] = useState(true)
    const [refPreviewSrc, setRefPreviewSrc] = useState("")
    const [firstFrameSrc, setFirstFrameSrc] = useState("")
    const [firstFrameError, setFirstFrameError] = useState("")

    const [coverAspectOverride, setCoverAspectOverride] = useState<"3:4" | "4:3" | null>(null)
    const [coverPlatform, setCoverPlatform] = useState("all")
    type UploadedCover = { id: string; path: string; platform: string; orientation: string; width: number; height: number; source?: string }
    const [coverLibrary, setCoverLibrary] = useState<{ items: UploadedCover[]; selected: Record<string, string> }>({ items: [], selected: {} })
    const [uploadingCovers, setUploadingCovers] = useState(false)
    const [showAllCovers, setShowAllCovers] = useState(true)
    useEffect(() => {
        setCoverAspectOverride(null)
        setCoverLibrary({ items: [], selected: {} })
        if (!material?.id) return
        const controller = new AbortController()
        void fetch(`${backendBaseUrl}/api/v1/files/${material.id}/covers`, { signal: controller.signal }).then(response => {
            if (!response.ok) throw new Error("封面列表读取失败")
            return response.json()
        }).then(payload => setCoverLibrary(payload.data)).catch(() => {})
        return () => controller.abort()
    }, [material?.id])
    const inferredCoverAspect = useMemo<"3:4" | "4:3">(() => {
        if (coverAspectOverride) return coverAspectOverride
        const o = material?.orientation
        if (o === "landscape") return "4:3"
        if (o === "portrait") return "3:4"
        const w = Number(material?.video_width || 0)
        const h = Number(material?.video_height || 0)
        if (w > 0 && h > 0) return w >= h ? "4:3" : "3:4"
        return "3:4"
    }, [coverAspectOverride, material?.orientation, material?.video_width, material?.video_height])

    // 预览框：保留素材真实比例，但用 max-width 反向约束高（<= maxH），避免大盒子占满
    const coverBoxStyle = useMemo(() => {
        const isPortrait = inferredCoverAspect === "3:4"
        const ratio = isPortrait ? 3 / 4 : 4 / 3 // width / height
        const maxH = 280
        return {
            aspectRatio: isPortrait ? "3 / 4" : "4 / 3",
            maxWidth: `min(100%, ${Math.round(maxH * ratio)}px)`,
            marginLeft: "auto",
            marginRight: "auto",
        }
    }, [inferredCoverAspect])

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
    const [autoSaveStatus, setAutoSaveStatus] = useState("")
    const saveCallbackRef = useRef(onSave)
    saveCallbackRef.current = onSave
    const hydratedDraftRef = useRef<string | null>(null)
    const savedSnapshotRef = useRef("")
    const saveQueueRef = useRef(Promise.resolve())


    useEffect(() => {
        const identity = `${material?.id || "new"}:${mode}`
        if (!initialData && initializedFormRef.current === identity) return
        initializedFormRef.current = identity
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
        if (material?.id && mode === "edit" && !initialData) {
            const key = `materialEditorDraft:${material.id}:default`
            try {
                const draft = JSON.parse(localStorage.getItem(key) || "null")
                if (draft?.form) setEditForm(prev => ({ ...prev, ...draft.form }))
                if (typeof draft?.coverPrompt === "string") setCoverPrompt(draft.coverPrompt)
            } catch { /* Ignore invalid drafts. */ }
            hydratedDraftRef.current = null
            savedSnapshotRef.current = ""
        }
    }, [material, mode, initialData])

    useEffect(() => {
        if (!material?.id || mode !== "edit" || initialData || hideFooter) return
        const key = `materialEditorDraft:${material.id}:${activePreset}`
        const snapshot = JSON.stringify({ ...editForm, updateDiskFile, ...(activePreset !== "default" ? { coverPrompt, coverAspectOverride, presetPlatform } : {}) })
        if (hydratedDraftRef.current !== key) {
            hydratedDraftRef.current = key
            savedSnapshotRef.current = snapshot
            return
        }
        localStorage.setItem(key, JSON.stringify({ form: editForm, coverPrompt }))
        if (snapshot === savedSnapshotRef.current) return
        setAutoSaveStatus("等待自动保存…")
        const data = { ...editForm, group: editForm.group === "none" ? "" : editForm.group, updateDiskFile, autoSave: true }
        const saveCurrent = saveCallbackRef.current
        let disposed = false
        const persist = () => {
            saveQueueRef.current = saveQueueRef.current.catch(() => {}).then(async () => {
                if (!disposed) setAutoSaveStatus("自动保存中…")
                try {
                    if (activePreset === "default") {
                        await saveCurrent(data)
                    } else {
                        const preset = { name: presets[activePreset]?.name || "平台预设", platform: presetPlatform, data: { form: editForm, coverPrompt, coverAspect: coverAspectOverride } }
                        const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/presets/${activePreset}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(preset) })
                        if (!response.ok) throw new Error("预设保存失败")
                    }
                    savedSnapshotRef.current = snapshot
                    if (!disposed) setAutoSaveStatus("已自动保存")
                } catch {
                    if (!disposed) setAutoSaveStatus("保存失败，输入已保留在本机")
                }
            })
        }
        const timer = setTimeout(persist, 1200)
        return () => {
            disposed = true
            clearTimeout(timer)
        }
    }, [editForm, coverPrompt, updateDiskFile, material?.id, mode, initialData, hideFooter, activePreset, presets, presetPlatform, coverAspectOverride])

    useEffect(() => {
        setFirstFrameSrc("")
        setFirstFrameError("")
        if (!material?.id || mode === "batch" || !useFirstFrame) return
        const controller = new AbortController()
        void (async () => {
            try {
                const response = await fetch(`${backendBaseUrl}/api/v1/files/${encodeURIComponent(material.id)}/first-frame`, { signal: controller.signal })
                const payload = await response.json()
                if (!response.ok || !payload?.data?.url) throw new Error(payload?.detail || "首帧提取失败")
                setFirstFrameSrc(new URL(payload.data.url, backendBaseUrl).href)
            } catch (error) {
                if (!controller.signal.aborted) setFirstFrameError(error instanceof Error ? error.message : "首帧提取失败")
            }
        })()
        return () => controller.abort()
    }, [material?.id, mode, useFirstFrame])

    useEffect(() => {
        if (initialPresetId === "default") return
        const preset = presets[initialPresetId]
        if (!preset || appliedPresetRef.current === initialPresetId) return
        appliedPresetRef.current = initialPresetId
        setActivePreset(initialPresetId)
        setPresetPlatform(preset.platform)
        setCoverPlatform(preset.platform)
        if (preset.data.form) setEditForm(prev => ({ ...prev, ...preset.data.form, cover_image: preset.data.form.cover_image || "" }))
        setCoverPrompt(preset.data.coverPrompt || "")
        setCoverAspectOverride(preset.data.coverAspect || null)
    }, [initialPresetId, presets])

    const coverSrc = useMemo(() => {
        // Each preset owns its applied cover. Library selections must not override an empty preset.
        const raw = editForm.cover_image.trim()
        if (!raw) return ""
        if (raw.startsWith("http")) return raw
        return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
    }, [editForm.cover_image])

    const coverJobStorageKey = useMemo(() => {
        return material?.id ? `aiCoverJob:${material.id}` : ""
    }, [material?.id])

    const stopCoverPolling = useCallback(() => {
        coverPollGenerationRef.current += 1
        if (coverPollTimerRef.current) {
            clearTimeout(coverPollTimerRef.current)
            coverPollTimerRef.current = null
        }
    }, [])

    const pollCoverJob = useCallback(async (jobId: string) => {
        if (!jobId) return
        stopCoverPolling()
        const generation = coverPollGenerationRef.current

        const tick = async () => {
            if (generation !== coverPollGenerationRef.current) return
            try {
                const response = await fetch(`/api/v1/files/ai-cover-jobs/${encodeURIComponent(jobId)}`)
                const payload = await response.json().catch(() => ({}))
                if (generation !== coverPollGenerationRef.current) return
                if (response.status === 404) {
                    stopCoverPolling()
                    setCoverJobStatus("failed")
                    setCoverJobError("生成任务已失效（服务可能已重启），请重新生成封面。")
                    setCoverJobId(null)
                    if (coverJobStorageKey) localStorage.removeItem(coverJobStorageKey)
                    return
                }
                if (!response.ok) throw new Error(payload?.detail || "无法读取生成进度，请检查后端连接。")
                const status = payload?.data?.status as typeof coverJobStatus | undefined
                const coverPath = payload?.data?.cover_path as string | undefined
                const error = payload?.data?.error as string | undefined

                if (status) setCoverJobStatus(status)
                if (payload?.data?.stage) setCoverStage(payload.data.stage)
                if (payload?.data?.created_at) {
                    const timestamp = Date.parse(payload.data.created_at)
                    if (Number.isFinite(timestamp)) setCoverStartedAt(timestamp)
                }

                if (status === "succeeded" && coverPath) {
                    setEditForm(prev => ({ ...prev, cover_image: coverPath }))
                    const libraryResponse = await fetch(`${backendBaseUrl}/api/v1/files/${material?.id}/covers`)
                    if (libraryResponse.ok) {
                        const libraryPayload = await libraryResponse.json()
                        setCoverLibrary(libraryPayload.data)
                    }
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
                if (generation !== coverPollGenerationRef.current) return
                setCoverJobError(e instanceof Error ? e.message : "封面生成失败")
            }

            if (generation === coverPollGenerationRef.current) coverPollTimerRef.current = setTimeout(tick, 1200)
        }

        tick()
    }, [coverJobStorageKey, stopCoverPolling, toast, material?.id])

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

    // 为上传的参考图生成可预览的 Object URL（并在变更/卸载时释放）
    useEffect(() => {
        if (!referenceImage) {
            setRefPreviewSrc("")
            return
        }
        const url = URL.createObjectURL(referenceImage)
        setRefPreviewSrc(url)
        return () => URL.revokeObjectURL(url)
    }, [referenceImage])

    const handleAIGenerate = async (field: 'title' | 'desc' | 'tags' | 'both') => {
        if (!editForm.description.trim() && !editForm.title.trim() && !editForm.tags.trim()) {
            toast({ title: "请补充素材内容", description: "请先输入内容说明、标题或标签，帮助 AI 理解素材" })
            return
        }
        setAiGenerating(field)

        try {
            const instructions = {
                title: "生成一个准确、吸引人的短视频标题，10-27字；只输出标题，不加引号或表情。",
                desc: "生成简洁的短视频描述；只输出描述，不加表情。",
                both: '生成标题和1-4个相关标签，只输出 JSON：{"title":"标题","tags":["标签"]}，标题10-27字。',
                tags: "提炼1-4个与实际内容相关的标签，空格分隔，不带#；只输出标签。",
            }
            const context = [
                platformContext,
                editForm.description.trim() && `内容说明（主要依据）：${editForm.description.trim()}`,
                editForm.title.trim() && `当前标题：${editForm.title.trim()}`,
                editForm.tags.trim() && `当前标签：${editForm.tags.trim()}`,
                editForm.note.trim() && `补充要求：${editForm.note.trim()}`,
                `文件名（仅辅助，随机编号不代表内容）：${editForm.filename || material?.filename || ""}`,
            ].filter(Boolean).join("\n")
            const prompt = `根据下面的用户信息生成内容，优先遵循内容说明，不编造事实，不添加无关的品牌或游戏名称。\n${instructions[field]}\n${context}`

            const response = await fetch(`${backendBaseUrl}/api/v1/ai/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: [{ role: 'user', content: prompt }],
                    stream: false
                })
            })

            const data = await response.json()
            if (!response.ok) throw new Error(data?.detail || "AI 生成失败")
            const content = data.content || data.message || ''
            if (typeof content !== "string" || !content.trim()) throw new Error("模型未返回有效内容")

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

            if (field === 'both') {
                const parsed = JSON.parse(content.trim().replace(/^```(?:json)?\s*/, "").replace(/\s*```$/, ""))
                if (typeof parsed.title !== "string" || !parsed.title.trim() || !Array.isArray(parsed.tags) || !parsed.tags.every((tag: unknown) => typeof tag === "string")) throw new Error("模型返回格式不正确，请重试")
                const candidate = { title: parsed.title.trim(), tags: normalizeTags(parsed.tags.join(" ")).join(" ") }
                setEditForm(prev => ({ ...prev, ...candidate }))
                await recordTextHistory(candidate)
            } else if (field === 'title') {
                setEditForm(prev => ({ ...prev, title: content.trim() }))
                await recordTextHistory({ title: content.trim() })
            } else if (field === 'desc') {
                setEditForm(prev => ({ ...prev, description: content.trim() }))
            } else if (field === 'tags') {
                const tags = normalizeTags(content.trim())
                setEditForm(prev => ({ ...prev, tags: tags.join(" ") }))
                await recordTextHistory({ tags: tags.join(" ") })
            }

            toast({ title: "AI 生成完成", description: "内容已自动填充" })
        } catch (error) {
            console.error('AI generation error:', error)
            toast({ variant: "destructive", title: "AI 生成失败", description: error instanceof Error ? error.message : "请稍后重试" })
        } finally {
            setAiGenerating(null)
        }
    }

    const handleGenerateCover = async (optimizedPrompt?: string) => {
        if (!coverPrompt.trim() && !editForm.description.trim() && !editForm.title.trim()) {
            toast({ variant: "destructive", title: "请输入提示词", description: "封面生成需要描述提示词" })
            return
        }
        if (!material?.id) {
            toast({ variant: "destructive", title: "无法生成封面", description: "请先保存素材后再生成封面" })
            return
        }

        setCoverJobError("")
        setCoverJobStatus("pending")
        setCoverStage("pending")
        setCoverStartedAt(Date.now())
        setCoverElapsed(0)

        try {
            const formData = new FormData()
            formData.append("platform_name", adaptPlatforms && selectedPlatforms.length ? selectedPlatforms.join("、") : "全平台")
            formData.append("aspect_ratio", inferredCoverAspect)
            formData.append("use_first_frame", String(useFirstFrame))
            formData.append("prompt", [
                referenceImage || useFirstFrame ? "以参考画面为主体，保留人物、物品和场景特征，设计清晰、有视觉层次的封面。" : "根据视频内容和设计要求生成清晰、有视觉层次的封面。",
                editForm.description.trim() && `视频内容：${editForm.description.trim()}`,
                editForm.title.trim() && `标题主题：${editForm.title.trim()}`,
                editForm.tags.trim() && `主题标签：${editForm.tags.trim()}`,
                (optimizedPrompt || coverPrompt).trim() && `设计要求：${(optimizedPrompt || coverPrompt).trim()}`,
            ].filter(Boolean).join("\n"))
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

    const handleFillSelected = async () => {
        if (aiFillBusyRef.current) return
        const targets = generationTargets.length ? generationTargets : ["title", "tags"]
        if (!editForm.description.trim()) {
            toast({ variant: "destructive", title: "请先填写内容说明", description: "只需描述素材内容，无需先填写标题或标签。" })
            return
        }
        aiFillBusyRef.current = true
        setAiGenerating("selected")
        try {
            const schemaExample = JSON.stringify({ ...(targets.includes("title") ? { title: "标题文本" } : {}), ...(targets.includes("tags") ? { tags: ["标签一", "标签二"] } : {}), ...(targets.includes("cover") ? { coverPrompt: "封面设计提示词" } : {}) })
            const requested = targets.map(target => ({ title: "title：10-27字标题", tags: "tags：1-4个标签的字符串数组", cover: "coverPrompt：结合视频主体、构图、光影、配色和标题安全区的中文封面设计提示词" })[target]).join("；")
            const response = await fetch(`${backendBaseUrl}/api/v1/ai/chat`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ structured_output: true, stream: false, messages: [{ role: "user", content: `根据内容说明生成所选项目，只输出 JSON 对象，字段必须与此模板一致：${schemaExample}。生成要求：${requested}。不编造事实，不添加无关品牌。封面提示词要求保留参考图主体，不生成水印。${platformContext}\n内容说明：${editForm.description.trim()}\n封面额外要求：${coverPrompt}` }] }),
            })
            const payload = await response.json()
            if (!response.ok) throw new Error(payload?.detail || "生成失败")
            const content = payload.content || payload.message
            if (typeof content !== "string") throw new Error("模型未返回有效内容")
            const result = parseMaterialAIResult(content)
            if (targets.includes("title") && (typeof result.title !== "string" || !result.title.trim())) throw new Error("模型未返回标题")
            if (targets.includes("tags") && (!Array.isArray(result.tags) || !result.tags.every((tag: unknown) => typeof tag === "string"))) throw new Error("模型未返回有效标签")
            if (targets.includes("cover") && (typeof result.coverPrompt !== "string" || !result.coverPrompt.trim())) throw new Error("模型未返回封面提示词")
            const candidate = {
                ...(targets.includes("title") ? { title: result.title.trim() } : {}),
                ...(targets.includes("tags") ? { tags: [...new Set<string>(result.tags.map((tag: string) => tag.trim().replace(/^#/, "")).filter(Boolean))].slice(0, 4).join(" ") } : {}),
            }
            setEditForm(prev => ({ ...prev, ...candidate }))
            if (candidate.title || candidate.tags) await recordTextHistory(candidate)
            if (targets.includes("cover")) {
                setCoverPrompt(result.coverPrompt.trim())
                await handleGenerateCover(result.coverPrompt.trim())
            }
            toast({ title: "AI 填充完成", description: targets.includes("cover") ? "已优化封面提示词并提交图片生成任务。" : "生成内容已填充，系统会自动保存。" })
        } catch (error) {
            toast({ variant: "destructive", title: "AI 填充失败", description: error instanceof TypeError ? "后端连接中断，请稍后重试；输入已保留。" : error instanceof Error ? error.message : "请稍后重试" })
        } finally { aiFillBusyRef.current = false; setAiGenerating(null) }
    }

    const handleSave = async () => {
        setLocalIsSaving(true)
        try {
            if (activePreset !== "default" && material?.id) {
                const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/presets/${activePreset}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: presets[activePreset]?.name || "平台预设", platform: presetPlatform, data: { form: editForm, coverPrompt, coverAspect: coverAspectOverride } }) })
                if (!response.ok) throw new Error("预设保存失败")
                setAutoSaveStatus("预设已保存")
                return
            }
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
            <AlertDialog open={!!coverToDelete} onOpenChange={open => { if (!open && !deletingCover) setCoverToDelete(null) }}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>删除这张封面？</AlertDialogTitle>
                        <AlertDialogDescription>删除后无法恢复，其他封面将保留。</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deletingCover}>取消</AlertDialogCancel>
                        <AlertDialogAction disabled={deletingCover} className="bg-red-600 text-white hover:bg-red-700" onClick={async event => {
                            event.preventDefault()
                            if (!coverToDelete || !material?.id) return
                            setDeletingCover(true)
                            try {
                                const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/covers/${encodeURIComponent(coverToDelete.id)}`, { method: "DELETE" })
                                const payload = await response.json()
                                if (!response.ok) throw new Error(payload.detail || "删除失败")
                                setCoverLibrary(payload.data)
                                if (editForm.cover_image === coverToDelete.path) setEditForm(prev => ({ ...prev, cover_image: "" }))
                                setCoverToDelete(null)
                            } catch (error) { toast({ title: "删除封面失败", description: error instanceof Error ? error.message : "请重试", variant: "destructive" }) }
                            finally { setDeletingCover(false) }
                        }}>{deletingCover ? "删除中…" : "删除封面"}</AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <Dialog open={coverPreviewOpen} onOpenChange={setCoverPreviewOpen}>
                <DialogContent className="w-[92vw] max-w-5xl border-white/15 bg-zinc-950 p-4">
                    <DialogTitle>封面预览</DialogTitle>
                    <DialogDescription className="sr-only">完整查看当前封面，按 Escape 或点击关闭按钮返回编辑。</DialogDescription>
                    <div className="relative h-[75vh] w-full">
                        {coverSrc ? <Image src={coverSrc} alt="完整封面预览" fill sizes="92vw" className="object-contain" unoptimized /> : null}
                    </div>
                </DialogContent>
            </Dialog>
            {!hideFooter && (
                <div className="px-6 py-4 border-b border-border/70 bg-black flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1">
                            <Button variant="secondary" onClick={() => void handleFillSelected()} disabled={!!aiGenerating || coverBusy}>
                                {aiGenerating === "selected" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                                AI 填充
                            </Button>
                            <Popover>
                                <PopoverTrigger asChild><Button variant="secondary" size="icon" aria-label="选择 AI 填充项目"><ChevronDown className="h-4 w-4" /></Button></PopoverTrigger>
                                <PopoverContent align="start" sideOffset={10} className="w-[360px] max-w-[calc(100vw-2rem)] rounded-2xl border border-white/15 bg-zinc-950 p-5 text-zinc-100 shadow-2xl">
                                    <div className="mb-4">
                                        <div className="text-sm font-semibold">生成选项</div>
                                        <p className="mt-1 text-xs text-zinc-400">根据内容说明，生成你需要的内容</p>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
                                        {[["title", "标题", "提炼亮点"], ["tags", "标签", "精准话题"], ["cover", "封面", "优化后生成"]].map(([value, label, hint]) => {
                                            const active = generationTargets.includes(value) || (!generationTargets.length && value !== "cover")
                                            return <button key={value} type="button" aria-pressed={active} className={cn("rounded-xl border px-2 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400", active ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/5 text-zinc-300 hover:bg-white/10")} onClick={() => setGenerationTargets(prev => {
                                                const current = prev.length ? prev : ["title", "tags"]
                                                return current.includes(value) ? current.filter(item => item !== value) : [...current, value]
                                            })}>
                                                <span className="flex items-center justify-between text-sm font-medium">{label}<span className={cn("h-2 w-2 rounded-full", active ? "bg-blue-400" : "bg-zinc-600")} /></span>
                                                <span className="mt-1 block text-[11px] text-zinc-400">{hint}</span>
                                            </button>
                                        })}
                                    </div>
                                    <div className="mt-5 border-t border-white/10 pt-4">
                                        <button type="button" role="switch" aria-checked={adaptPlatforms} onClick={() => setAdaptPlatforms(prev => !prev)} className="flex w-full items-center justify-between rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                                            <span><span className="block text-sm font-medium">适配平台调性</span><span className="mt-1 block text-xs text-zinc-400">调整表达风格与内容重点</span></span>
                                            <span className={cn("flex h-5 w-9 items-center rounded-full p-0.5 transition-colors", adaptPlatforms ? "justify-end bg-blue-500" : "justify-start bg-zinc-700")}><span className="h-4 w-4 rounded-full bg-white" /></span>
                                        </button>
                                        {adaptPlatforms ? <div className="mt-3 grid grid-cols-4 gap-2">
                                            {["抖音", "小红书", "快手", "B站", "视频号", "TikTok", "YouTube", "Instagram"].map(platform => <button key={platform} type="button" aria-pressed={selectedPlatforms.includes(platform)} className={cn("rounded-lg border px-1 py-2 text-[11px] transition-colors focus-visible:ring-2 focus-visible:ring-blue-400", selectedPlatforms.includes(platform) ? "border-blue-400/50 bg-blue-500/15 text-blue-100" : "border-white/10 text-zinc-400 hover:bg-white/10")} onClick={() => setSelectedPlatforms(prev => prev.includes(platform) ? prev.filter(item => item !== platform) : [...prev, platform])}>{platform}</button>)}
                                        </div> : null}
                                    </div>
                                    <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-3">
                                        <span className="text-[11px] text-zinc-500">默认生成标题和标签</span>
                                        <Button size="sm" onClick={() => void handleFillSelected()} disabled={!!aiGenerating || coverBusy} className="rounded-lg bg-blue-500 text-white hover:bg-blue-600">开始生成</Button>
                                    </div>
                                </PopoverContent>
                            </Popover>
                        </div>
                        <span className="text-xs text-muted-foreground" role="status">{autoSaveStatus}</span>
                    </div>
                    <Button onClick={handleSave} disabled={isSaving} className="min-w-[100px]">
                        {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : (mode === 'create' ? "确认发布" : "保存更改")}
                    </Button>
                </div>
            )}

            <ScrollArea className="flex-1 px-6 py-6">
                <div className="space-y-8 pb-20">

                    {mode === "edit" ? <div className="space-y-3 rounded-xl border border-border/70 p-4">
                        <Label>素材发布预设</Label>
                        <Select value={activePreset} onValueChange={async value => {
                            if (!material?.id || value === activePreset) return
                            try {
                                if (activePreset === "default") {
                                    await saveCallbackRef.current({ ...editForm, group: editForm.group === "none" ? "" : editForm.group, updateDiskFile, autoSave: true })
                                } else {
                                    const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/presets/${activePreset}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: presets[activePreset]?.name || "平台预设", platform: presetPlatform, data: { form: editForm, coverPrompt, coverAspect: coverAspectOverride } }) })
                                    if (!response.ok) throw new Error("预设保存失败")
                                }
                            } catch {
                                toast({ title: "当前预设保存失败", description: "请重试后切换预设", variant: "destructive" })
                                return
                            }
                            setPresets(prev => ({ ...prev, [activePreset]: { name: prev[activePreset]?.name || "通用配置", platform: presetPlatform, data: { form: editForm, coverPrompt, coverAspect: coverAspectOverride } } }))
                            const target = presets[value]
                            setActivePreset(value)
                            setPresetPlatform(target?.platform || "all")
                            setCoverPlatform(target?.platform || "all")
                            setCoverAspectOverride(target?.data.coverAspect || null)
                            setCoverPrompt(target?.data.coverPrompt || "")
                            if (target?.data.form) setEditForm(prev => ({ ...prev, ...target.data.form, cover_image: target.data.form.cover_image || "" }))
                        }}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent><SelectItem value="default">通用配置</SelectItem>{Object.entries(presets).filter(([id]) => id !== "default").map(([id, preset]) => <SelectItem key={id} value={id}>{preset.name}</SelectItem>)}</SelectContent>
                        </Select>
                        <div className="flex gap-2">
                            <Input placeholder="新预设名称，如：抖音日常版" value={presetName} onChange={event => setPresetName(event.target.value)} />
                            <Button className="shrink-0 bg-white text-black hover:bg-zinc-200" disabled={!presetName.trim()} onClick={async () => {
                                if (!material?.id) return
                                const id = crypto.randomUUID()
                                const preset = { name: presetName.trim(), platform: coverPlatform, data: { form: editForm, coverPrompt, coverAspect: coverAspectOverride } }
                                try {
                                    const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/presets/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(preset) })
                                    if (!response.ok) throw new Error("创建预设失败")
                                    setPresets(prev => ({ ...prev, [id]: preset, [activePreset]: { name: prev[activePreset]?.name || "通用配置", platform: presetPlatform, data: { form: editForm, coverPrompt, coverAspect: coverAspectOverride } } }))
                                    setActivePreset(id); setPresetPlatform(coverPlatform); setPresetName("")
                                } catch { toast({ title: "创建预设失败", variant: "destructive" }) }
                            }}>新增预设</Button>
                        </div>
                        {activePreset !== "default" ? <Select value={presetPlatform} onValueChange={value => { setPresetPlatform(value); setCoverPlatform(value) }}><SelectTrigger aria-label="预设适用平台"><SelectValue /></SelectTrigger><SelectContent>{[["all", "全平台"], ["douyin", "抖音"], ["xiaohongshu", "小红书"], ["bilibili", "B站"], ["kuaishou", "快手"], ["wechat", "视频号"], ["tiktok", "TikTok"], ["youtube", "YouTube"], ["instagram", "Instagram"]].map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select> : null}
                        <p className="text-xs text-muted-foreground">每份预设独立保存标题、标签、内容说明与封面。新预设复制当前配置。</p>
                    </div> : null}

                    {/* Content Info - 内容设置 */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">内容设置</h3>
                            <Badge variant="secondary" className="bg-black text-white border-border">
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
                                            className="h-3.5 w-3.5 rounded border-border/80 bg-black text-primary focus:ring-2 focus:ring-primary cursor-pointer"
                                        />
                                        <label htmlFor="update-disk-file" className="text-xs text-muted-foreground cursor-pointer">
                                            同步修改磁盘文件名
                                        </label>
                                    </div>
                                </div>
                                <Input
                                    value={editForm.filename}
                                    onChange={e => setEditForm(prev => ({ ...prev, filename: e.target.value }))}
                                    className="bg-card border-border/70"
                                    placeholder="输入文件名（含扩展名）"
                                />
                                {/* <p className="text-xs text-foreground/40">
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
                                        className="h-6 text-xs text-muted-foreground hover:text-foreground hover:bg-card/50"
                                        onClick={() => handleAIGenerate('title')}
                                        disabled={!!aiGenerating}
                                    >
                                        {aiGenerating === 'title' ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Wand2 className="w-3 h-3 mr-1" />}
                                        AI 生成
                                    </Button>
                                </div>
                                <EditableHistoryInput
                                    value={editForm.title}
                                    onChange={value => setEditForm(prev => ({ ...prev, title: value }))}
                                    history={textHistory.titles}
                                    onDelete={value => deleteTextHistory("titles", value)}
                                    label="标题"
                                    placeholder="输入标题或选择生成记录"
                                />

                            </div>

                            {/* <div className="grid gap-2">
                                <div className="flex justify-between items-center">
                                    <Label>描述</Label>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-6 text-xs text-muted-foreground hover:text-foreground hover:bg-card/50"
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
                                    className="bg-black border-border/70 min-h-[100px]"
                                    placeholder="输入视频描述或脚本..."
                                />
                            </div> */}

                            <div className="grid gap-2">
                                <div className="flex justify-between items-center">
                                    <Label>标签</Label>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-6 text-xs text-muted-foreground hover:text-foreground hover:bg-card/50"
                                        onClick={() => handleAIGenerate('tags')}
                                        disabled={!!aiGenerating}
                                    >
                                        {aiGenerating === 'tags' ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Wand2 className="w-3 h-3 mr-1" />}
                                        AI 推荐
                                    </Button>
                                </div>
                                <EditableHistoryInput
                                    value={editForm.tags}
                                    onChange={value => setEditForm(prev => ({ ...prev, tags: value }))}
                                    history={textHistory.tags}
                                    onDelete={value => deleteTextHistory("tags", value)}
                                    label="标签"
                                    placeholder="输入标签或选择生成记录"
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
                                        <SelectTrigger className="bg-card border-border/70">
                                            <SelectValue placeholder="选择分组" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-black border-border/70 text-foreground">
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

                    <div className="space-y-2">
                        <Label htmlFor="material-content-brief">内容说明 · AI 生成依据</Label>
                        <Textarea
                            id="material-content-brief"
                            value={editForm.description}
                            onChange={(event) => setEditForm(prev => ({ ...prev, description: event.target.value }))}
                            placeholder="描述视频讲什么、主体和场景、希望突出哪些亮点，以及目标受众。标题、标签和封面都会结合这些信息生成。"
                            className="min-h-[100px]"
                        />
                        <p className="text-xs text-muted-foreground">内容说明会随素材保存，可分别点击标题、标签和封面的 AI 按钮生成。</p>
                    </div>

                    {/* AI 封面工坊 · 图生图（参考图 → 封面） */}
                    <div className="space-y-4 rounded-xl border border-border/50 bg-card/40 p-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">封面工坊 · 图生图</h3>
                                <Badge variant="secondary" className="bg-black text-white border-border">
                                    <Sparkles className="w-3 h-3 mr-1" /> AI
                                </Badge>
                            </div>
                            {(coverJobStatus === "pending" || coverJobStatus === "running") && (
                                <Badge variant="secondary" className="bg-black text-white border-border">
                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" /> 生成中
                                </Badge>
                            )}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                            {/* 左侧：AI 封面结果预览 */}
                            <div className="md:col-span-2 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <Label className="text-xs text-muted-foreground">封面</Label>
                                    <div className="flex gap-1">
                                        {(["3:4", "4:3"] as const).map(ratio => <Button key={ratio} size="sm" variant={inferredCoverAspect === ratio ? "default" : "secondary"} onClick={() => setCoverAspectOverride(ratio)}>{ratio === "3:4" ? "竖版" : "横版"}</Button>)}
                                    </div>
                                </div>
                                <Select value={coverPlatform} onValueChange={setCoverPlatform}>
                                    <SelectTrigger aria-label="封面适用平台"><SelectValue /></SelectTrigger>
                                    <SelectContent>{[["all", "通用封面"], ["douyin", "抖音"], ["xiaohongshu", "小红书"], ["kuaishou", "快手"], ["bilibili", "B站"], ["wechat", "视频号"], ["tiktok", "TikTok"], ["youtube", "YouTube"], ["instagram", "Instagram"]].map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                                </Select>
                                <Button className="w-full bg-white text-black hover:bg-zinc-200" disabled={!coverSrc || uploadingCovers} onClick={async () => {
                                    if (!material?.id) return
                                    const path = editForm.cover_image
                                    setUploadingCovers(true)
                                    try {
                                        const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/covers/adapt`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, platform: coverPlatform }) })
                                        const payload = await response.json()
                                        if (!response.ok) throw new Error(payload.detail || "适配失败")
                                        setCoverLibrary(payload.data)
                                        toast({ title: "横竖封面已保存", description: "已裁切为3:4与4:3，可切换查看并使用。" })
                                    } catch (error) { toast({ title: "封面适配失败", description: error instanceof Error ? error.message : "请重试", variant: "destructive" }) }
                                    finally { setUploadingCovers(false) }
                                }}>一键裁切横竖版</Button>
                                <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-border/70 px-3 py-3 text-xs">
                                    <UploadCloud className="h-4 w-4" />{uploadingCovers ? "上传中…" : "上传封面 · 支持横竖多张"}
                                    <input type="file" accept="image/*" multiple disabled={uploadingCovers || !material?.id} className="hidden" onChange={async event => {
                                        const files = Array.from(event.target.files || [])
                                        event.target.value = ""
                                        if (!files.length || !material?.id) return
                                        setUploadingCovers(true)
                                        try {
                                            const form = new FormData()
                                            form.append("platform", coverPlatform)
                                            files.forEach(file => form.append("images", file))
                                            const response = await fetch(`${backendBaseUrl}/api/v1/files/${material.id}/covers`, { method: "POST", body: form })
                                            const payload = await response.json()
                                            if (!response.ok) throw new Error(payload.detail || "上传失败")
                                            setCoverLibrary(payload.data)
                                            toast({ title: "封面已上传", description: "已按平台与横竖比例分别保存" })
                                        } catch (error) { toast({ title: "封面上传失败", description: error instanceof Error ? error.message : "请重试", variant: "destructive" }) }
                                        finally { setUploadingCovers(false) }
                                    }} />
                                </label>
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs text-zinc-400">封面库 · {coverLibrary.items.length} 张</span>
                                    <Button size="sm" variant="secondary" onClick={() => setShowAllCovers(value => !value)}>{showAllCovers ? "全部封面 · 点击筛选" : "当前平台与比例 · 查看全部"}</Button>
                                </div>
                                <div className="grid grid-cols-3 gap-2">
                                    {coverLibrary.items.filter(item => showAllCovers || (item.platform === coverPlatform && item.orientation === (inferredCoverAspect === "3:4" ? "portrait" : "landscape"))).map(item => <div key={item.id} className="overflow-hidden rounded-xl border border-white/15 bg-zinc-950"><button type="button" aria-label="选择封面" aria-pressed={editForm.cover_image === item.path} className={cn("relative block w-full overflow-hidden rounded-t-xl border-2", editForm.cover_image === item.path ? "border-blue-400" : "border-transparent")} onClick={async () => {
                                        try {
                                            const response = await fetch(`${backendBaseUrl}/api/v1/files/${material?.id}/covers/select`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cover_id: item.id }) })
                                            if (!response.ok) throw new Error("选择封面失败")
                                            const payload = await response.json()
                                            setCoverLibrary(payload.data)
                                            setEditForm(prev => ({ ...prev, cover_image: item.path }))
                                            setCoverAspectOverride(item.orientation === "portrait" ? "3:4" : "4:3")
                                        } catch { toast({ title: "选择封面失败", variant: "destructive" }) }
                                    }}><Image src={`${backendBaseUrl}/getFile?filename=${encodeURIComponent(item.path)}`} alt="封面" width={240} height={180} className="h-28 w-full bg-zinc-900 object-contain" unoptimized /></button><div className="flex items-center justify-between gap-2 px-2 py-2"><span className="text-[11px] text-zinc-400">{item.source === "generated" ? "AI 生成" : "本地封面"}<span className="ml-1 text-zinc-600">{item.width}×{item.height}</span></span><button type="button" aria-label="删除这张封面" className="shrink-0 rounded-md border border-white/15 bg-white px-2 py-1 text-[11px] text-black hover:bg-zinc-200" onClick={() => setCoverToDelete({ id: item.id, path: item.path })}>删除</button></div></div>)}
                                </div>
                                <div
                                    className="relative w-full rounded-lg border border-border/70 bg-card overflow-hidden group"
                                    style={coverBoxStyle}
                                >
                                    {coverSrc ? (
                                        <button type="button" aria-label="放大预览封面" className="absolute inset-0 cursor-zoom-in focus-visible:ring-2 focus-visible:ring-blue-400" onClick={() => setCoverPreviewOpen(true)}>
                                            <Image src={coverSrc} alt="AI 封面预览" fill className="object-contain" unoptimized />
                                        </button>
                                    ) : (
                                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-foreground/20">
                                            <ImageIcon className="w-7 h-7" />
                                            <span className="text-[11px]">生成后在此预览</span>
                                        </div>
                                    )}

                                </div>
                                <div className="text-center text-xs text-foreground/40">{inferredCoverAspect} · 封面预览</div>
                                {coverSrc ? <div className="flex justify-center gap-2">
                                    <Button className="bg-white text-black hover:bg-zinc-200" size="sm" onClick={() => setCoverPreviewOpen(true)}>放大预览</Button>
                                    <Button className="bg-white text-black hover:bg-zinc-200" size="sm" onClick={() => {
                                        setEditForm(prev => ({ ...prev, cover_image: "" }))
                                    }}>清除封面</Button>


                                </div> : null}
                            </div>

                            {/* 右侧：参考图（图生图输入）+ 提示词 */}
                            <div className="md:col-span-3 space-y-3">
                                {/* 参考图上传（带缩略图预览） */}
                                <div className="space-y-1.5">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-xs text-muted-foreground">参考图</Label>
                                        {referenceImage && (
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="h-6 text-xs text-muted-foreground hover:text-foreground hover:bg-card/10"
                                                onClick={() => setReferenceImage(null)}
                                            >
                                                移除
                                            </Button>
                                        )}
                                    </div>
                                    <div className="flex items-center justify-between gap-3 py-2">
                                        <Label htmlFor="cover-use-first-frame" className="text-xs">使用视频首帧</Label>
                                        <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">{useFirstFrame ? "已开启" : "已关闭"}</span><Switch id="cover-use-first-frame" checked={useFirstFrame} onCheckedChange={setUseFirstFrame} /></div>
                                    </div>
                                    {!useFirstFrame && !referenceImage && <p className="text-xs text-muted-foreground">已关闭首帧参考，将按提示词生成封面；也可上传参考图。</p>}
                                    {useFirstFrame && !referenceImage && firstFrameSrc ? (
                                        <div className="space-y-1 rounded-lg border border-border/70 p-2">
                                            <Image src={firstFrameSrc} alt="视频首帧参考" width={320} height={180} className="max-h-40 w-full object-contain" unoptimized />
                                            <p className="text-xs text-muted-foreground">已自动提取视频首帧；上传图片可替换参考。</p>
                                        </div>
                                    ) : null}
                                    {useFirstFrame && !referenceImage && firstFrameError ? <p className="text-xs text-red-400">{firstFrameError}；可上传参考图。</p> : null}
                                    {referenceImage ? (
                                        <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-card p-2">
                                            {refPreviewSrc && <img
                                                src={refPreviewSrc}
                                                alt="参考图预览"
                                                className="h-12 w-12 rounded-md object-cover shrink-0"
                                            />}
                                            <div className="flex-1 min-w-0">
                                                <p className="text-xs text-foreground/80 truncate">{referenceImage.name}</p>
                                                <p className="text-[10px] text-muted-foreground">将作为图生图参考</p>
                                            </div>
                                            <Button
                                                size="icon"
                                                variant="ghost"
                                                className="h-7 w-7 text-foreground/40 hover:text-foreground"
                                                onClick={() => setReferenceImage(null)}
                                            >
                                                <X className="h-3.5 w-3.5" />
                                            </Button>
                                        </div>
                                    ) : (
                                        <div
                                            className="flex items-center justify-center gap-2 w-full h-14 rounded-lg border border-dashed border-border/70 bg-card cursor-pointer hover:border-border/90 transition-colors"
                                            onDragOver={(e) => { e.preventDefault(); e.stopPropagation() }}
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
                                            <UploadCloud className="h-4 w-4 text-foreground/40" />
                                            <span className="text-xs text-muted-foreground">点击或拖拽上传参考图</span>
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
                                    )}
                                </div>

                                {/* 提示词 */}
                                <div className="space-y-1.5">
                                    <Label className="text-xs text-muted-foreground">AI 封面提示词</Label>
                                    <Textarea
                                        value={coverPrompt}
                                        onChange={e => setCoverPrompt(e.target.value)}
                                        className="bg-card border-border/70 text-sm resize-none min-h-[80px]"
                                        placeholder="描述想要的封面画面，可结合参考图风格..."
                                    />
                                </div>

                                {/* 生成按钮 + 状态 */}
                                <Button
                                    className="w-full bg-foreground text-background hover:bg-foreground/90 border-0"
                                    onClick={() => void handleGenerateCover()}
                                    disabled={!!aiGenerating || coverJobStatus === "pending" || coverJobStatus === "running"}
                                >
                                    {(coverJobStatus === "pending" || coverJobStatus === "running") ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Wand2 className="w-4 h-4" />
                                    )}
                                    <span className="ml-2 text-sm">
                                        {(coverJobStatus === "pending" || coverJobStatus === "running") ? "生成中..." : "生成封面"}
                                    </span>
                                </Button>
                                {coverBusy ? (
                                    <div className="space-y-2" role="status" aria-live="polite">
                                        <div className="flex justify-between text-xs text-muted-foreground">
                                            <span>{coverJobStatus === "pending" ? "正在提交任务" : coverStage === "preparing" ? "准备参考图和提示词" : coverStage === "saving" ? "生成完成，正在保存封面" : "图片服务正在生成"}</span>
                                            <span>已等待 {coverElapsed} 秒</span>
                                        </div>
                                        <div role="progressbar" aria-label="封面生成进度" className="h-2 overflow-hidden rounded-full bg-foreground/10">
                                            <div className="h-full w-1/3 animate-pulse rounded-full bg-foreground/70" />
                                        </div>
                                        <p className="text-[11px] text-muted-foreground">图片服务未提供百分比，进度条表示任务正在处理。</p>
                                    </div>
                                ) : coverJobStatus === "succeeded" ? (
                                    <div className="space-y-1" role="status">
                                        <div role="progressbar" aria-label="封面生成完成" aria-valuenow={100} aria-valuemin={0} aria-valuemax={100} className="h-2 rounded-full bg-green-500" />
                                        <p className="text-xs text-muted-foreground">100% · 封面已生成</p>
                                    </div>
                                ) : null}
                                {coverJobError && (
                                    <p className="text-xs text-red-400">{coverJobError}</p>
                                )}
                                <p className="text-[11px] text-muted-foreground leading-relaxed">
                                    可开关视频首帧参考；上传参考图后优先使用上传图片。结合内容说明、标题、标签和设计要求生成封面，完成后自动回填预览。
                                </p>
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
    showGroupSelector = true,
    initialPresetId = "default"
 }: MaterialEditorSheetProps) {
    const [panelWidth, setPanelWidth] = useState(770)
    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" style={{ width: `min(100vw, ${panelWidth}px)`, maxWidth: "100vw" }} className="border-l border-border/70 bg-black p-0 flex flex-col shadow-2xl">
                <div role="separator" aria-label="拖动调整编辑面板宽度" aria-orientation="vertical" tabIndex={0} className="absolute left-0 top-0 z-50 h-full w-2 cursor-col-resize touch-none hover:bg-blue-400/40 focus-visible:bg-blue-400/40" onKeyDown={event => {
                    if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); setPanelWidth(prev => Math.max(420, Math.min(window.innerWidth, prev + (event.key === "ArrowLeft" ? 40 : -40)))) }
                }} onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId) }} onPointerMove={event => {
                    if (event.currentTarget.hasPointerCapture(event.pointerId)) setPanelWidth(Math.max(Math.min(420, window.innerWidth), Math.min(window.innerWidth, window.innerWidth - event.clientX)))
                }} onPointerUp={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId) }} />
                <SheetHeader className="px-6 py-4 border-b border-border/70">
                    <SheetTitle>{mode === 'batch' ? '批量编辑素材' : '编辑素材详情'}</SheetTitle>
                    <SheetDescription>配置标题、描述与封面，支持 AI 一键生成。</SheetDescription>
                </SheetHeader>
                <MaterialEditorContent
                    key={`${material?.id}:${initialPresetId}`}
                    initialPresetId={initialPresetId}
                    material={material}
                    groupOptions={groupOptions}
                    onSave={async (data) => {
                        await onSave(data)
                        if (!data.autoSave) onOpenChange(false)
                    }}
                    mode={mode}
                    showGroupSelector={showGroupSelector}
                />
            </SheetContent>
        </Sheet>
    )
}
