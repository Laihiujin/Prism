"use client"

/**
 * 图文发布页（/publish/note）
 * 一组图片 = 一条图文/笔记，支持 多平台(抖音/小红书/快手) × 各平台多账号，
 * 每个平台按账号生成 1 个图文任务（与矩阵"每素材一任务"不同）。
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
  ImagePlus,
  ArrowLeft,
  ArrowRight,
  CalendarClock,
  AlertTriangle,
  Check,
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
import { DouyinConfig, XhsConfig, KuaishouConfig } from "../components/PlatformConfigs"
import { PLATFORMS } from "../components/PlatformSelector"

// 图文仅支持抖音(3)/小红书(1)/快手(4)
const NOTE_PLATFORM_KEYS = ["douyin", "xiaohongshu", "kuaishou"] as const
type NotePlatformKey = typeof NOTE_PLATFORM_KEYS[number]

const PLATFORM_CODE: Record<NotePlatformKey, number> = {
  douyin: 3,
  xiaohongshu: 1,
  kuaishou: 4,
}

const platformMeta = (key: string) => PLATFORMS.find((p) => p.key === key)

function toBackendFileUrl(raw?: string): string {
  if (!raw) return ""
  if (raw.startsWith("http")) return raw
  if (raw.startsWith("/getFile")) return `${backendBaseUrl}${raw}`
  return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
}

interface NotePlan {
  platforms: NotePlatformKey[] // 多平台
  accountsByPlatform: Record<NotePlatformKey, string[]> // 每平台选中的账号
  imageIds: string[] // 顺序即图序
  title: string
  description: string
  tags: string
  scheduled: boolean
  scheduleDate?: string
  scheduleTime?: string
  platformSettings: Record<string, any>
}

export default function NotePublishPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { isVisible } = useVisiblePlatforms()

  // 素材（图片）与账号
  const { data: materialsData } = useQuery({
    queryKey: ["materials"],
    queryFn: () =>
      fetch("/api/materials").then((r) => r.json()),
  })
  const { data: accountsData } = useQuery({
    queryKey: ["accounts"],
    queryFn: () =>
      fetch("/api/accounts?limit=1000").then((r) => r.json()),
  })

  const imageMaterials = useMemo(() => {
    const list = Array.isArray((materialsData as any)?.data?.data)
      ? (materialsData as any).data.data
      : Array.isArray((materialsData as any)?.data)
        ? (materialsData as any).data
        : []
    return (list as Material[]).filter(
      (m) => m.type === "image" || /\.(jpe?g|png|gif|webp|bmp|avif|heic|heif)$/i.test(m.filename || "")
    )
  }, [materialsData])

  const accounts = useMemo(() => {
    const list = Array.isArray((accountsData as any)?.data)
      ? (accountsData as any).data
      : Array.isArray((accountsData as any)?.items)
        ? (accountsData as any).items
        : []
    return (list as any[]).filter((a) => isVisible(a.platform))
  }, [accountsData, isVisible])

  const [plan, setPlan] = useState<NotePlan>({
    platforms: [],
    accountsByPlatform: { douyin: [], xiaohongshu: [], kuaishou: [] },
    imageIds: [],
    title: "",
    description: "",
    tags: "",
    scheduled: false,
    platformSettings: {},
  })

  const [pickerOpen, setPickerOpen] = useState(false)
  const [keyword, setKeyword] = useState("")

  const patch = (p: Partial<NotePlan>) => setPlan((prev) => ({ ...prev, ...p }))

  const visibleNotePlatforms = useMemo(
    () => NOTE_PLATFORM_KEYS.filter((key) => isVisible(key)),
    [isVisible]
  )

  // 平台多选
  const togglePlatform = (key: NotePlatformKey) => {
    const on = plan.platforms.includes(key)
    patch({
      platforms: on ? plan.platforms.filter((k) => k !== key) : [...plan.platforms, key],
    })
  }

  // 每平台独立账号勾选
  const toggleAccount = (platform: NotePlatformKey, accountId: string) => {
    const current = plan.accountsByPlatform[platform] || []
    const next = current.includes(accountId)
      ? current.filter((x) => x !== accountId)
      : [...current, accountId]
    patch({
      accountsByPlatform: { ...plan.accountsByPlatform, [platform]: next },
    })
  }

  const selectAllAccountsOf = (platform: NotePlatformKey) => {
    const avail = accounts.filter((a: any) => a.platform === platform).map((a: any) => String(a.id))
    patch({
      accountsByPlatform: { ...plan.accountsByPlatform, [platform]: avail },
    })
  }

  const accountsByPlatformFor = (platform: NotePlatformKey) =>
    accounts.filter((a: any) => a.platform === platform)

  const filteredImages = useMemo(() => {
    if (!keyword.trim()) return imageMaterials
    const kw = keyword.toLowerCase()
    return imageMaterials.filter((m) => m.filename.toLowerCase().includes(kw))
  }, [imageMaterials, keyword])

  const selectedImages = useMemo(() => {
    const byId = new Map(imageMaterials.map((m) => [String(m.id), m]))
    return plan.imageIds.map((id) => byId.get(id)).filter(Boolean) as Material[]
  }, [imageMaterials, plan.imageIds])

  const toggleImage = (id: string) => {
    patch({
      imageIds: plan.imageIds.includes(id)
        ? plan.imageIds.filter((x) => x !== id)
        : [...plan.imageIds, id],
    })
  }

  const moveImage = (index: number, dir: -1 | 1) => {
    const next = [...plan.imageIds]
    const target = index + dir
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    patch({ imageIds: next })
  }

  // 提交：每个已选平台（且有账号）发一次 /api/publish/note
  const publishMutation = useMutation({
    mutationFn: async () => {
      if (plan.platforms.length === 0) throw new Error("请至少选择 1 个平台")
      if (plan.imageIds.length === 0) throw new Error("请至少选择 1 张图片")
      if (!plan.title.trim()) throw new Error("请填写图文标题")
      if (plan.imageIds.length > 18) throw new Error("单篇图文最多 18 张图片")

      const activePlatforms = plan.platforms.filter(
        (k) => (plan.accountsByPlatform[k] || []).length > 0
      )
      if (activePlatforms.length === 0) throw new Error("请至少为 1 个平台选择账号")

      const ps = plan.platformSettings || {}
      const platformSettings: Record<string, any> = {}
      const keys = ["douyin", "xiaohongshu", "kuaishou"]
      for (const k of keys) {
        if (ps[k] && Object.keys(ps[k]).length > 0) platformSettings[k] = ps[k]
      }

      let scheduledTime: string | undefined
      if (plan.scheduled && plan.scheduleDate && plan.scheduleTime) {
        scheduledTime = `${plan.scheduleDate} ${plan.scheduleTime}`
      }

      const results: { platform: string; success_count: number; failed_count: number }[] = []
      const errors: string[] = []

      for (const platformKey of activePlatforms) {
        const accounts = plan.accountsByPlatform[platformKey] || []
        if (accounts.length === 0) continue
        const payload = {
          platform: PLATFORM_CODE[platformKey],
          accounts,
          image_ids: plan.imageIds.map(Number),
          title: plan.title.trim(),
          description: plan.description.trim() || undefined,
          topics: plan.tags
            .split(/[#\s,，]+/)
            .map((t) => t.trim())
            .filter(Boolean),
          scheduled_time: scheduledTime,
          platform_settings: platformSettings,
        }
        const res = await fetch("/api/publish/note", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok || data?.success === false) {
          errors.push(`${platformMeta(platformKey)?.name}: ${data?.detail || data?.msg || data?.message || `HTTP ${res.status}`}`)
          continue
        }
        const d = data?.data || data
        results.push({
          platform: platformMeta(platformKey)?.name || platformKey,
          success_count: d?.success_count ?? 0,
          failed_count: d?.failed_count ?? 0,
        })
      }

      if (results.length === 0) {
        throw new Error(errors[0] || "没有平台提交成功")
      }
      return { results, errors }
    },
    onSuccess: (data: any) => {
      const summary = data.results
        .map((r: any) => `${r.platform} +${r.success_count}`)
        .join("  ")
      toast({
        title: "图文任务已提交",
        description: summary + (data.errors?.length ? ` · ${data.errors.length} 个平台失败` : ""),
      })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
    onError: (error: any) => {
      toast({ title: "发布失败", description: error?.message || "请稍后再试", variant: "destructive" })
    },
  })

  const commonProps = {
    data: plan,
    onChange: (newData: any) => setPlan((prev) => ({ ...prev, ...newData })),
  }

  const totalSelectedAccounts = Object.values(plan.accountsByPlatform).reduce(
    (n, ids) => n + ids.length,
    0
  )

  const canSubmit =
    plan.platforms.length > 0 &&
    plan.imageIds.length > 0 &&
    totalSelectedAccounts > 0 &&
    plan.title.trim().length > 0

  return (
    <div className="space-y-6 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="图文发布"
        description="一组图片 = 一条图文/笔记（抖音/小红书/快手，可多平台同时分发）"
        actions={
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="border-border/70 bg-black hover:bg-accent/50 text-foreground"
              onClick={() =>
                patch({
                  platforms: [],
                  accountsByPlatform: { douyin: [], xiaohongshu: [], kuaishou: [] },
                  imageIds: [],
                  title: "",
                  description: "",
                  tags: "",
                })
              }
              disabled={publishMutation.isPending}
            >
              <X className="w-4 h-4 mr-2" />
              清空
            </Button>
            <Button
              onClick={() => publishMutation.mutate()}
              disabled={!canSubmit || publishMutation.isPending}
            >
              {publishMutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Send className="w-4 h-4 mr-2" />
              )}
              {publishMutation.isPending ? "提交中..." : "发布图文"}
            </Button>
          </div>
        }
      />

      {/* 1. 平台多选（图文能力平台） */}
      <section className="space-y-3">
        <Label className="text-base font-medium flex items-center gap-2">
          <span className="text-foreground">1. 选择平台（可多选）</span>
          <span className="text-[11px] text-muted-foreground">
            已选 {plan.platforms.length} 个平台 · 图文仅支持 抖音 / 小红书 / 快手
          </span>
        </Label>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {visibleNotePlatforms.map((key) => {
            const meta = platformMeta(key)
            if (!meta) return null
            const isSelected = plan.platforms.includes(key)
            return (
              <button
                key={key}
                onClick={() => togglePlatform(key)}
                className={cn(
                  "relative flex items-center gap-3 p-4 rounded-xl border text-left transition-all group",
                  isSelected
                    ? "border-primary bg-black ring-1 ring-primary"
                    : "border-border/70 bg-card hover:bg-accent/50 hover:border-border/80"
                )}
              >
                {isSelected && (
                  <span className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                    <Check className="w-3 h-3 text-primary-foreground" />
                  </span>
                )}
                <div className="w-10 h-10 relative shrink-0 transition-transform group-hover:scale-110">
                  <Image src={meta.icon} alt={meta.name} fill className="object-contain" />
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-sm text-foreground">{meta.name}</div>
                  <div className="text-[10px] text-muted-foreground truncate">图文/笔记</div>
                </div>
              </button>
            )
          })}
        </div>
      </section>

      {/* 2. 图片组（多图 = 一条） */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-base font-medium flex items-center gap-2">
            2. 图片（多图 = 一条图文）
            <span className="text-[11px] text-muted-foreground">
              已选 {plan.imageIds.length}/18 张，排序即发布顺序
            </span>
          </Label>
          <Button variant="outline" size="sm" className="h-8 border-border/70 bg-black hover:bg-accent/50 text-foreground" onClick={() => setPickerOpen(true)}>
            <Plus className="w-3 h-3 mr-2" />
            添加图片
          </Button>
        </div>

        {selectedImages.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-card/30 p-8 text-center">
            <ImagePlus className="w-8 h-8 mx-auto mb-2 text-foreground/25" />
            <p className="text-sm text-muted-foreground">还没有选择图片素材。点右上角「添加图片」从素材库选取（支持多选）。</p>
          </div>
        ) : (
          <div className="rounded-2xl border border-border/70 bg-card p-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {selectedImages.map((m, index) => (
                <div key={String(m.id)} className="relative group rounded-xl overflow-hidden border border-border/70 bg-black aspect-[3/4]">
                  <Image
                    src={toBackendFileUrl((m as any).fileUrl || (m as any).storageKey || (m as any).file_path)}
                    alt={m.filename}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                  <div className="absolute top-1 left-1 w-5 h-5 rounded-full bg-black/70 backdrop-blur text-[11px] flex items-center justify-center text-white z-10">
                    {index + 1}
                  </div>
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors" />
                  <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                    <button
                      className="w-6 h-6 rounded-full bg-black/70 backdrop-blur flex items-center justify-center hover:bg-black"
                      onClick={() => moveImage(index, -1)}
                      disabled={index === 0}
                    >
                      <ArrowLeft className="w-3 h-3 text-white" />
                    </button>
                    <button
                      className="w-6 h-6 rounded-full bg-black/70 backdrop-blur flex items-center justify-center hover:bg-black"
                      onClick={() => moveImage(index, 1)}
                      disabled={index === selectedImages.length - 1}
                    >
                      <ArrowRight className="w-3 h-3 text-white" />
                    </button>
                  </div>
                  <button
                    className="absolute bottom-1 right-1 w-6 h-6 rounded-full bg-red-500/80 backdrop-blur flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 hover:bg-red-500"
                    onClick={() => toggleImage(String(m.id))}
                  >
                    <X className="w-3 h-3 text-white" />
                  </button>
                  <p className="absolute bottom-0 inset-x-0 px-1.5 py-0.5 text-[9px] text-white/80 bg-black/60 truncate">
                    {m.filename}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 3. 账号选择（按已选平台分组） */}
      <section className="space-y-3">
        <Label className="text-base font-medium flex items-center gap-2">
          3. 选择账号（按平台分组）
          <span className="text-[11px] text-muted-foreground">
            共选 {totalSelectedAccounts} 个账号{plan.platforms.length === 0 ? " · 先选择平台" : ""}
          </span>
        </Label>
        {plan.platforms.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-card/30 p-6 text-center text-sm text-muted-foreground">
            请先选择平台（抖音 / 小红书 / 快手）
          </div>
        ) : (
          <div className="space-y-4">
            {plan.platforms.map((key) => {
              const meta = platformMeta(key)
              const platformAccounts = accountsByPlatformFor(key)
              const selectedCount = (plan.accountsByPlatform[key] || []).length
              return (
                <div key={key} className="rounded-2xl border border-border/70 bg-card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {meta?.icon && (
                        <div className="w-6 h-6 relative">
                          <Image src={meta.icon} alt={meta.name || key} fill className="object-contain" />
                        </div>
                      )}
                      <span className="text-sm font-medium text-foreground">{meta?.name}</span>
                      <Badge variant="outline" className="text-[10px] border-border text-muted-foreground">
                        {platformAccounts.length} 个可用账号
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] text-foreground/50">已选 {selectedCount}</span>
                      {platformAccounts.length > 0 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-[11px] text-muted-foreground hover:text-foreground"
                          onClick={() => selectAllAccountsOf(key)}
                        >
                          全选
                        </Button>
                      )}
                    </div>
                  </div>

                  {platformAccounts.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-border/70 bg-card/30 p-4 text-center text-xs text-muted-foreground">
                      <AlertTriangle className="w-4 h-4 mx-auto mb-1 text-yellow-500/70" />
                      该平台暂无可用账号，请先到
                      <a href="/account" className="text-primary underline mx-1">账号管理</a>
                      添加/登录
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                      {platformAccounts.map((account: any) => {
                        const isSelected = (plan.accountsByPlatform[key] || []).includes(String(account.id))
                        return (
                          <button
                            key={String(account.id)}
                            onClick={() => toggleAccount(key, String(account.id))}
                            className={cn(
                              "flex items-center gap-2.5 p-2.5 rounded-xl border text-left transition-all",
                              isSelected
                                ? "border-primary bg-black ring-1 ring-primary"
                                : "border-border/70 bg-card/40 hover:bg-accent/50"
                            )}
                          >
                            <div className="w-7 h-7 relative shrink-0">
                              <Image
                                src={(account as any).avatar || (meta?.icon ?? "/douYin.svg")}
                                alt={account.name || ""}
                                width={28}
                                height={28}
                                className="rounded-full object-cover"
                                unoptimized
                              />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-xs font-medium text-foreground truncate">{account.name}</p>
                              <p className="text-[10px] text-muted-foreground truncate">{meta?.name || account.platform}</p>
                            </div>
                            {isSelected && <Check className="w-3.5 h-3.5 text-primary shrink-0" />}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* 4. 内容编辑 */}
      <section className="space-y-3">
        <Label className="text-base font-medium">4. 内容编辑</Label>
        <div className="rounded-2xl border border-border/70 bg-card p-6 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">图文标题 *（抖音最多 20 字）</Label>
            <Input
              value={plan.title}
              onChange={(e) => patch({ title: e.target.value })}
              placeholder="请输入图文标题"
              maxLength={50}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">正文描述</Label>
            <Textarea
              value={plan.description}
              onChange={(e) => patch({ description: e.target.value })}
              placeholder="描述文字…（小红书/快手可用作标题/正文，抖音为正文）"
              rows={4}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">话题标签</Label>
            <Input
              value={plan.tags}
              onChange={(e) => patch({ tags: e.target.value })}
              placeholder="多个话题用空格或 # 分隔，如 生活 美食 #旅行"
            />
          </div>

          <div className="flex items-center justify-between rounded-xl border border-border/70 p-4">
            <div className="flex items-center gap-3">
              <CalendarClock className="w-4 h-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-foreground">定时发布</p>
                <p className="text-[11px] text-muted-foreground">不开启则提交后立即发布</p>
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
                <Input
                  type="date"
                  value={plan.scheduleDate || ""}
                  onChange={(e) => patch({ scheduleDate: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">时间</Label>
                <Input
                  type="time"
                  value={plan.scheduleTime || ""}
                  onChange={(e) => patch({ scheduleTime: e.target.value })}
                />
              </div>
              <p className="text-[11px] text-yellow-500/90 sm:col-span-2">
                各平台定时发布时间需晚于当前 2 小时，否则会按平台规则校验失败。
              </p>
            </div>
          )}
        </div>
      </section>

      {/* 5. 平台专属配置（每个已选平台一个面板） */}
      {plan.platforms.length > 0 && (
        <section className="space-y-3">
          <Label className="text-base font-medium">
            5. 平台发布配置（{plan.platforms.map((k) => platformMeta(k)?.name).join(" / ")}）
          </Label>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {plan.platforms.includes("douyin") && (
              <div key="douyin-note"><DouyinConfig data={commonProps.data} onChange={commonProps.onChange} /></div>
            )}
            {plan.platforms.includes("xiaohongshu") && (
              <div key="xhs-note"><XhsConfig data={commonProps.data} onChange={commonProps.onChange} /></div>
            )}
            {plan.platforms.includes("kuaishou") && (
              <div key="ks-note"><KuaishouConfig data={commonProps.data} onChange={commonProps.onChange} /></div>
            )}
          </div>
        </section>
      )}

      {/* 图片选择弹窗 */}
      {pickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setPickerOpen(false)} />
          <div className="relative w-full max-w-3xl bg-card border border-border/70 rounded-2xl p-6 max-h-[85vh] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-foreground">选择图片素材（可多选，已选 {plan.imageIds.length}）</h3>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => setPickerOpen(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="搜索图片文件名…"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-3 md:grid-cols-5 gap-3 overflow-y-auto pr-1 pb-2">
              {filteredImages.length === 0 && (
                <p className="col-span-full text-center text-sm text-muted-foreground py-10">
                  没有找到图片素材。请先到
                  <a href="/materials" className="text-primary underline mx-1">素材管理</a>
                  上传图片。
                </p>
              )}
              {filteredImages.map((m) => {
                const isSelected = plan.imageIds.includes(String(m.id))
                return (
                  <button
                    key={String(m.id)}
                    onClick={() => toggleImage(String(m.id))}
                    className={cn(
                      "relative rounded-xl overflow-hidden border bg-black aspect-[3/4] transition-all",
                      isSelected ? "border-primary ring-2 ring-primary" : "border-border/70 hover:border-border"
                    )}
                  >
                    <Image
                      src={toBackendFileUrl((m as any).fileUrl || (m as any).storageKey || (m as any).file_path)}
                      alt={m.filename}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                    {isSelected && (
                      <span className="absolute top-1 right-1 w-5 h-5 rounded-full bg-primary flex items-center justify-center text-[10px] text-primary-foreground font-bold">
                        {plan.imageIds.indexOf(String(m.id)) + 1}
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
              <Button onClick={() => setPickerOpen(false)} disabled={plan.imageIds.length === 0}>
                确定（{plan.imageIds.length} 张）
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
