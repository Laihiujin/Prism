"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, CheckCircle2, Clock, Layers, Play, Sparkles, UploadCloud } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/components/ui/use-toast"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import type { Account, Material } from "@/lib/schemas"

const PLATFORM_OPTIONS = [
  { value: "douyin", label: "抖音", code: 3 },
  { value: "kuaishou", label: "快手", code: 4 },
  { value: "redbook", label: "小红书", code: 1 },
  { value: "tencent", label: "视频号", code: 2 },
  { value: "bilibili", label: "B站", code: 5 },
] as const

type PlatformValue = (typeof PLATFORM_OPTIONS)[number]["value"]

const defaultTimePoints = ["10:00", "14:00", "20:00"]

export default function CampaignPackageBuilderPage() {
  const params = useParams()
  const router = useRouter()
  const { toast } = useToast()
  const planId = params.id as string

  const [packageName, setPackageName] = useState("")
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformValue>("douyin")
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
  const [selectedMaterials, setSelectedMaterials] = useState<string[]>([])
  const [dispatchMode, setDispatchMode] = useState<"random" | "fixed">("random")
  const [timePoints, setTimePoints] = useState<string[]>(defaultTimePoints)
  const [scheduleMode, setScheduleMode] = useState<"immediate" | "daily">("daily")
  const [perAccountPerDay, setPerAccountPerDay] = useState(1)
  const [generateTasks, setGenerateTasks] = useState(true)
  const [publishNow, setPublishNow] = useState(true)
  const [note, setNote] = useState("")
  const [saving, setSaving] = useState(false)

  const { data: planResponse } = useQuery({
    queryKey: ["plan-new", planId],
    queryFn: async () => {
      const res = await fetch(`/api/plans/${planId}`)
      const payload = await res.json()
      return payload?.data
    },
  })

  const { data: accountsResponse } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => {
      const res = await fetch("/api/accounts", { cache: "no-store" })
      const payload = await res.json()
      return Array.isArray(payload?.data) ? (payload.data as Account[]) : []
    },
  })

  const { data: materialsResponse } = useQuery({
    queryKey: ["materials"],
    queryFn: async () => {
      const res = await fetch("/api/materials", { cache: "no-store" })
      const payload = await res.json()
      const list = Array.isArray(payload?.data?.data) ? payload.data.data : Array.isArray(payload?.data) ? payload.data : []
      return list as Material[]
    },
  })

  const plan = planResponse
  const accounts = accountsResponse ?? []
  const materials = materialsResponse ?? []

  const planPlatforms: PlatformValue[] = useMemo(() => {
    const raw = plan?.platforms ?? []
    if (Array.isArray(raw) && raw.length > 0) {
      const normalized = raw.map((item: any) => String(item)) as PlatformValue[]
      return normalized
    }
    return ["douyin"]
  }, [plan])

  useEffect(() => {
    if (planPlatforms.length > 0) {
      setSelectedPlatform(planPlatforms[0])
    }
    if (plan?.name) {
      setPackageName(`${plan.name} - 任务包`)
    }
  }, [plan, planPlatforms])

  const filteredAccounts = useMemo(
    () => accounts.filter((acc) => acc.platform === selectedPlatform),
    [accounts, selectedPlatform]
  )

  const pendingMaterials = useMemo(
    () => materials.filter((m) => m.status === "pending"),
    [materials]
  )

  const toggleAccount = (id: string) => {
    setSelectedAccounts((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]))
  }

  const toggleMaterial = (id: string) => {
    setSelectedMaterials((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]))
  }

  const handleAddTimePoint = () => {
    const last = timePoints[timePoints.length - 1] || "10:00"
    setTimePoints((prev) => [...prev, last])
  }

  const handleChangeTimePoint = (index: number, value: string) => {
    setTimePoints((prev) => prev.map((item, idx) => (idx === index ? value : item)))
  }

  const selectedPlatformCode =
    PLATFORM_OPTIONS.find((item) => item.value === selectedPlatform)?.code ?? PLATFORM_OPTIONS[0].code

  const buildPublishTasks = () => {
    const files = selectedMaterials
      .map((id) => materials.find((m) => String(m.id) === String(id)))
      .map((item) => item?.storageKey || item?.filename)
      .filter(Boolean) as string[]

    if (!files.length || !selectedAccounts.length) return []

    return selectedAccounts.map((accountId) => ({
      platformCode: selectedPlatformCode,
      fileList: files,
      accountList: [accountId],
      title: packageName || plan?.name || "发布任务",
      tags: [],
      enableTimer: scheduleMode !== "immediate",
      scheduleTimes: scheduleMode === "immediate" ? undefined : timePoints,
      scheduleTime: scheduleMode === "immediate" ? undefined : timePoints[0],
      videosPerDay: perAccountPerDay,
    }))
  }

  const handleSubmit = async () => {
    if (!selectedAccounts.length || !selectedMaterials.length) {
      toast({ variant: "destructive", title: "请选择账号与素材" })
      return
    }
    setSaving(true)
    try {
      const payload = {
        plan_id: Number(planId),
        name: packageName || "任务包",
        platform: selectedPlatform,
        account_ids: selectedAccounts,
        material_ids: selectedMaterials,
        dispatch_mode: dispatchMode,
        time_strategy: {
          mode: scheduleMode === "immediate" ? "once" : "date_range",
          time_points: timePoints,
          per_account_per_day: perAccountPerDay,
        },
        remark: note,
      }

      const res = await fetch("/api/task-packages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const msg = await res.text()
        throw new Error(msg || "创建任务包失败")
      }
      const pkg = await res.json().catch(() => ({}))
      const packageId = pkg?.data?.package_id ?? pkg?.package_id

      if (generateTasks && packageId) {
        await fetch(`/api/task-packages/${packageId}/generate`, { method: "POST" })
      }

      if (publishNow) {
        const publishTasks = buildPublishTasks()
        if (publishTasks.length) {
          await fetch("/api/publish", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tasks: publishTasks }),
          })
        }
      }

      toast({ title: "任务包已创建", description: "可在计划详情中查看任务" })
      router.push(`/campaigns/${planId}`)
    } catch (error) {
      toast({
        variant: "destructive",
        title: "操作失败",
        description: error instanceof Error ? error.message : "未知错误",
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-semibold">构建任务包</h1>
          <p className="text-sm text-white/60">选择素材与账号，生成可发布的子任务</p>
        </div>
        <div className="flex gap-2">

          <Button variant="outline" className="rounded-xl" onClick={() => router.push("/campaigns/publish")}>
            <UploadCloud className="mr-2 h-4 w-4" />
            发布中心
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2 border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle>基础信息</CardTitle>
            <CardDescription>确认计划与任务包信息，便于追踪与复用</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>关联计划</Label>
                <div className="mt-2 rounded-xl border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <span className="font-medium">{plan?.name || `计划 #${planId}`}</span>
                  </div>
                  <p className="mt-1 text-xs text-white/60 line-clamp-2">{plan?.remark || "未添加备注"}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {planPlatforms.map((p) => (
                      <Badge key={p} variant="secondary" className="rounded-xl text-xs">
                        {PLATFORM_OPTIONS.find((item) => item.value === p)?.label || p}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <Label>任务包名称</Label>
                <Input
                  value={packageName}
                  onChange={(e) => setPackageName(e.target.value)}
                  placeholder="例如：11月矩阵-日更任务包"
                  className="rounded-xl"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>执行备注</Label>
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="说明时间策略、选材理由等（可选）"
                className="min-h-[90px] rounded-xl"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle>发布策略</CardTitle>
            <CardDescription>控制分发模式与定时配置</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>分发模式</Label>
              <div className="grid grid-cols-2 gap-2">
                {["random", "fixed"].map((mode) => (
                  <Button
                    key={mode}
                    variant={dispatchMode === mode ? "secondary" : "outline"}
                    className="rounded-xl"
                    onClick={() => setDispatchMode(mode as "random" | "fixed")}
                  >
                    {mode === "random" ? "随机分配" : "固定顺序"}
                  </Button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label>时间策略</Label>
              <div className="flex gap-2">
                <Button
                  variant={scheduleMode === "immediate" ? "secondary" : "outline"}
                  className="rounded-xl flex-1"
                  onClick={() => setScheduleMode("immediate")}
                >
                  立即执行
                </Button>
                <Button
                  variant={scheduleMode === "daily" ? "secondary" : "outline"}
                  className="rounded-xl flex-1"
                  onClick={() => setScheduleMode("daily")}
                >
                  每日定时
                </Button>
              </div>
              {scheduleMode === "daily" && (
                <div className="space-y-2 rounded-xl border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm text-white/80">时间点</Label>
                    <Button variant="ghost" size="sm" className="rounded-lg" onClick={handleAddTimePoint}>
                      + 添加
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {timePoints.map((time, index) => (
                      <Input
                        key={`${time}-${index}`}
                        value={time}
                        onChange={(e) => handleChangeTimePoint(index, e.target.value)}
                        placeholder="HH:mm"
                        className="rounded-lg bg-black/20"
                      />
                    ))}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-sm text-white/80">单账号每日条数</Label>
                    <Input
                      type="number"
                      min={1}
                      value={perAccountPerDay}
                      onChange={(e) => setPerAccountPerDay(Math.max(1, Number(e.target.value) || 1))}
                      className="rounded-lg bg-black/20"
                    />
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3">
              <div>
                <p className="font-medium">自动生成任务</p>
                <p className="text-xs text-white/60">保存后立即拆解为发布任务</p>
              </div>
              <Switch checked={generateTasks} onCheckedChange={setGenerateTasks} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/10 p-3">
              <div>
                <p className="font-medium">直接调用发布接口</p>
                <p className="text-xs text-white/70">同步触发矩阵发布，避免重复配置</p>
              </div>
              <Switch checked={publishNow} onCheckedChange={setPublishNow} />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border-white/10 bg-white/5 lg:col-span-2">
          <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle>选择平台与账号</CardTitle>
              <CardDescription>仅展示当前平台可用账号</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              {PLATFORM_OPTIONS.map((option) => (
                <Button
                  key={option.value}
                  variant={selectedPlatform === option.value ? "secondary" : "outline"}
                  className="rounded-xl"
                  onClick={() => setSelectedPlatform(option.value)}
                  disabled={!planPlatforms.includes(option.value)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {filteredAccounts.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-white/60">
                当前平台暂无账号
              </div>
            ) : (
              <ScrollArea className="max-h-[320px]">
                <div className="grid gap-3 md:grid-cols-2">
                  {filteredAccounts.map((account) => {
                    const active = selectedAccounts.includes(account.id)
                    return (
                      <button
                        key={account.id}
                        onClick={() => toggleAccount(account.id)}
                        className={cn(
                          "flex w-full items-center justify-between rounded-xl border p-3 text-left transition",
                          active
                            ? "border-primary/50 bg-primary/10"
                            : "border-white/10 bg-white/5 hover:border-white/20"
                        )}
                      >
                        <div>
                          <p className="font-medium">{account.name}</p>
                          <p className="text-xs text-white/60">{account.user_id || account.id}</p>
                        </div>
                        <Badge variant={active ? "secondary" : "outline"} className="rounded-lg">
                          {account.status}
                        </Badge>
                      </button>
                    )
                  })}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle>选择素材</CardTitle>
            <CardDescription>仅显示待发布素材</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {pendingMaterials.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-white/60">
                暂无待发布素材
              </div>
            ) : (
              <ScrollArea className="max-h-[400px]">
                <div className="space-y-2">
                  {pendingMaterials.map((material) => {
                    const active = selectedMaterials.includes(String(material.id))
                    return (
                      <button
                        key={material.id}
                        onClick={() => toggleMaterial(String(material.id))}
                        className={cn(
                          "w-full rounded-xl border p-3 text-left transition",
                          active
                            ? "border-primary/50 bg-primary/10"
                            : "border-white/10 bg-white/5 hover:border-white/20"
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <p className="font-medium">{material.filename}</p>
                            <p className="text-xs text-white/60">{material.filesize}</p>
                          </div>
                          <Badge variant="outline" className="rounded-lg text-xs">
                            {(material.type as any)?.toUpperCase?.() || 'FILE'}
                          </Badge>
                        </div>
                        {material.note && (
                          <p className="mt-1 text-xs text-white/60 line-clamp-2">{material.note}</p>
                        )}
                      </button>
                    )
                  })}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between py-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-primary" />
              <p className="font-semibold">执行摘要</p>
            </div>
            <p className="text-sm text-white/70">
              {selectedAccounts.length} 个账号 · {selectedMaterials.length} 条素材 ·{" "}
              {scheduleMode === "immediate" ? "即时发布" : `${timePoints.length} 个时间点`}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="ghost"
              className="rounded-xl border border-white/10"
              onClick={() => router.push(`/campaigns/${planId}`)}
            >
              取消
            </Button>
            <Button
              className="rounded-xl"
              onClick={handleSubmit}
              disabled={saving}
            >
              {saving ? (
                <span className="flex items-center gap-2">
                  <Clock className="h-4 w-4 animate-spin" />
                  保存中...
                </span>
              ) : publishNow ? (
                <span className="flex items-center gap-2">
                  <Play className="h-4 w-4" />
                  保存并发布
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  保存任务包
                </span>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
