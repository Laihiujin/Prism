"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Loader2, RefreshCcw, Server, Radio, Puzzle, Settings2 } from "lucide-react"

import { PageHeader } from "@/components/layout/page-scaffold"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useToast } from "@/components/ui/use-toast"
import { API_ENDPOINTS } from "@/lib/env"
import { cn } from "@/lib/utils"
import { resolveRuntimeBackendBase } from "@/lib/runtime-backend"

/* ── Types (mirror Hermes /api/mcp/servers, /api/plugins, /config) ─────────── */

type McpServer = {
  name: string
  transport: "http" | "stdio" | "invalid"
  status: "active" | "configured" | "disabled" | "invalid_config" | "unknown"
  enabled: boolean
  url?: string
  headers?: Record<string, string>
  command?: string
  args?: string[]
  env?: Record<string, string>
  timeout?: number
  connect_timeout?: number
}

type McpServerPayload = {
  servers: McpServer[]
  toggle_supported?: boolean
  reload_required?: boolean
}

type PluginEntry = {
  name: string
  key: string
  version: string
  description: string
  enabled: boolean
  activation: "enabled" | "disabled" | "exclusive" | "provider"
  hooks: string[]
}

type PluginPayload = {
  plugins: PluginEntry[]
  empty: boolean
  supported_hooks: string[]
  read_only: boolean
}

type ModelConfig = {
  provider?: string | null
  model?: string | null
  base_url?: string | null
  api_key?: string | null
  max_turns?: number
  is_configured?: boolean
}

const PROVIDERS = [
  { value: "custom", label: "OpenAI Compatible" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "lmstudio", label: "LM Studio" },
]

type TabKey = "model" | "mcp" | "plugin"

const TABS: { key: TabKey; label: string; icon: any }[] = [
  { key: "model", label: "模型配置", icon: Settings2 },
  { key: "mcp", label: "MCP 服务", icon: Server },
  { key: "plugin", label: "插件", icon: Puzzle },
]

export default function HermesInteropPage() {
  const { toast } = useToast()
  const [tab, setTab] = useState<TabKey>("model")
  const [base, setBase] = useState(API_ENDPOINTS.base)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let active = true
    resolveRuntimeBackendBase()
      .catch(() => API_ENDPOINTS.base)
      .then((url) => {
        if (active) setBase(url)
      })
    return () => {
      active = false
    }
  }, [])

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), [])
  const url = useCallback(
    (path: string) => `${base}/api/v1/agent/config/${path}`,
    [base]
  )

  return (
    <div className="space-y-6 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        eyebrow="Hermes Interop"
        title="模型 / MCP / 插件"
        description="与 Hermes 共用同一份 config.yaml —— 在 Prism 控制台即可查看并切换 Hermes 的模型、MCP 服务与插件。"
        actions={
          <Button variant="outline" size="sm" className="rounded-lg border-border/70 bg-black hover:bg-accent/50" onClick={refresh}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            刷新
          </Button>
        }
      />

      <div className="flex items-center gap-2">
        {TABS.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition",
                tab === t.key
                  ? "border-foreground/50 bg-black text-foreground"
                  : "border-border/70 bg-card/40 text-muted-foreground hover:bg-accent/40"
              )}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      {tab === "model" && <ModelConfigPanel baseUrl={base} refreshKey={refreshKey} toast={toast} />}
      {tab === "mcp" && <McpPanel baseUrl={base} refreshKey={refreshKey} toast={toast} />}
      {tab === "plugin" && <PluginPanel baseUrl={base} refreshKey={refreshKey} toast={toast} />}
    </div>
  )
}

/* ── Helper: the backend wraps everything as { success, data } ─────────────── */

async function apiGet<T>(base: string, path: string): Promise<T | null> {
  const res = await fetch(`${base}/api/v1/agent/config/${path}`, { cache: "no-store" })
  if (!res.ok) return null
  const payload = await res.json().catch(() => null)
  return (payload?.data ?? null) as T | null
}

