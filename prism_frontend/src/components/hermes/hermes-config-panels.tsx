"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Puzzle, Server } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

/* ── Types (mirror Hermes /api/mcp/servers, /api/plugins) ──────────────────── */

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

/* ── Helper: the backend wraps everything as { success, data } ─────────────── */

async function apiGet<T>(base: string, path: string): Promise<T | null> {
  const res = await fetch(`${base}/api/v1/agent/config/${path}`, { cache: "no-store" })
  if (!res.ok) return null
  const payload = await res.json().catch(() => null)
  return (payload?.data ?? null) as T | null
}

async function apiPatch(base: string, path: string, body: unknown): Promise<boolean> {
  const res = await fetch(`${base}/api/v1/agent/config/${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const payload = await res.json().catch(() => null)
  return res.ok && payload?.success !== false
}

function EmptyCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="col-span-full rounded-xl border border-border/70 bg-card/40 py-10 text-center text-sm text-muted-foreground">
      {children}
    </div>
  )
}

/* ── 本项目的 MCP（prism MCP server：把 Prism 业务工具暴露给 Hermes）──────── */

export function McpPanel({
  baseUrl,
  refreshKey,
  toast,
}: {
  baseUrl: string
  refreshKey: number
  toast: ReturnType<typeof useToast>["toast"]
}) {
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

  const toggle = useCallback(
    async (name: string, enabled: boolean) => {
      setToggling(name)
      const ok = await apiPatch(baseUrl, `hermes/mcp/servers/${encodeURIComponent(name)}`, { enabled })
      setToggling(null)
      if (!ok) {
        toast({ variant: "destructive", title: "切换失败", description: `无法更新 MCP server "${name}"。` })
        return
      }
      setServers((prev) => prev.map((s) => (s.name === name ? { ...s, enabled, status: enabled ? "configured" : "disabled" } : s)))
      toast({ title: enabled ? "已启用" : "已停用", description: `MCP server "${name}"。` })
    },
    [baseUrl, toast]
  )

  if (loading) {
    return (
      <EmptyCard>
        <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin" />
        加载 MCP 服务…
      </EmptyCard>
    )
  }

  if (servers.length === 0) {
    return <EmptyCard>尚未配置 MCP 服务</EmptyCard>
  }

  return (
    <>
      {servers.map((s) => (
        <Card key={s.name} className="bg-card/40 border-border/70">
          <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
            <div className="flex items-start gap-3">
              <div className="rounded-lg border border-white/17 bg-black p-2">
                <Server className="h-5 w-5" />
              </div>
              <div>
                <CardTitle className="text-base">{s.name}</CardTitle>
                <p className="mt-0.5 break-all font-mono text-xs text-muted-foreground">
                  {s.transport === "http" ? s.url : s.command ? `${s.command} ${(s.args || []).join(" ")}` : "无效配置"}
                </p>
              </div>
            </div>
            <Badge
              variant="secondary"
              className={cn("shrink-0 text-xs", s.enabled ? "bg-black text-white border-border" : "bg-muted text-muted-foreground")}
            >
              {s.enabled ? "运行中" : "已停用"}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="outline" className="text-xs">MCP</Badge>
                <code className="font-mono text-[10px]">{s.transport}</code>
                {s.env && <span>{Object.keys(s.env).length} 个环境变量</span>}
              </div>
              <div className="flex flex-wrap items-center justify-between border-t border-border/45 pt-2">
                <span className="text-[11px] text-muted-foreground">{s.status}</span>
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
          </CardContent>
        </Card>
      ))}
    </>
  )
}

/* ── 插件（Hermes 运行时 plugins 启停，随 config.yaml 同步）──────────────────── */

export function PluginPanel({
  baseUrl,
  refreshKey,
  toast,
}: {
  baseUrl: string
  refreshKey: number
  toast: ReturnType<typeof useToast>["toast"]
}) {
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

  const toggle = useCallback(
    async (name: string, enabled: boolean) => {
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
    },
    [baseUrl, toast]
  )

  if (loading) {
    return (
      <EmptyCard>
        <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin" />
        加载插件…
      </EmptyCard>
    )
  }

  if (plugins.length === 0) {
    return <EmptyCard>尚未配置插件</EmptyCard>
  }

  return (
    <>
      {plugins.map((p) => {
        const active = p.activation === "enabled" || p.activation === "exclusive" || p.activation === "provider"
        return (
          <Card key={p.name} className="bg-card/40 border-border/70">
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
              <div className="flex items-start gap-3">
                <div className="rounded-lg border border-white/17 bg-black p-2">
                  <Puzzle className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-base">{p.name}</CardTitle>
                  {p.description && <p className="mt-0.5 text-xs text-muted-foreground">{p.description}</p>}
                </div>
              </div>
              <Badge
                variant="secondary"
                className={cn("shrink-0 text-xs", active ? "bg-black text-white border-border" : "bg-muted text-muted-foreground")}
              >
                {active ? "已启用" : "已停用"}
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline" className="text-xs">插件</Badge>
                  {p.version && <code className="font-mono text-[10px]">v{p.version}</code>}
                  {p.hooks.map((h) => (
                    <span key={h} className="font-mono text-[10px]">{h}</span>
                  ))}
                </div>
                <div className="flex flex-wrap items-center justify-between border-t border-border/45 pt-2">
                  <span className="text-[11px] text-muted-foreground">{p.activation}</span>
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
            </CardContent>
          </Card>
        )
      })}
    </>
  )
}
