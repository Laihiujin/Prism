"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { ArrowRightLeft, CheckCircle2, ChevronDown, Database, Download, Loader2, RefreshCw, ShieldOff, TestTube2, XCircle } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"
import { API_ENDPOINTS } from "@/lib/env"

type CcSwitchProvider = {
  id: string
  app_type: string
  name: string
  is_current: boolean
  category?: string
  provider_type?: string
  base_url?: string
  api_key?: string
  api_mode?: string
  models?: Array<{ id: string; name?: string }>
}

type CcSwitchStatus = {
  available: boolean
  db_path?: string
  detail?: string
  providers_by_type?: Record<string, { count: number; current: number }>
}

/** cc-switch 支持的 agent 类型（与后端 APP_TYPES 对齐） */
const APP_TYPES = [
  { value: "claude", label: "Claude Code" },
  { value: "claude-desktop", label: "Claude Desktop" },
  { value: "codex", label: "Codex" },
  { value: "gemini", label: "Gemini CLI" },
  { value: "grokbuild", label: "Grok Build" },
  { value: "opencode", label: "OpenCode" },
  { value: "openclaw", label: "OpenClaw" },
  { value: "hermes", label: "Hermes" },
  { value: "pi", label: "Pi" },
] as const

type AppTypeValue = (typeof APP_TYPES)[number]["value"]

type ProjectHermesConfig = {
  provider?: string | null
  model?: string | null
  base_url?: string | null
  api_key?: string | null
  max_turns?: number
  is_configured?: boolean
}

const fetchJson = async (url: string, init?: RequestInit) => {
  const res = await fetch(url, init)
  return res.json()
}

