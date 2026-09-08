"use client"

/**
 * B站分P（多P）发布页（/publish/bilibili）
 * 一个稿件 = 多个视频分P（P1..Pn 顺序上传，单稿件单账号）。
 * 与矩阵页不同：矩阵"每个素材一个稿件"；这里全部选中的视频合并为一个稿件。
 *
 * 提交语义：file_ids=[P1 素材 id] + platform_settings.bilibili.video_parts
 * = [{path: P2..Pn 的 file_path, title?}]，经 /api/v1/publish/batch 建单任务，
 * batch 任务执行时按 video_parts 合并分P（见 batch_publish_service bili_parts 分支）。
 */
import { useMemo, useState } from "react"
import Image from "next/image"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Send,
  Loader2,
  Plus,
  Search,
  X,
  ArrowLeft,
  ArrowRight,
  CalendarClock,
  AlertTriangle,
  Layers,
  Film,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/components/ui/use-toast"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import { backendBaseUrl } from "@/lib/env"
import type { Material } from "@/lib/mock-data"
import { PageHeader } from "@/components/layout/page-scaffold"
import { useVisiblePlatforms } from "@/hooks/use-visible-platforms"

function toBackendFileUrl(raw?: string): string {
  if (!raw) return ""
  if (raw.startsWith("http")) return raw
  if (raw.startsWith("/getFile")) return `${backendBaseUrl}${raw}`
  return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
}

interface BiliPlan {
  accountId: string | null // B站账号
  partIds: string[] // 视频素材 id，顺序即 P1..Pn
  title: string // 稿件主标题
  description: string // 简介
  tags: string
  tid: number // 分区 id
  category: string // 分区名（展示）
  copyright: 1 | 2
  source: string // 转载来源
  cover: string // 封面 URL 或本地路径
  dynamic: string // 粉丝动态
  scheduled: boolean
  scheduleDate?: string
  scheduleTime?: string
}

const BILI_CATEGORIES: { label: string; tid: number }[] = [
  { label: "生活", tid: 160 },
  { label: "游戏", tid: 17 },
  { label: "娱乐", tid: 71 },
  { label: "知识", tid: 207 },
  { label: "科技", tid: 188 },
  { label: "音乐", tid: 3 },
  { label: "舞蹈", tid: 129 },
  { label: "影视", tid: 181 },
]

