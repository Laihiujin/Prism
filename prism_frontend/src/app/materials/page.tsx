"use client"

import { Suspense, startTransition, useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Trash2,
  UploadCloud,
  FileText,
  Plus,
  X,
  RefreshCw,
  Sparkles,
  Wand2,
} from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
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
import { useToast } from "@/components/ui/use-toast"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { DataTable } from "@/components/ui/data-table"
import { fetcher } from "@/lib/api"
import { useSearchParams } from "next/navigation"
import { backendBaseUrl } from "@/lib/env"
import { FileUpload } from "@/components/ui/file-upload"
import { type Material } from "@/lib/mock-data"
import { frontendMaterialsResponseSchema } from "@/lib/schemas"
import { type ColumnDef } from "@tanstack/react-table"
import { cn } from "@/lib/utils"
import { MaterialEditorSheet } from "@/components/material-editor-sheet"
import { PageHeader } from "@/components/layout/page-scaffold"

/** 限制文件名显示长度，但始终保留扩展名(如 .mp4/.jpg)，便于区分视频/图片 */
function truncateFilename(name: string, maxLen = 24): string {
  if (!name) return ""
  const dot = name.lastIndexOf(".")
  const ext = dot > 0 ? name.slice(dot) : ""
  const base = dot > 0 ? name.slice(0, dot) : name
  if (name.length <= maxLen) return name
  const keepBase = Math.max(1, maxLen - 1 - ext.length)
  if (base.length <= keepBase) return name
  return `${base.slice(0, keepBase)}…${ext}`
}

/** 根据扩展名判断是否为图片，用于预览(图片)与视频区分 */
function isImageFile(name: string): boolean {
  return /\.(jpe?g|png|gif|webp|bmp|avif|heic|heif)$/i.test(name || "")
}