export function CcSwitchPanel() {
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<CcSwitchStatus | null>(null)
  const [providers, setProviders] = useState<CcSwitchProvider[]>([])
  const [projectConfig, setProjectConfig] = useState<ProjectHermesConfig | null>(null)
  const [appType, setAppType] = useState<AppTypeValue>("hermes")
  const [applyingId, setApplyingId] = useState<string | null>(null)
  const [selectedModels, setSelectedModels] = useState<Record<string, string>>({})
  const [liveModels, setLiveModels] = useState<Record<string, Array<{ id: string; name?: string }>>>({})
  const [testResult, setTestResult] = useState<
    Record<string, { ok?: boolean; stage?: string; error?: string; latency_ms?: number }>
  >({})
  const [fetchingId, setFetchingId] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(
    async (targetType?: AppTypeValue) => {
      const at = targetType ?? appType
      setLoading(true)
      try {
        const statusRes = await fetchJson(`${API_ENDPOINTS.base}/api/v1/ccswitch/status`)
        const statusData = statusRes?.data as CcSwitchStatus | null
        setStatus(statusData)

        if (statusData?.available) {
          const provRes = await fetchJson(
            `${API_ENDPOINTS.base}/api/v1/ccswitch/providers?app_type=${encodeURIComponent(at)}`
          )
          setProviders(provRes?.data?.providers || [])
        } else {
          setProviders([])
        }
      } catch (error) {
        console.error("Failed to load cc-switch status:", error)
        toast({
          title: "读取 cc-switch 失败",
          description: "无法读取本机 CC Switch 数据。",
          variant: "destructive",
        })
      } finally {
        setLoading(false)
      }
    },
    [appType, toast]
  )

  const loadProjectConfig = useCallback(async () => {
    try {
      const res = await fetchJson(`${API_ENDPOINTS.base}/api/v1/agent/config/hermes`)
      setProjectConfig((res?.data || null) as ProjectHermesConfig | null)
    } catch {
      setProjectConfig(null)
    }
  }, [])

  useEffect(() => {
    void refresh()
    void loadProjectConfig()
  }, [refresh, loadProjectConfig])

  const applyProvider = useCallback(
    async (providerId?: string, model?: string) => {
      setApplyingId(providerId || "__current__")
      try {
        const res = await fetchJson(`${API_ENDPOINTS.base}/api/v1/ccswitch/apply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            app_type: appType,
            provider_id: providerId || null,
            model: model || null,
          }),
        })
        if (!res?.success) {
          throw new Error(res?.detail || res?.message || "应用失败")
        }
        toast({
          title: "已应用到项目 Hermes",
          description: res?.data?.message || "配置已写入项目内。",
        })
        await loadProjectConfig()
        await refresh()
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        toast({ title: "应用失败", description: message, variant: "destructive" })
      } finally {
        setApplyingId(null)
      }
    },
    [appType, loadProjectConfig, refresh, toast]
  )

  const fetchModels = useCallback(
    async (providerId: string) => {
      setFetchingId(providerId)
      try {
        const res = await fetchJson(`${API_ENDPOINTS.base}/api/v1/ccswitch/models`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ app_type: appType, provider_id: providerId }),
        })
        if (!res?.success) {
          throw new Error(res?.detail || res?.message || "抓取失败")
        }
        const models = res?.data?.models || []
        setLiveModels((prev) => ({ ...prev, [providerId]: models }))
        if (models.length > 0) {
          setSelectedModels((prev) => ({ ...prev, [providerId]: models[0].id }))
        }
        toast({
          title: "已抓取模型",
          description: res?.message || `共 ${models.length} 个模型`,
        })
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        toast({ title: "抓取模型失败", description: message, variant: "destructive" })
      } finally {
        setFetchingId(null)
      }
    },
    [appType, toast]
  )

  const testModel = useCallback(
    async (providerId: string, model?: string) => {
      setTestingId(providerId)
      setTestResult((prev) => ({ ...prev, [providerId]: {} }))
      try {
        const res = await fetchJson(`${API_ENDPOINTS.base}/api/v1/ccswitch/test`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ app_type: appType, provider_id: providerId, model: model || null }),
        })
        const data = res?.data || {}
        setTestResult((prev) => ({ ...prev, [providerId]: data }))
        if (!data?.ok) {
          toast({
            title: "测试失败",
            description: data?.error || res?.detail || "连接异常",
            variant: "destructive",
          })
        } else {
          toast({
            title: "测试通过",
            description: `连接正常${data?.latency_ms ? `（${data.latency_ms}ms）` : ""}${model ? `，模型 ${model} 可用` : ""}`,
          })
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        setTestResult((prev) => ({ ...prev, [providerId]: { ok: false, error: message } }))
        toast({ title: "测试失败", description: message, variant: "destructive" })
      } finally {
        setTestingId(null)
      }
    },
    [appType, toast]
  )

  const appliedProviderName = useMemo(() => {
    if (!projectConfig?.is_configured) return null
    const byUrl = providers.find((p) => p.base_url === projectConfig.base_url)
    if (byUrl) return byUrl.name
    // base_url 带 /v1 后缀等差异时，宽松匹配
    const norm = (u?: string | null) => (u || "").replace(/\/+$/, "")
    return (
      providers.find(
        (p) => norm(p.base_url).replace(/\/v1$/, "") === norm(projectConfig.base_url).replace(/\/v1$/, "")
      )?.name || null
    )
  }, [projectConfig, providers])

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="border-border/70 bg-transparent">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-start justify-between gap-4 rounded-2xl px-5 py-4 text-left transition-colors hover:bg-accent/40"
          >
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Database className="h-4 w-4" />
                <div className="text-sm font-medium text-foreground">cc-switch 模型管辖</div>
              </div>
              <p className="text-xs leading-5 text-muted-foreground">
                只读本机 CC Switch 的 provider 档案（<code>~/.cc-switch/cc-switch.db</code>），
                把选中的 provider 应用到<b>项目内</b>的 Hermes Agent。不改动本机 Claude / Hermes 配置。
              </p>
            </div>
            <ChevronDown
              className={cn(
                "mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                open && "rotate-180"
              )}
            />
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="space-y-5 border-t border-border/70 pt-5">
        {/* 状态行 */}
        <div className="flex flex-wrap items-center gap-2">
          {loading ? (
            <Badge variant="secondary" className="bg-foreground/10">
              <Loader2 className="mr-1 h-3 w-3 animate-spin" /> 检测中…
            </Badge>
          ) : status?.available ? (
            <Badge className="gap-1 bg-black text-white">
              <CheckCircle2 className="h-3.5 w-3.5" /> cc-switch 已连接
            </Badge>
          ) : (
            <Badge variant="destructive" className="gap-1">
              <ShieldOff className="h-3.5 w-3.5" /> 未检测到 cc-switch 数据库
            </Badge>
          )}
          <span className="text-xs text-muted-foreground break-all">
            {status?.db_path || "~/.cc-switch/cc-switch.db"}
          </span>
          <Button size="sm" variant="secondary" className="ml-auto bg-foreground/10" onClick={() => void refresh()}>
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            刷新
          </Button>
        </div>

        {!status?.available && (
          <div className="rounded-2xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
            {status?.detail || "请先在本机 CC Switch 应用中添加 provider（例如 hermes 类型），再回到这里刷新。"}
          </div>
        )}

        {/* agent 类型切换 */}
        {status?.available && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-[0.22em] text-foreground/40">Agent 类型</span>
            <Select
              value={appType}
              onValueChange={(value) => {
                setAppType(value as AppTypeValue)
                setLiveModels({})
                setSelectedModels({})
                setTestResult({})
              }}
            >
              <SelectTrigger className="h-8 w-52 text-xs">
                <SelectValue placeholder="选择 agent 类型" />
              </SelectTrigger>
              <SelectContent>
                {APP_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-xs">
                    {t.label}（{t.value}）
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-xs text-muted-foreground">
              {status?.providers_by_type?.[appType]?.count != null
                ? `${status.providers_by_type[appType].count} 个 provider`
                : "该类型暂无 provider"}
            </span>
          </div>
        )}

        {status?.available && (
          <div className="grid grid-cols-1 gap-3">
            {providers.length === 0 && (
              <div className="rounded-2xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
                cc-switch 中还没有 <b>{appType}</b> 类型的 provider，请先在本机 CC Switch 中添加。
              </div>
            )}
            {providers.map((provider) => (
              <div
                key={provider.id}
                className={cn(
                  "rounded-2xl border p-4 transition-all",
                  provider.is_current ? "border-border bg-black" : "border-border/70 bg-card/30"
                )}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{provider.name}</span>
                      {provider.api_mode && (
                        <Badge variant="secondary" className="bg-foreground/10 text-xs text-muted-foreground">
                          {provider.api_mode}
                        </Badge>
                      )}
                      {provider.is_current && (
                        <Badge className="bg-black text-white">CC Switch 当前选中</Badge>
                      )}
                    </div>
                    <div className="mt-1 break-all text-xs text-muted-foreground">
                      {provider.base_url || <span className="text-foreground/40">（无 base_url，可能为 OAuth/官方登录态）</span>}
                    </div>
                    {provider.models && provider.models.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {provider.models.map((m) => (
                          <Badge key={m.id} variant="secondary" className="bg-black text-foreground/80 text-xs">
                            {m.name || m.id}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {(liveModels[provider.id] || provider.models) && (liveModels[provider.id] || provider.models).length > 0 && (
                      <Select
                        value={selectedModels[provider.id] || (liveModels[provider.id] || provider.models)[0].id}
                        onValueChange={(value) =>
                          setSelectedModels((prev) => ({ ...prev, [provider.id]: value }))
                        }
                      >
                        <SelectTrigger className="h-8 w-56 text-xs">
                          <SelectValue placeholder="选择模型" />
                        </SelectTrigger>
                        <SelectContent>
                          {(liveModels[provider.id] || provider.models).map((m) => (
                            <SelectItem key={m.id} value={m.id} className="text-xs">
                              {m.name || m.id}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    <div className="flex flex-wrap justify-end gap-1.5">
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-8 rounded-lg text-xs bg-foreground/10"
                        onClick={() => void fetchModels(provider.id)}
                        disabled={fetchingId !== null || testingId !== null}
                      >
                        {fetchingId === provider.id ? (
                          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Download className="mr-1 h-3.5 w-3.5" />
                        )}
                        拉取模型
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-8 rounded-lg text-xs bg-foreground/10"
                        onClick={() => void testModel(provider.id, selectedModels[provider.id] || provider.models?.[0]?.id)}
                        disabled={fetchingId !== null || testingId !== null}
                      >
                        {testingId === provider.id ? (
                          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <TestTube2 className="mr-1 h-3.5 w-3.5" />
                        )}
                        测试
                      </Button>
                      <Button
                        size="sm"
                        onClick={() =>
                          void applyProvider(provider.id, selectedModels[provider.id] || provider.models?.[0]?.id)
                        }
                        disabled={applyingId !== null}
                        className="gap-1.5"
                      >
                        {applyingId === provider.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <ArrowRightLeft className="h-4 w-4" />
                        )}
                        应用到项目 Hermes
                      </Button>                    </div>
                    {testResult[provider.id] && testResult[provider.id].ok !== undefined && (
                      <div
                        className={cn(
                          "flex max-w-full items-center gap-1 text-xs break-all",
                          testResult[provider.id].ok ? "text-emerald-400" : "text-red-400"
                        )}
                      >
                        {testResult[provider.id].ok ? (
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5 shrink-0" />
                        )}
                        <span>
                          {testResult[provider.id].ok
                            ? `连接正常${testResult[provider.id].latency_ms ? `（${testResult[provider.id].latency_ms}ms）` : ""}`
                            : `${testResult[provider.id].stage ? `${testResult[provider.id].stage}：` : ""}${testResult[provider.id].error || "测试失败"}`}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 当前项目内 Hermes 生效配置 */}
        <div className="rounded-2xl border border-border/70 bg-card/30 p-4">
          <div className="text-xs uppercase tracking-[0.22em] text-foreground/40">项目内 Hermes 当前生效</div>
          {projectConfig?.is_configured ? (
            <div className="mt-2 space-y-1 text-sm text-foreground/80">
              <div>
                提供商：<span className="text-foreground">{projectConfig.provider || "custom"}</span>
                {appliedProviderName && (
                  <span className="text-muted-foreground">（来自 cc-switch：{appliedProviderName}）</span>
                )}
              </div>
              <div>模型：<span className="text-foreground">{projectConfig.model}</span></div>
              <div className="break-all">Base URL：<span className="text-foreground">{projectConfig.base_url}</span></div>
              <div>
                API Key：<span className="text-foreground">{"*".repeat(Math.min(projectConfig.api_key?.length || 0, 12))}</span>
              </div>
            </div>
          ) : (
            <div className="mt-2 text-sm text-muted-foreground">尚未配置 —— 选上面的 provider 和模型，一键应用到项目。</div>
          )}
        </div>
        </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}