export default function BilibiliMultipartPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { isVisible } = useVisiblePlatforms()

  const { data: materialsData } = useQuery({
    queryKey: ["materials"],
    queryFn: () => fetch("/api/materials").then((r) => r.json()),
  })
  const { data: accountsData } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => fetch("/api/accounts?limit=1000").then((r) => r.json()),
  })

  const videoMaterials = useMemo(() => {
    const list = Array.isArray((materialsData as any)?.data?.data)
      ? (materialsData as any).data.data
      : Array.isArray((materialsData as any)?.data)
        ? (materialsData as any).data
        : []
    return (list as Material[]).filter((m) => m.type === "video" || /\.(mp4|mov|avi|flv|mkv|wmv)$/i.test(m.filename || ""))
  }, [materialsData])

  const biliAccounts = useMemo(() => {
    const list = Array.isArray((accountsData as any)?.data)
      ? (accountsData as any).data
      : Array.isArray((accountsData as any)?.items)
        ? (accountsData as any).items
        : []
    return (list as any[]).filter((a) => a.platform === "bilibili" && isVisible("bilibili"))
  }, [accountsData, isVisible])

  const [plan, setPlan] = useState<BiliPlan>({
    accountId: null,
    partIds: [],
    title: "",
    description: "",
    tags: "",
    tid: 160,
    category: "生活",
    copyright: 1,
    source: "",
    cover: "",
    dynamic: "",
    scheduled: false,
  })

  const [pickerOpen, setPickerOpen] = useState(false)
  const [keyword, setKeyword] = useState("")

  const patch = (p: Partial<BiliPlan>) => setPlan((prev) => ({ ...prev, ...p }))

  const filteredVideos = useMemo(() => {
    if (!keyword.trim()) return videoMaterials
    const kw = keyword.toLowerCase()
    return videoMaterials.filter((m) => m.filename.toLowerCase().includes(kw))
  }, [videoMaterials, keyword])

  const selectedParts = useMemo(() => {
    const byId = new Map(videoMaterials.map((m) => [String(m.id), m]))
    return plan.partIds.map((id) => byId.get(id)).filter(Boolean) as Material[]
  }, [videoMaterials, plan.partIds])

  const togglePart = (id: string) => {
    const on = plan.partIds.includes(id)
    if (on) {
      // 取消时把该 id 从列表移除（其余保序）
      patch({ partIds: plan.partIds.filter((x) => x !== id) })
    } else {
      patch({ partIds: [...plan.partIds, id] })
    }
  }

  const movePart = (index: number, dir: -1 | 1) => {
    const next = [...plan.partIds]
    const target = index + dir
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    patch({ partIds: next })
  }

  const removePart = (id: string) => patch({ partIds: plan.partIds.filter((x) => x !== id) })

  const selectCategory = (label: string) => {
    const found = BILI_CATEGORIES.find((c) => c.label === label)
    patch({ category: label, tid: found ? found.tid : plan.tid })
  }

  const publishMutation = useMutation({
    mutationFn: async () => {
      if (!plan.accountId) throw new Error("请选择 B站 账号")
      if (plan.partIds.length < 2) throw new Error("分P发布至少需要 2 个视频（P1 + P2..Pn）")
      if (!plan.title.trim()) throw new Error("请填写稿件标题")

      // P1 = file_ids 主素材；P2..Pn = video_parts（取素材 file_path）
      const byId = new Map(videoMaterials.map((m) => [String(m.id), m]))
      const p1 = byId.get(plan.partIds[0])
      const restIds = plan.partIds.slice(1)
      const parts: { path: string; title?: string }[] = []
      for (const id of restIds) {
        const m = byId.get(id)
        if (!m) continue
        const path = (m as any).storageKey || (m as any).file_path || ""
        if (path) parts.push({ path, title: m.filename })
      }
      if (parts.length !== restIds.length) {
        throw new Error("部分分P素材缺少后端路径（storageKey/file_path），无法提交")
      }

      let scheduledTime: string | undefined
      if (plan.scheduled && plan.scheduleDate && plan.scheduleTime) {
        scheduledTime = `${plan.scheduleDate} ${plan.scheduleTime}`
      }

      const platform_settings = {
        bilibili: {
          contentKind: "video",
          video_parts: parts,
          tid: plan.tid,
          copyright: plan.copyright,
          source: plan.source || undefined,
          dynamic: plan.dynamic || undefined,
          cover: plan.cover || undefined,
        },
      }

      const payload = {
        file_ids: [Number(plan.partIds[0])],
        accounts: [plan.accountId],
        platform: 5,
        title: plan.title.trim(),
        description: plan.description.trim() || undefined,
        topics: plan.tags
          .split(/[#\s,，]+/)
          .map((t) => t.trim())
          .filter(Boolean),
        scheduled_time: scheduledTime,
        platform_settings,
      }

      const res = await fetch("/api/publish/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data?.success === false) {
        throw new Error(data?.detail || data?.msg || data?.message || `提交失败 (HTTP ${res.status})`)
      }
      return data
    },
    onSuccess: (data: any) => {
      const d = data?.data || data
      const batchId = d?.batch_id || ""
      toast({
        title: "分P稿件任务已提交",
        description: `P1..P${plan.partIds.length} 共 ${plan.partIds.length} 个分P · ${plan.title}${batchId ? `（批次 ${batchId}）` : ""}`,
      })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
    onError: (error: any) => {
      toast({ title: "提交失败", description: error?.message || "请稍后再试", variant: "destructive" })
    },
  })

  const canSubmit =
    Boolean(plan.accountId) &&
    plan.partIds.length >= 2 &&
    plan.title.trim().length > 0 &&
    !publishMutation.isPending

  return (
    <div className="space-y-6 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="B站分P发布"
        description={"一个稿件包含多个视频（P1..Pn 顺序上传），与矩阵「每素材一稿」不同"}
        actions={
          <Button
            onClick={() => publishMutation.mutate()}
            disabled={!canSubmit}
          >
            {publishMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Send className="w-4 h-4 mr-2" />
            )}
            {publishMutation.isPending ? "提交中..." : "提交分P稿件"}
          </Button>
        }
      />

      {/* 1. 账号 */}
      <section className="space-y-3">
        <Label className="text-base font-medium flex items-center gap-2">
          1. 选择账号
          <span className="text-[11px] text-muted-foreground">B站 · 分P稿件一次发到一个账号</span>
        </Label>
        {biliAccounts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-card/30 p-6 text-center text-sm text-muted-foreground">
            <AlertTriangle className="w-5 h-5 mx-auto mb-2 text-yellow-500/70" />
            暂无 B站 账号，请先到
            <a href="/account" className="text-primary underline mx-1">账号管理</a>
            添加/登录
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {biliAccounts.map((account: any) => {
              const isSelected = plan.accountId === String(account.id)
              return (
                <button
                  key={String(account.id)}
                  onClick={() => patch({ accountId: isSelected ? null : String(account.id) })}
                  className={cn(
                    "flex items-center gap-2.5 p-2.5 rounded-xl border text-left transition-all",
                    isSelected ? "border-primary bg-black ring-1 ring-primary" : "border-border/70 bg-card/40 hover:bg-accent/50"
                  )}
                >
                  <div className="w-7 h-7 relative shrink-0">
                    <Image
                      src={(account as any).avatar || ""}
                      alt={account.name || ""}
                      width={28}
                      height={28}
                      className="rounded-full object-cover bg-muted"
                      unoptimized
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-foreground truncate">{account.name}</p>
                    <p className="text-[10px] text-muted-foreground truncate">B站</p>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </section>

      {/* 2. 分P视频列表 */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-base font-medium flex items-center gap-2">
            <Layers className="w-4 h-4" />
            2. 分P视频（P1..Pn，顺序即分P顺序）
            <span className="text-[11px] text-muted-foreground">
              已选 {plan.partIds.length} 个视频
            </span>
          </Label>
          <Button variant="outline" size="sm" className="h-8 border-border/70 bg-black hover:bg-accent/50 text-foreground" onClick={() => setPickerOpen(true)}>
            <Plus className="w-3 h-3 mr-2" />
            添加视频
          </Button>
        </div>

        {selectedParts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-card/30 p-8 text-center">
            <Film className="w-8 h-8 mx-auto mb-2 text-foreground/25" />
            <p className="text-sm text-muted-foreground">还没有选择视频。点右上角「添加视频」从素材库选取（至少 2 个）。</p>
          </div>
        ) : (
          <div className="rounded-2xl border border-border/70 bg-card p-4 space-y-2">
            {selectedParts.map((m, index) => (
              <div key={String(m.id)} className="flex items-center gap-3 rounded-xl border border-border/70 bg-black/40 p-2.5">
                <div className="relative w-16 h-10 rounded-md overflow-hidden bg-black shrink-0">
                  {m.fileUrl || (m as any).storageKey || (m as any).file_path ? (
                    <Image
                      src={toBackendFileUrl((m as any).fileUrl || (m as any).storageKey || (m as any).file_path)}
                      alt={m.filename}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                  ) : null}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] shrink-0 border-primary/50 text-primary">P{index + 1}</Badge>
                    <span className="text-sm font-medium text-foreground truncate">{m.filename}</span>
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate mt-0.5">
                    {(m as any).title || m.description || m.note || (m as any).storageKey || (m as any).file_path || ""}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    className="w-7 h-7 rounded-lg border border-border/70 flex items-center justify-center hover:bg-accent/50 disabled:opacity-30"
                    onClick={() => movePart(index, -1)}
                    disabled={index === 0}
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                  </button>
                  <button
                    className="w-7 h-7 rounded-lg border border-border/70 flex items-center justify-center hover:bg-accent/50 disabled:opacity-30"
                    onClick={() => movePart(index, 1)}
                    disabled={index === selectedParts.length - 1}
                  >
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                  <button
                    className="w-7 h-7 rounded-lg border border-border/70 flex items-center justify-center hover:bg-red-500/20 hover:text-red-400"
                    onClick={() => removePart(String(m.id))}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
            <p className="text-[11px] text-foreground/40 px-1 pt-1">
              P1 为稿件主视频（按素材库路径解析），P2..Pn 经 platform_settings.bilibili.video_parts 按顺序合并进同一稿件。
            </p>
          </div>
        )}
      </section>

      {/* 3. 稿件配置 */}
      <section className="space-y-3">
        <Label className="text-base font-medium">3. 稿件配置</Label>
        <div className="rounded-2xl border border-border/70 bg-card p-6 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">稿件主标题 *</Label>
            <Input value={plan.title} onChange={(e) => patch({ title: e.target.value })} placeholder="主标题（P2..Pn 缺省时用 主标题+P序号）" />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">简介</Label>
            <Textarea value={plan.description} onChange={(e) => patch({ description: e.target.value })} rows={3} placeholder="稿件简介（可选）" />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">标签</Label>
            <Input value={plan.tags} onChange={(e) => patch({ tags: e.target.value })} placeholder="多个标签用空格或 # 分隔" />
          </div>

          {/* 分区 */}
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">分区</Label>
            <div className="flex flex-wrap gap-2">
              {BILI_CATEGORIES.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  aria-pressed={plan.category === option.label}
                  onClick={() => selectCategory(option.label)}
                  className={cn(
                    "cursor-pointer border px-3 py-1 text-xs transition-colors",
                    plan.category === option.label
                      ? "border-foreground bg-foreground text-background"
                      : "border-border/70 bg-black text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-foreground/40">当前 tid：{plan.tid}</p>
          </div>

          {/* 版权 */}
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">版权</Label>
            <div className="flex gap-2">
              {([{ v: 1 as const, label: "自制" }, { v: 2 as const, label: "转载" }]).map((opt) => (
                <button
                  key={opt.v}
                  type="button"
                  aria-pressed={plan.copyright === opt.v}
                  onClick={() => patch({ copyright: opt.v })}
                  className={cn(
                    "cursor-pointer border px-3 py-1 text-xs transition-colors",
                    plan.copyright === opt.v
                      ? "border-foreground bg-foreground text-background"
                      : "border-border/70 bg-black text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {plan.copyright === 2 && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">转载来源</Label>
              <Input value={plan.source} onChange={(e) => patch({ source: e.target.value })} placeholder="原作品来源（转载时建议填写）" className="bg-card/20 border-border/70 text-xs" />
            </div>
          )}

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">封面</Label>
            <Input value={plan.cover} onChange={(e) => patch({ cover: e.target.value })} placeholder="封面 URL 或本地图片路径（可选，缺省用视频首帧）" className="bg-card/20 border-border/70 text-xs" />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">粉丝动态</Label>
            <Input value={plan.dynamic} onChange={(e) => patch({ dynamic: e.target.value })} placeholder="发布时同步到粉丝动态的文案（可选）" className="bg-card/20 border-border/70 text-xs" />
          </div>

          {/* 定时 */}
          <div className="flex items-center justify-between rounded-xl border border-border/70 p-4">
            <div className="flex items-center gap-3">
              <CalendarClock className="w-4 h-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-foreground">定时发布</p>
                <p className="text-[11px] text-muted-foreground">需晚于当前 2 小时且在 15 天内</p>
              </div>
            </div>
            <Switch
              checked={plan.scheduled}
              onCheckedChange={(v) => {
                if (!v) {
                  patch({ scheduled: false, scheduleDate: undefined, scheduleTime: undefined })
                  return
                }
                const now = new Date()
                const rounded = new Date(now)
                rounded.setMinutes(rounded.getMinutes() + 120, 0, 0)
                patch({
                  scheduled: true,
                  scheduleDate: now.toISOString().split("T")[0],
                  scheduleTime: `${String(rounded.getHours()).padStart(2, "0")}:${String(rounded.getMinutes()).padStart(2, "0")}`,
                })
              }}
            />
          </div>
          {plan.scheduled && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">日期</Label>
                <Input type="date" value={plan.scheduleDate || ""} onChange={(e) => patch({ scheduleDate: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">时间</Label>
                <Input type="time" value={plan.scheduleTime || ""} onChange={(e) => patch({ scheduleTime: e.target.value })} />
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 素材选择弹窗 */}
      {pickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setPickerOpen(false)} />
          <div className="relative w-full max-w-3xl bg-card border border-border/70 rounded-2xl p-6 max-h-[85vh] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-foreground">选择视频素材（已选 {plan.partIds.length}，顺序 = 添加顺序）</h3>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => setPickerOpen(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input className="pl-9" placeholder="搜索视频文件名…" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
            </div>
            <div className="grid grid-cols-3 md:grid-cols-5 gap-3 overflow-y-auto pr-1 pb-2">
              {filteredVideos.length === 0 && (
                <p className="col-span-full text-center text-sm text-muted-foreground py-10">
                  没有找到视频素材。请先到
                  <a href="/materials" className="text-primary underline mx-1">素材管理</a>
                  上传视频。
                </p>
              )}
              {filteredVideos.map((m) => {
                const idx = plan.partIds.indexOf(String(m.id))
                const isSelected = idx >= 0
                return (
                  <button
                    key={String(m.id)}
                    onClick={() => togglePart(String(m.id))}
                    className={cn(
                      "relative rounded-xl overflow-hidden border bg-black aspect-video transition-all",
                      isSelected ? "border-primary ring-2 ring-primary" : "border-border/70 hover:border-border"
                    )}
                  >
                    {m.fileUrl || (m as any).storageKey || (m as any).file_path ? (
                      <Image
                        src={toBackendFileUrl((m as any).fileUrl || (m as any).storageKey || (m as any).file_path)}
                        alt={m.filename}
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center text-foreground/20">
                        <Film className="w-8 h-8" />
                      </div>
                    )}
                    {isSelected && (
                      <span className="absolute top-1 right-1 w-5 h-5 rounded-full bg-primary flex items-center justify-center text-[10px] text-primary-foreground font-bold">
                        {idx + 1}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
            <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-border/70">
              <Button variant="outline" className="border-border/70" onClick={() => setPickerOpen(false)}>
                取消
              </Button>
              <Button onClick={() => setPickerOpen(false)} disabled={plan.partIds.length === 0}>
                确定（{plan.partIds.length} 个视频）
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