async function apiPatch<T>(base: string, path: string, body: unknown): Promise<boolean> {
  const res = await fetch(`${base}/api/v1/agent/config/${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const payload = await res.json().catch(() => null)
  return res.ok && payload?.success !== false
}

/* ── Tab 1: 模型配置 (Hermes Providers panel) ─────────────────────────────── */

function ModelConfigPanel({
  baseUrl,
  refreshKey,
  toast,
}: {
  baseUrl: string
  refreshKey: number
  toast: any
}) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState<ModelConfig | null>(null)
  const [provider, setProvider] = useState("custom")
  const [model, setModel] = useState("")
  const [modelList, setModelList] = useState<string[]>([])
  const [baseUrlField, setBaseUrlField] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [maxTurns, setMaxTurns] = useState("12")

  const load = useCallback(async () => {
    setLoading(true)
    const config = await apiGet<ModelConfig>(baseUrl, "hermes")
    setConfig(config)
    if (config) {
      setProvider(config.provider || "custom")
      setModel(config.model || "")
      setBaseUrlField(config.base_url || "")
      setApiKey(config.api_key || "")
      setMaxTurns(String(config.max_turns || 12))
    }
    setLoading(false)
  }, [baseUrl])

  const loadModels = useCallback(async () => {
    const res = await fetch(`${baseUrl}/api/v1/ai/models`, { cache: "no-store" })
    const payload = await res.json().catch(() => null)
    const providers: Record<string, any[]> = payload?.providers || {}
    const names = new Set<string>()
    for (const list of Object.values(providers)) {
      for (const m of list || []) {
        const id = m?.id || m?.model_name || m?.name
        if (id) names.add(String(id))
      }
    }
    setModelList(Array.from(names).sort())
  }, [baseUrl])

  useEffect(() => {
    void load()
    void loadModels()
  }, [load, loadModels, refreshKey])

  const save = useCallback(async () => {
    if (!model.trim()) {
      toast({ variant: "destructive", title: "模型不能为空", description: "请填写默认模型。" })
      return
    }
    setSaving(true)
    const res = await fetch(`${baseUrl}/api/v1/agent/config/hermes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        llm: {
          provider,
          model: model.trim(),
          api_key: apiKey.trim(),
          base_url: baseUrlField.trim() || null,
        },
        runtime: { max_turns: Number(maxTurns || 12) },
      }),
    })
    const payload = await res.json().catch(() => ({}))
    setSaving(false)
    if (!res.ok || payload?.success === false) {
      toast({ variant: "destructive", title: "保存失败", description: payload?.detail || payload?.data?.message || "请稍后重试" })
      return
    }
    await load()
    toast({ title: "模型已保存", description: "已同步到 Hermes 运行时的 config.yaml。" })
  }, [baseUrl, provider, model, apiKey, baseUrlField, maxTurns, load, toast])

  const test = useCallback(async () => {
    const res = await fetch(`${baseUrl}/api/v1/agent/config/hermes/test`, { method: "POST" })
    const payload = await res.json().catch(() => ({}))
    if (!res.ok || payload?.success === false) {
      toast({ variant: "destructive", title: "连接测试失败", description: payload?.data?.message || payload?.detail || "请检查模型配置。" })
      return
    }
    toast({ title: "Hermes 连接正常", description: payload?.data?.test_result || "运行时已能调用当前模型。" })
  }, [baseUrl, toast])

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card className="border-border/70 bg-card/40">
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Radio className="h-4 w-4" />
            {loading ? "加载中…" : config?.is_configured ? "已配置" : "尚未配置"}
            {model && <span className="font-mono text-[11px] text-foreground/70">→ {model}</span>}
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Provider</Label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="h-8 rounded-lg border-border/70 bg-black">
                <SelectValue placeholder="选择 Provider" />
              </SelectTrigger>
              <SelectContent>
                {PROVIDERS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Base URL</Label>
            <Input
              className="h-8 rounded-lg border-border/70 bg-black font-mono text-[12px]"
              value={baseUrlField}
              onChange={(e) => setBaseUrlField(e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">API Key</Label>
            <Input
              type="password"
              className="h-8 rounded-lg border-border/70 bg-black font-mono text-[12px]"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-…"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">模型 (Model)</Label>
              <Input
                list="hermes-model-list"
                className="h-8 rounded-lg border-border/70 bg-black font-mono text-[12px]"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="model id"
              />
              <datalist id="hermes-model-list">
                {modelList.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">最大轮次 (max_turns)</Label>
              <Input
                type="number"
                min={1}
                max={90}
                className="h-8 rounded-lg border-border/70 bg-black font-mono text-[12px]"
                value={maxTurns}
                onChange={(e) => setMaxTurns(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button size="sm" className="h-7 rounded-lg text-xs" onClick={() => void save()} disabled={saving}>
              {saving ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Settings2 className="mr-1.5 h-3.5 w-3.5" />}
              {saving ? "保存中…" : "保存"}
            </Button>
            <Button size="sm" variant="outline" className="h-7 rounded-lg border-border/70 bg-black text-xs" onClick={() => void test()}>
              <Radio className="mr-1.5 h-3.5 w-3.5" />
              测试连接
            </Button>
          </div>
        </CardContent>
      </Card>

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        模型配置写入 <code className="font-mono">config.yaml</code> 的 <code className="font-mono">model</code> 与{" "}
        <code className="font-mono">agent</code> 字段，与 Hermes 运行时互通。
      </p>
    </div>
  )
}

/* ── Tab 2: MCP 服务 ───────────────────────────────────────────────────────── */

const STATUS_META: Record<string, string> = {
  active: "hm-pill--active",
  configured: "hm-pill--active",
  disabled: "hm-pill--muted",
  invalid_config: "hm-pill--warn",
  unknown: "hm-pill--muted",
}

function McpPanel({ baseUrl, refreshKey, toast }: { baseUrl: string; refreshKey: number; toast: any }) {
  const [loading, setLoading] = useState(true)
  const [servers, setServers] = useState<McpServer[]>([])
  const [toggling, setToggling] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    const data = await apiGet<McpServerPayload>(baseUrl, "hermes/mcp/servers")
    setServers(data?.servers || [])
    setLoading(false)
  }, [baseUrl])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  const toggle = useCallback(async (name: string, enabled: boolean) => {
    setToggling(name)
    const ok = await apiPatch(baseUrl, `hermes/mcp/servers/${encodeURIComponent(name)}`, { enabled })
    setToggling(null)
    if (!ok) {
      toast({ variant: "destructive", title: "切换失败", description: `无法更新 MCP server "${name}"。` })
      return
    }
    setServers((prev) => prev.map((s) => (s.name === name ? { ...s, enabled, status: enabled ? "configured" : "disabled" } : s)))
    toast({ title: enabled ? "已启用" : "已停用", description: `MCP server "${name}"。` })
  }, [baseUrl, toast])

  return (
    <div className="mx-auto max-w-3xl space-y-3">
      {loading && (
        <div className="py-10 text-center text-sm text-muted-foreground">
          <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin" />
          加载 MCP 服务…
        </div>
      )}

      {!loading && servers.length === 0 && (
        <div className="rounded-lg border border-border/70 bg-card/40 py-10 text-center text-sm text-muted-foreground">
          尚未配置 MCP 服务
        </div>
      )}

      {!loading &&
        servers.map((s) => (
          <div key={s.name} className="rounded-lg border border-border/70 bg-card/40 p-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[12px] font-semibold text-foreground">{s.name}</span>
              <span className={cn("hm-pill hm-pill--mono", s.transport === "http" ? "hm-pill--active" : s.transport === "stdio" ? "hm-pill--warn" : "hm-pill--muted")}>
                {s.transport}
              </span>
              <span className={cn("hm-pill", STATUS_META[s.status] || "hm-pill--muted")}>{s.status}</span>
            </div>
            <div className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
              {s.transport === "http" ? s.url : s.command ? `${s.command} ${(s.args || []).join(" ")}` : "无效配置"}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground">{s.env ? Object.keys(s.env).length : 0} 个环境变量</span>
              <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
                {s.enabled ? "Enabled" : "Disabled"}
                <Switch
                  checked={s.enabled}
                  disabled={toggling === s.name}
                  onCheckedChange={(checked) => void toggle(s.name, checked)}
                />
              </label>
            </div>
          </div>
        ))}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        只读列表，与 Hermes 的 <code className="font-mono">mcp_servers</code> 配置共享。启停直接写入 config.yaml。
      </p>
    </div>
  )
}

/* ── Tab 3: 插件 ───────────────────────────────────────────────────────────── */

function PluginPanel({ baseUrl, refreshKey, toast }: { baseUrl: string; refreshKey: number; toast: any }) {
  const [loading, setLoading] = useState(true)
  const [plugins, setPlugins] = useState<PluginEntry[]>([])
  const [toggling, setToggling] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    const data = await apiGet<PluginPayload>(baseUrl, "hermes/plugins")
    setPlugins(data?.plugins || [])
    setLoading(false)
  }, [baseUrl])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  const toggle = useCallback(async (name: string, enabled: boolean) => {
    setToggling(name)
    const ok = await apiPatch(baseUrl, `hermes/plugins/${encodeURIComponent(name)}`, { enabled })
    setToggling(null)
    if (!ok) {
      toast({ variant: "destructive", title: "切换失败", description: `无法更新插件 "${name}"。` })
      return
    }
    setPlugins((prev) =>
      prev.map((p) =>
        p.name === name
          ? { ...p, enabled, activation: enabled ? "enabled" : "disabled" }
          : p
      )
    )
    toast({ title: enabled ? "已启用" : "已停用", description: `插件 "${name}"。` })
  }, [baseUrl, toast])

  return (
    <div className="mx-auto max-w-3xl space-y-3">
      {loading && (
        <div className="py-10 text-center text-sm text-muted-foreground">
          <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin" />
          加载插件…
        </div>
      )}

      {!loading && plugins.length === 0 && (
        <div className="rounded-lg border border-border/70 bg-card/40 py-10 text-center text-sm text-muted-foreground">
          尚未配置插件
        </div>
      )}

      {!loading &&
        plugins.map((p) => {
          const active = p.activation === "enabled" || p.activation === "exclusive" || p.activation === "provider"
          return (
            <div key={p.name} className="rounded-lg border border-border/70 bg-card/40 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Puzzle className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate font-mono text-[12px] font-semibold text-foreground">{p.name}</span>
                  {p.version && <span className="text-[11px] text-muted-foreground">v{p.version}</span>}
                </div>
                <span className={cn("hm-pill", active ? "hm-pill--active" : "hm-pill--muted")}>
                  {active ? "enabled" : "disabled"}
                </span>
              </div>
              {p.description && <p className="mt-1 text-[12px] text-muted-foreground">{p.description}</p>}
              {p.hooks.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {p.hooks.map((h) => (
                    <span key={h} className="hm-pill hm-pill--mono">{h}</span>
                  ))}
                </div>
              )}
              <div className="mt-2 flex items-center justify-end border-t border-border/45 pt-2">
                <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
                  {active ? "已启用" : "已停用"}
                  <Switch
                    checked={active}
                    disabled={toggling === p.name}
                    onCheckedChange={(checked) => void toggle(p.name, checked)}
                  />
                </label>
              </div>
            </div>
          )
        })}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        复用 Hermes <code className="font-mono">plugins.enabled/disabled</code> 语义，启停与 Hermes 运行时互通。
      </p>
    </div>
  )
}