function MaterialsPageContent() {
  const searchParams = useSearchParams()
  const { toast } = useToast()

  // State - Must be declared BEFORE useQuery to avoid TDZ errors
  const [materials, setMaterials] = useState<Material[]>([])
  const [keyword, setKeyword] = useState("")
  const [statusFilter, setStatusFilter] = useState<"all" | Material["status"]>("all")
  const [groupFilter, setGroupFilter] = useState<string>("all")

  // Queries
  const { data: materialsResponse, refetch } = useQuery({
    queryKey: ["materials", keyword],
    queryFn: () => {
      const params = new URLSearchParams()
      if (keyword) params.append("keyword", keyword)
      const url = keyword ? `/api/materials?${params.toString()}` : "/api/materials"
      return fetcher(url, frontendMaterialsResponseSchema)
    },
  })

  // Upload State
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [filesToUpload, setFilesToUpload] = useState<File[]>([])
  const [uploadGroup, setUploadGroup] = useState<string>("none")
  const [showNewGroup, setShowNewGroup] = useState(false)
  const [newGroupName, setNewGroupName] = useState("")
  const [localGroupOptions, setLocalGroupOptions] = useState<string[]>([])
  const [showGroupManager, setShowGroupManager] = useState(false)
  const [groupActionBusy, setGroupActionBusy] = useState(false)
  const [editingGroup, setEditingGroup] = useState<string | null>(null)
  const [editingGroupName, setEditingGroupName] = useState("")
  const [uploading, setUploading] = useState(false)

  // Explicit Sync State (for the button)
  const [isSyncing, setIsSyncing] = useState(false)

  // Edit Sheet State
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null)
  const [editForm, setEditForm] = useState({
    title: "",
    description: "",
    tags: "",
    note: "",
    group: "",
    cover_image: ""
  })
  const [aiGenerating, setAiGenerating] = useState<string | null>(null) // 'title' | 'desc' | 'tags' | 'cover'
  const [coverPrompt, setCoverPrompt] = useState("")

  // Preview Dialog State
  const [previewMaterial, setPreviewMaterial] = useState<Material | null>(null)

  // Multi-select State
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [isAllSelected, setIsAllSelected] = useState(false)

  const formatDuration = (seconds: unknown): string => {
    const n = typeof seconds === "number" ? seconds : Number(seconds)
    if (!Number.isFinite(n) || n <= 0) return "-"
    const total = Math.round(n)
    const m = Math.floor(total / 60)
    const s = total % 60
    return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`
  }

  const formatResolution = (material: Material): string => {
    const w = (material as any).video_width
    const h = (material as any).video_height
    const ar = (material as any).aspect_ratio
    if (!w || !h) return "-"
    const ratio = ar ? ` (${ar})` : ""
    return `${w}×${h}${ratio}`
  }

  const getPreviewUrl = (material: Material | null) => {
    if (!material) return ""
    const direct = (material as any).fileUrl || ""
    if (direct) {
      if (direct.startsWith("http")) return direct
      return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(direct)}`
    }
    const rawPath = (material as any).storageKey || (material as any).file_path
    if (rawPath) {
      return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(rawPath as string)}`
    }
    return ""
  }

  // Update local state when query data changes
  useEffect(() => {
    if (!materialsResponse?.data?.data) return
    startTransition(() => {
      setMaterials(materialsResponse.data.data)
    })
  }, [materialsResponse])

  // 当选中素材时，将其信息填充到编辑表单 (for legacy components if needed)
  useEffect(() => {
    if (selectedMaterial) {
      setEditForm({
        title: selectedMaterial.title || selectedMaterial.filename.split('.').slice(0, -1).join('.') || "",
        description: selectedMaterial.description || "",
        tags: selectedMaterial.tags || "",
        note: selectedMaterial.note || "",
        group: selectedMaterial.group || "none",
        cover_image: selectedMaterial.cover_image || ""
      })
      setCoverPrompt(`为视频 "${selectedMaterial.filename}" 生成一张吸引人的封面，风格现代，高清晰度`)
    }
  }, [selectedMaterial])

  // Filter Logic from searchParams
  useEffect(() => {
    const statusParam = searchParams.get("status") as any
    if (statusParam === "pending" || statusParam === "published" || statusParam === "all") {
      setStatusFilter(statusParam)
    }
    const groupParam = searchParams.get("group")
    if (groupParam) {
      setGroupFilter(groupParam)
    }
  }, [searchParams])

  const groupOptions = useMemo(() => {
    const set = new Set<string>()
    materials.forEach((m) => {
      if (m.group) set.add(m.group)
    })
    return Array.from(set).sort()
  }, [materials])

  const uploadGroupOptions = useMemo(() => {
    return Array.from(new Set([...groupOptions, ...localGroupOptions])).sort()
  }, [groupOptions, localGroupOptions])

  const filteredMaterials = useMemo(() => {
    return materials.filter((material) => {
      const matchStatus = statusFilter === "all" || material.status === statusFilter
      const matchGroup = groupFilter === "all" || (material.group || "") === groupFilter
      return matchStatus && matchGroup
    })
  }, [materials, statusFilter, groupFilter])

  // --- Actions ---

  const handleSync = async () => {
    setIsSyncing(true)
    const attempt = async (url: string) => {
      const res = await fetch(url, { method: "POST" })
      const text = await res.text()
      let data: any = {}
      try {
        data = JSON.parse(text)
      } catch {
        data = { message: text || "" }
      }
      return { ok: res.ok, status: res.status, data }
    }

    try {
      let result = await attempt(`/api/files/sync`)
      if (!result.ok) {
        result = await attempt(`${backendBaseUrl}/api/v1/files/sync`)
      }

      if (result.ok && result.data?.success !== false) {
        toast({
          variant: "success",
          title: "同步完成",
          description: `扫描 ${result.data?.data?.scanned ?? 0} 个文件，新增 ${result.data?.data?.added ?? 0} 个`
        })
        await refetch()
      } else {
        throw new Error(result.data?.message || `Sync failed (${result.status})`)
      }
    } catch (error: any) {
      console.error("sync failed", error)
      toast({
        variant: "destructive",
        title: "同步失败",
        description: error?.message || "无法连接到后端服务"
      })
    } finally {
      setIsSyncing(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      console.log('[材料删除] 开始删除，ID:', id)
      const response = await fetch(`${backendBaseUrl}/api/v1/files/${encodeURIComponent(id)}`, {
        method: 'DELETE'
      })
      console.log('[材料删除] 响应状态:', response.status, response.statusText)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('[材料删除] 删除失败:', errorText)
        throw new Error(`删除失败: ${response.status} ${errorText}`)
      }

      const result = await response.json()
      console.log('[材料删除] 删除成功:', result)

      toast({ title: "素材已删除", description: "该文件将无法再用于发布任务" })
      await refetch()
    } catch (error) {
      console.error('[材料删除] 异常:', error)
      toast({
        variant: "destructive",
        title: "删除失败",
        description: error instanceof Error ? error.message : "请稍后重试"
      })
    }
  }

  const handleToggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedIds(newSelected)
    setIsAllSelected(newSelected.size === filteredMaterials.length && filteredMaterials.length > 0)
  }

  const handleToggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds(new Set())
      setIsAllSelected(false)
    } else {
      const allIds = new Set(filteredMaterials.map(m => m.id))
      setSelectedIds(allIds)
      setIsAllSelected(true)
    }
  }

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return

    const totalCount = selectedIds.size
    const ids = Array.from(selectedIds).map(id => parseInt(id))

    try {
      console.log(`[批量删除] 使用批量删除API删除 ${totalCount} 个素材`)

      // 🚀 使用新的批量删除API - 单次请求完成所有删除
      const response = await fetch(`${backendBaseUrl}/api/v1/files/batch-delete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          file_ids: ids
        })
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`批量删除失败: ${response.status} ${errorText}`)
      }

      const result = await response.json()
      const { success_count, failed_count, failed_ids } = result.data

      console.log(`[批量删除] 完成: 成功=${success_count}, 失败=${failed_count}`, failed_ids)

      if (failed_count === 0) {
        toast({
          title: "批量删除成功",
          description: `已删除 ${success_count} 个素材`
        })
      } else {
        toast({
          variant: "destructive",
          title: "部分删除失败",
          description: `成功: ${success_count}, 失败: ${failed_count}（ID: ${failed_ids.join(', ')}）`
        })
      }

      setSelectedIds(new Set())
      setIsAllSelected(false)
      await refetch()
    } catch (error) {
      console.error('[批量删除] 异常:', error)
      toast({
        variant: "destructive",
        title: "批量删除失败",
        description: error instanceof Error ? error.message : "请稍后重试"
      })
    }
  }

  const handleUpload = async () => {
    if (!filesToUpload.length) return
    const group = (uploadGroup === "none" ? "" : uploadGroup).trim()
    setUploading(true)
    try {
      for (const file of filesToUpload) {
        const formData = new FormData()
        formData.append('file', file)
        if (group) formData.append('group', group)
        await fetch(`/api/files/upload-save`, { method: 'POST', body: formData })
      }
      setFilesToUpload([])
      setUploadGroup("none")
      setShowNewGroup(false)
      setNewGroupName("")
      setUploadDialogOpen(false)
      toast({ variant: 'success', title: '上传成功' })
      await refetch()
    } catch (error) {
      toast({ variant: 'destructive', title: '上传失败' })
    } finally {
      setUploading(false)
    }
  }

  // --- Columns ---
  const columns: ColumnDef<Material>[] = [
    {
      id: "select",
      size: 56,
      header: () => (
        <div className="flex items-center">
          <input
            type="checkbox"
            checked={isAllSelected}
            onChange={handleToggleSelectAll}
            className="h-4 w-4 rounded border-border/80 bg-black text-primary focus:ring-2 focus:ring-primary cursor-pointer"
          />
        </div>
      ),
      cell: ({ row }) => (
        <div className="flex items-center">
          <input
            type="checkbox"
            checked={selectedIds.has(row.original.id)}
            onChange={() => handleToggleSelect(row.original.id)}
            className="h-4 w-4 rounded border-border/80 bg-black text-primary focus:ring-2 focus:ring-primary cursor-pointer"
          />
        </div>
      ),
    },
    {
      accessorKey: "filename",
      header: "文件名",
      size: 420,
      cell: ({ row }) => {
        const hasTitle = !!row.original.title && row.original.title !== row.original.filename
        const primary = (hasTitle ? row.original.title : row.original.filename) ?? ""
        return (
          <div className="flex flex-col gap-0.5 min-w-0">
            <div className="truncate font-medium" title={primary}>
              {hasTitle ? primary : truncateFilename(primary)}
            </div>
            {hasTitle && (
              <div className="text-xs text-muted-foreground truncate" title={row.original.filename}>
                {truncateFilename(row.original.filename)}
              </div>
            )}
          </div>
        )
      },
    },
    {
      accessorKey: "filesize",
      header: "大小",
      size: 110,
      cell: ({ row }) => <span className="text-muted-foreground">{(row.original.filesize || 0).toFixed(2)} MB</span>,
    },
    {
      accessorKey: "duration",
      header: "时长",
      size: 90,
      cell: ({ row }) => <span className="text-muted-foreground">{formatDuration(row.original.duration)}</span>,
    },
    {
      id: "resolution",
      header: "分辨率",
      size: 140,
      cell: ({ row }) => <span className="text-muted-foreground">{formatResolution(row.original)}</span>,
    },
    {
      accessorKey: "uploadTime",
      header: "上传时间",
      size: 140,
      cell: ({ row }) => <span className="text-muted-foreground text-xs">{row.original.uploadTime?.split('T')[0]}</span>,
    },
    {
      accessorKey: "status",
      header: "状态",
      size: 110,
      cell: ({ row }) => (
        <Badge
          variant={row.original.status === "published" ? "secondary" : "default"}
          className="rounded-md text-xs font-normal"
        >
          {row.original.status === "published" ? "已发布" : "待发布"}
        </Badge>
      ),
    },
    {
      accessorKey: "group",
      header: "分组",
      size: 140,
      cell: ({ row }) => (
        row.original.group ? (
          <Badge variant="outline" className="rounded-md text-xs border-border/70 text-foreground/70">
            {row.original.group}
          </Badge>
        ) : <span className="text-xs text-foreground/30">-</span>
      ),
    },
    {
      id: "actions",
      header: () => <div className="text-right">操作</div>,
      size: 200,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" className="h-8 px-2 text-foreground/70 hover:text-foreground" onClick={() => setPreviewMaterial(row.original)}>
            预览
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="h-8 px-3 rounded-lg bg-black hover:bg-accent/60 text-foreground border border-border/40"
            onClick={() => setSelectedMaterial(row.original)}
          >
            <FileText className="h-3.5 w-3.5 mr-1.5" />
            编辑详情
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="icon" variant="ghost" className="h-8 w-8 text-foreground/40 hover:text-white hover:bg-black">
                <Trash2 className="h-4 w-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确认删除？</AlertDialogTitle>
                <AlertDialogDescription>此操作无法撤销。</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction onClick={() => handleDelete(row.original.id)}>删除</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      ),
    },
  ]

  return (
    <div className="mx-auto flex h-full max-w-[1440px] flex-col space-y-5 px-4 py-4 md:px-6 md:py-5">
      <PageHeader
        eyebrow="PRISM / ASSET REGISTRY"
        title="素材管理"
        actions={
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="rounded-xl border-border/70 bg-black hover:bg-accent/50"
              onClick={handleSync}
              disabled={isSyncing}
            >
              <RefreshCw className={cn("mr-2 h-4 w-4", isSyncing && "animate-spin")} />
              {isSyncing ? "同步中..." : "同步文件"}
            </Button>

            <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
              {/* ... dialog content remains same ... */}
              <DialogTrigger asChild>
                <Button className="rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20">
                  <UploadCloud className="mr-2 h-4 w-4" />
                  上传素材
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[80vh] border-border/70 bg-card text-foreground flex flex-col">
                <DialogHeader>
                  <DialogTitle>上传素材</DialogTitle>
                  <DialogDescription>支持批量上传视频文件，自动提取元数据。</DialogDescription>
                </DialogHeader>
                <div className="flex-1 overflow-y-auto py-3 space-y-6 px-1">
                  <FileUpload onChange={setFilesToUpload} />

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium text-foreground/90">分组设置</Label>
                      {!showGroupManager && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                          onClick={() => setShowGroupManager(true)}
                        >
                          管理分组
                        </Button>
                      )}
                    </div>

                    <div className="rounded-xl border border-border/70 bg-card p-4 space-y-4">
                      <div className="flex gap-3">
                        <div className="flex-1 min-w-0">
                          <Select value={uploadGroup} onValueChange={(v) => setUploadGroup(v)}>
                            <SelectTrigger className="h-10 bg-card border-border/70 text-sm focus:ring-0 focus:border-primary/50 transition-colors">
                              <SelectValue placeholder="选择分组..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">无分组</SelectItem>
                              {uploadGroupOptions.map((g) => (
                                <SelectItem key={g} value={g}>{g}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          className="h-10 px-3 bg-black hover:bg-accent/50 text-foreground border border-border/40"
                          onClick={() => setShowNewGroup(v => !v)}
                        >
                          <Plus className={cn("h-4 w-4 transition-transform", showNewGroup ? "rotate-45" : "")} />
                          <span className="ml-2">新建</span>
                        </Button>
                      </div>

                      {showNewGroup && (
                        <div className="flex items-center gap-2 animate-in slide-in-from-top-2 fade-in duration-200">
                          <Input
                            placeholder="输入新分组名称"
                            value={newGroupName}
                            onChange={(e) => setNewGroupName(e.target.value)}
                            className="h-10 bg-card border-border/70 text-sm"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                const name = newGroupName.trim()
                                if (!name) return
                                setLocalGroupOptions((prev) => (prev.includes(name) ? prev : [name, ...prev]))
                                setUploadGroup(name)
                                setShowNewGroup(false)
                                setNewGroupName("")
                              }
                            }}
                          />
                          <Button
                            type="button"
                            className="h-10 px-4 whitespace-nowrap"
                            onClick={() => {
                              const name = newGroupName.trim()
                              if (!name) return
                              setLocalGroupOptions((prev) => (prev.includes(name) ? prev : [name, ...prev]))
                              setUploadGroup(name)
                              setShowNewGroup(false)
                              setNewGroupName("")
                            }}
                          >
                            确认添加
                          </Button>
                        </div>
                      )}

                      {showGroupManager && (
                        <div className="pt-2 border-t border-border/40 space-y-3 animate-in fade-in duration-300">
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-foreground/40">已创建 {uploadGroupOptions.length} 个分组</span>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setShowGroupManager(false)}
                              className="h-6 px-2 text-xs text-foreground/40 hover:text-foreground"
                            >
                              收起
                            </Button>
                          </div>

                          <ScrollArea className="h-[240px] pr-3">
                            <div className="space-y-2">
                              {uploadGroupOptions.length === 0 ? (
                                <div className="text-center py-8 text-foreground/20 text-sm border border-dashed border-border/70 rounded-lg">暂无分组</div>
                              ) : (
                                uploadGroupOptions.map((g) => {
                                  const backendGroup = groupOptions.includes(g)
                                  const isEditing = editingGroup === g
                                  return (
                                    <div
                                      key={g}
                                      className="group flex items-center justify-between p-2 rounded-lg bg-card/20 hover:bg-card/40 border border-border/40 hover:border-border/70 transition-all"
                                    >
                                      {isEditing ? (
                                        <div className="flex items-center gap-2 flex-1 w-full">
                                          <Input
                                            value={editingGroupName}
                                            onChange={(e) => setEditingGroupName(e.target.value)}
                                            className="h-8 text-sm bg-card/40 border-primary/50 focus:border-primary"
                                            autoFocus
                                          />
                                          <Button
                                            size="sm"
                                            className="h-8 w-8 p-0 shrink-0"
                                            disabled={groupActionBusy}
                                            onClick={async () => {
                                              const to = editingGroupName.trim()
                                              const from = g.trim()
                                              if (!to || to === from) {
                                                setEditingGroup(null)
                                                setEditingGroupName("")
                                                return
                                              }
                                              setGroupActionBusy(true)
                                              try {
                                                if (backendGroup) {
                                                  const res = await fetch("/api/files/groups/rename", {
                                                    method: "POST",
                                                    headers: { "Content-Type": "application/json" },
                                                    body: JSON.stringify({ from, to }),
                                                  })
                                                  if (!res.ok) throw new Error(await res.text())
                                                  await refetch()
                                                }
                                                setLocalGroupOptions((prev) => {
                                                  const next = prev.filter((x) => x !== from)
                                                  return next.includes(to) ? next : [to, ...next]
                                                })
                                                setUploadGroup((cur) => (cur === from ? to : cur))
                                              } catch (e) {
                                                toast({ variant: "destructive", title: "失败", description: "重命名失败" })
                                              } finally {
                                                setGroupActionBusy(false)
                                                setEditingGroup(null)
                                                setEditingGroupName("")
                                              }
                                            }}
                                          >
                                            <Sparkles className="h-3.5 w-3.5" />
                                          </Button>
                                          <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-8 w-8 p-0 shrink-0 text-muted-foreground hover:text-foreground"
                                            onClick={() => {
                                              setEditingGroup(null)
                                              setEditingGroupName("")
                                            }}
                                          >
                                            <X className="h-3.5 w-3.5" />
                                          </Button>
                                        </div>
                                      ) : (
                                        <>
                                          <div className="flex items-center gap-2 min-w-0 flex-1">
                                            <span className="text-sm text-foreground/80 truncate font-medium">{g}</span>
                                            {!backendGroup && (
                                              <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-black text-foreground/30 border border-border/40">
                                                本地
                                              </span>
                                            )}
                                          </div>
                                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <Button
                                              type="button"
                                              variant="ghost"
                                              size="icon"
                                              className="h-7 w-7 text-foreground/40 hover:text-foreground hover:bg-accent/50"
                                              onClick={() => {
                                                setEditingGroup(g)
                                                setEditingGroupName(g)
                                              }}
                                            >
                                              <Wand2 className="h-3.5 w-3.5" />
                                            </Button>
                                            <Button
                                              type="button"
                                              variant="ghost"
                                              size="icon"
                                              className="h-7 w-7 text-foreground/40 hover:text-white hover:bg-black"
                                              disabled={groupActionBusy}
                                              onClick={async () => {
                                                if (!confirm(`确认删除分组：${g} ？`)) return
                                                setGroupActionBusy(true)
                                                try {
                                                  if (backendGroup) {
                                                    await fetch("/api/files/groups/delete", {
                                                      method: "POST",
                                                      headers: { "Content-Type": "application/json" },
                                                      body: JSON.stringify({ name: g }),
                                                    })
                                                    await refetch()
                                                  }
                                                  setLocalGroupOptions((prev) => prev.filter((x) => x !== g))
                                                  setUploadGroup((cur) => (cur === g ? "none" : cur))
                                                } catch (e) {
                                                  toast({ variant: "destructive", title: "错误", description: "删除失败" })
                                                } finally {
                                                  setGroupActionBusy(false)
                                                }
                                              }}
                                            >
                                              <Trash2 className="h-3.5 w-3.5" />
                                            </Button>
                                          </div>
                                        </>
                                      )}
                                    </div>
                                  )
                                })
                              )}
                            </div>
                          </ScrollArea>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setUploadDialogOpen(false)}>取消</Button>
                  <Button onClick={handleUpload} disabled={uploading || !filesToUpload.length}>
                    {uploading ? "上传中..." : "开始上传"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {/* Filter Toolbar */}
      <Card className="flex-1 border-border/70 bg-card flex flex-col min-h-0 shadow-none">
        <CardHeader className="flex-shrink-0 border-b border-border/60 pb-4">
          <div className="flex flex-col md:flex-row gap-4 justify-between items-center">
            <div className="flex items-center gap-2 bg-card p-1 rounded-xl border border-border/70">
              <Tabs value={statusFilter} onValueChange={(v) => setStatusFilter(v as any)} className="w-full">
                <TabsList className="h-8 rounded-sm bg-background border border-border/70 backdrop-blur-sm">
                  <TabsTrigger value="all" className="rounded-sm text-xs text-foreground/70 data-[state=active]:bg-foreground/90 data-[state=active]:text-background transition-colors">
                    全部
                  </TabsTrigger>
                  <TabsTrigger value="pending" className="rounded-sm text-xs text-foreground/70 data-[state=active]:bg-foreground/90 data-[state=active]:text-background transition-colors">
                    待发布
                  </TabsTrigger>
                  <TabsTrigger value="published" className="rounded-sm text-xs text-foreground/70 data-[state=active]:bg-foreground/90 data-[state=active]:text-background transition-colors">
                    已发布
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="flex gap-3 w-full md:w-auto items-center">
              <div className="flex items-center gap-2 bg-card border border-border/70 px-2.5 h-8">
                <span className="text-[11px] text-muted-foreground">分组</span>
                <Select value={groupFilter} onValueChange={(v) => setGroupFilter(v)}>
                  <SelectTrigger className="bg-transparent border-0 h-7 px-1.5 text-xs text-foreground/80">
                    <SelectValue placeholder="全部分组" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部分组</SelectItem>
                    {groupOptions.map(g => (
                      <SelectItem key={g} value={g}>{g}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-2 w-full md:w-auto">
                <Input
                  placeholder="搜索素材..."
                  value={keyword}
                  onChange={e => setKeyword(e.target.value)}
                  className="h-8 bg-card border-border/70 min-w-[200px] text-xs"
                />
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 min-h-0 overflow-hidden p-0">
          <ScrollArea className="h-full">
            <div className="p-4 pt-0">
              {selectedIds.size > 0 && (
                <div className="mb-3 flex items-center gap-3 p-2.5 bg-black border border-border">
                  <span className="text-xs text-foreground/80">
                    已选择 {selectedIds.size} 个素材
                  </span>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="destructive" className="ml-auto">
                        <Trash2 className="h-4 w-4 mr-2" />
                        批量删除
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>确认批量删除？</AlertDialogTitle>
                        <AlertDialogDescription>将删除 {selectedIds.size} 个素材，此操作无法撤销。</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>取消</AlertDialogCancel>
                        <AlertDialogAction onClick={handleBatchDelete}>确认删除</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              )}
              <DataTable columns={columns} data={filteredMaterials} pageSize={10} />
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Edit Sheet */}
      <MaterialEditorSheet
        open={!!selectedMaterial}
        onOpenChange={(open) => !open && setSelectedMaterial(null)}
        material={selectedMaterial}
        groupOptions={groupOptions}
        onSave={async (updatedData) => {
          if (!selectedMaterial) return
          try {
            // 检查文件名是否改变
            const filenameChanged = updatedData.filename && updatedData.filename !== selectedMaterial.filename

            // 如果文件名改变，使用重命名 API
            if (filenameChanged) {
              const renameResponse = await fetch(`/api/files/${encodeURIComponent(selectedMaterial.id)}/rename`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  new_filename: updatedData.filename,
                  update_disk_file: updatedData.updateDiskFile !== false // 默认 true
                })
              })

              if (!renameResponse.ok) {
                const errorData = await renameResponse.json().catch(() => ({}))
                throw new Error(errorData.detail || '文件重命名失败')
              }
            }

            // 更新其他元数据
            const response = await fetch(`/api/files/${encodeURIComponent(selectedMaterial.id)}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                title: updatedData.title,
                description: updatedData.description,
                tags: updatedData.tags,
                note: updatedData.note,
                group_name: updatedData.group === 'none' ? null : updatedData.group,
                cover_image: updatedData.cover_image
              })
            })
            if (!response.ok) throw new Error('update failed')

            toast({
              variant: 'success',
              title: '已保存',
              description: filenameChanged ? '素材信息和文件名已更新' : '素材信息已更新'
            })
            setSelectedMaterial(null)
            await refetch()
          } catch (error: any) {
            toast({
              variant: 'destructive',
              title: '保存失败',
              description: error.message || '请稍后重试'
            })
          }
        }}
      />

      {/* Preview Dialog */}
      <Dialog open={!!previewMaterial} onOpenChange={(open) => !open && setPreviewMaterial(null)}>
        <DialogContent className="max-w-[820px] w-[820px] h-auto bg-card border-border p-0 overflow-hidden gap-0">
          <DialogHeader className="sr-only">
            <DialogTitle>素材预览</DialogTitle>
          </DialogHeader>
          {previewMaterial && (
            <div className="relative w-full h-full flex items-center justify-center bg-card">
              {(() => {
                const previewSrc = getPreviewUrl(previewMaterial)
                if (isImageFile(previewMaterial.filename)) {
                  return (
                    <img
                      src={previewSrc}
                      alt={previewMaterial.title || previewMaterial.filename}
                      className="block max-w-full max-h-[80vh] object-contain bg-card shadow-2xl"
                    />
                  )
                }
                return (
                  <video
                    key={previewSrc}
                    src={previewSrc}
                    controls
                    className="w-full max-h-[80vh] object-contain bg-card block shadow-2xl"
                    autoPlay
                  />
                )
              })()}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default function MaterialsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading...</div>}>
      <MaterialsPageContent />
    </Suspense>
  )
}
