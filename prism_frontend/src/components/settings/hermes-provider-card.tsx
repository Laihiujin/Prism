"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ChevronDown, Loader2, RefreshCw, Save, TestTube2, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
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

type HermesConfigResponse = {
  provider?: string | null
  model?: string | null
  base_url?: string | null
  api_key?: string | null
  max_turns?: number
  is_configured?: boolean
  runtime?: {
    dashboard_url?: string
    home_path?: string
    dashboard_backend?: "official" | "webui" | null
    preferred_dashboard_backend?: "official" | "webui" | null
    agent_installed?: boolean
  }
}

type HermesFormState = {
  provider: string
  model: string
  baseUrl: string
  apiKey: string
  maxTurns: string
}

const DEFAULT_FORM: HermesFormState = {
  provider: "custom",
  model: "",
  baseUrl: "",
  apiKey: "",
  maxTurns: "12",
}

const PROVIDER_OPTIONS = [
  { value: "lmstudio", label: "LM Studio" },
  { value: "custom", label: "OpenAI Compatible" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
  { value: "openrouter", label: "OpenRouter" },
]

export function HermesProviderCard() {
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [modelSearch, setModelSearch] = useState("")
  const [form, setForm] = useState<HermesFormState>(DEFAULT_FORM)
  const [savedConfig, setSavedConfig] = useState<HermesConfigResponse | null>(null)
  const [loading, setLoading] = useState({
    hydrate: false,
    save: false,
    test: false,
    clear: false,
  })

  const [models, setModels] = useState<string[]>([])
  const [modelStatus, setModelStatus] = useState("")
  const [fetchingModels, setFetchingModels] = useState(false)
  const modelRequest = useRef<AbortController | null>(null)

  const setField = useCallback(<K extends keyof HermesFormState>(key: K, value: HermesFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }, [])

  const hydrate = useCallback(async () => {
    setLoading((prev) => ({ ...prev, hydrate: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.base}/api/v1/agent/config/hermes`)
      const payload = await response.json()
      const data = (payload?.data || null) as HermesConfigResponse | null
      setSavedConfig(data)
      if (data) {
        setForm({
          provider: data.provider || "custom",
          model: data.model || "",
          baseUrl: data.base_url || "",
          apiKey: data.api_key || "",
          maxTurns: String(data.max_turns || 12),
        })
      } else {
        setForm(DEFAULT_FORM)
      }
    } catch (error) {
      console.error("Failed to load Hermes config:", error)
      toast({
        title: "Hermes 配置读取失败",
        description: "无法读取当前模型提供商配置。",
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, hydrate: false }))
    }
  }, [toast])

  useEffect(() => {
    void hydrate()
  }, [hydrate])

  const providerLabel = useMemo(() => {
    return PROVIDER_OPTIONS.find((item) => item.value === form.provider)?.label || form.provider
  }, [form.provider])

  const resolvedBaseUrl = form.baseUrl.trim() || ({
    openai: "https://api.openai.com/v1",
    openrouter: "https://openrouter.ai/api/v1",
    lmstudio: "http://127.0.0.1:1234/v1",
  } as Record<string, string>)[form.provider] || ""

  const fetchModels = useCallback(async () => {
    if (!resolvedBaseUrl) {
      setModelStatus("请先填写提供商的 Base URL。")
      return
    }
    modelRequest.current?.abort()
    const controller = new AbortController()
    modelRequest.current = controller
    setFetchingModels(true)
    setModels([])
    setModelStatus("")
    try {
      const response = await fetch(`${API_ENDPOINTS.aiModels}/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_url: resolvedBaseUrl, api_key: form.apiKey.trim() }),
        signal: controller.signal,
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload?.detail || "模型列表获取失败")
      setModels(payload.data || [])
      setModelStatus(payload.data?.length ? `获取到 ${payload.data.length} 个模型，可选择或手动输入；请确认模型支持当前服务。` : "提供商返回的模型列表为空，可手动输入。")
    } catch (error) {
      if (!controller.signal.aborted) setModelStatus(error instanceof Error ? error.message : "模型列表获取失败，可手动输入。")
    } finally {
      if (!controller.signal.aborted) setFetchingModels(false)
    }
  }, [resolvedBaseUrl, form.apiKey])

  useEffect(() => {
    modelRequest.current?.abort()
    setModels([])
    setModelStatus("")
    setFetchingModels(false)
    if (!open || loading.hydrate || !resolvedBaseUrl || (!form.apiKey.trim() && form.provider !== "lmstudio")) return
    const timer = setTimeout(() => void fetchModels(), 700)
    return () => {
      clearTimeout(timer)
      modelRequest.current?.abort()
    }
  }, [open, loading.hydrate, resolvedBaseUrl, form.apiKey, form.provider, fetchModels])

  const saveConfig = useCallback(async () => {
    if (!form.model.trim()) {
      toast({
        title: "模型不能为空",
        description: "请填写 Hermes 默认模型。",
        variant: "destructive",
      })
      return
    }

    const maxTurns = Number(form.maxTurns || "12")
    if (!Number.isFinite(maxTurns) || maxTurns < 1 || maxTurns > 90) {
      toast({
        title: "最大轮次无效",
        description: "请输入 1 到 90 之间的整数。",
        variant: "destructive",
      })
      return
    }

    setLoading((prev) => ({ ...prev, save: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.base}/api/v1/agent/config/hermes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          llm: {
            provider: form.provider,
            model: form.model.trim(),
            api_key: form.apiKey.trim(),
            base_url: form.baseUrl.trim() || null,
          },
          runtime: {
            max_turns: maxTurns,
          },
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.detail || payload?.error || payload?.data?.message || "保存失败")
      }

      await hydrate()
      toast({
        title: "模型配置已保存",
        description: "系统页已经恢复独立的模型提供商配置入口。",
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      toast({
        title: "保存失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, save: false }))
    }
  }, [form, hydrate, toast])

  const testConfig = useCallback(async () => {
    if (!form.model.trim() || !resolvedBaseUrl) {
      toast({ title: "请填写模型和 Base URL", variant: "destructive" })
      return
    }
    setLoading((prev) => ({ ...prev, test: true }))
    try {
      const response = await fetch(API_ENDPOINTS.aiTestConnection, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_type: "chat",
          provider: form.provider,
          model_name: form.model.trim(),
          base_url: resolvedBaseUrl,
          api_key: form.apiKey.trim(),
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload?.connected !== true || payload?.status !== "success") {
        throw new Error(payload?.detail || payload?.message || "测试失败")
      }
      toast({
        title: "模型 API 连接正常",
        description: `${form.model}：${payload.response_preview || payload.message}`,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      toast({
        title: "连接测试失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, test: false }))
    }
  }, [form, resolvedBaseUrl, toast])

  const clearConfig = useCallback(async () => {
    setLoading((prev) => ({ ...prev, clear: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.base}/api/v1/agent/config/hermes`, {
        method: "DELETE",
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.detail || payload?.error || payload?.data?.message || "删除失败")
      }

      setForm(DEFAULT_FORM)
      await hydrate()
      toast({
        title: "模型配置已清除",
        description: "模型提供商已从本地运行时中移除。",
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      toast({
        title: "清除失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, clear: false }))
    }
  }, [hydrate, toast])

  const dashboardUrl =
    savedConfig?.runtime?.dashboard_url ||
    "http://127.0.0.1:9119"

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
                <div className="text-sm font-medium text-foreground">大语言模型配置</div>
                <Badge
                  variant="outline"
                  className={savedConfig ? "border-border/80 bg-black text-foreground" : "border-border/70 bg-card text-muted-foreground"}
                >
                  {savedConfig ? "已配置" : "未配置"}
                </Badge>
              </div>
              <p className="text-xs leading-5 text-muted-foreground">
                系统大语言模型（项目与 Hermes 共用）的 provider、模型、API Key 与最大轮次。
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
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="hermes-provider">提供商</Label>
                <Select value={form.provider} onValueChange={(value) => setField("provider", value)}>
                  <SelectTrigger id="hermes-provider">
                    <SelectValue placeholder="选择提供商" />
                  </SelectTrigger>
                  <SelectContent>
                    {PROVIDER_OPTIONS.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="hermes-model">默认模型</Label>
                <div className="flex items-center gap-2">
                  <div className="relative min-w-0 flex-1">
                    <Input
                      id="hermes-model"
                      value={form.model}
                      onChange={(event) => setField("model", event.target.value)}
                      placeholder="选择或手动输入模型名称"
                      className="pr-10"
                    />
                    <Popover open={modelPickerOpen} onOpenChange={(nextOpen) => {
                      setModelPickerOpen(nextOpen)
                      if (nextOpen) setModelSearch("")
                    }}>
                      <PopoverTrigger asChild>
                        <button type="button" aria-label="展开模型列表" className="absolute right-0 top-0 flex h-9 w-9 items-center justify-center text-foreground">
                          <ChevronDown className="h-4 w-4" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="end" className="w-80 max-w-[calc(100vw-2rem)] p-2">
                        <Input aria-label="搜索模型" placeholder="搜索模型…" value={modelSearch} onChange={(event) => setModelSearch(event.target.value)} />
                        <div className="mt-2 max-h-64 overflow-y-auto">
                          {models.filter((model) => model.toLowerCase().includes(modelSearch.toLowerCase())).map((model) => (
                            <button key={model} type="button" aria-pressed={form.model === model} className="block w-full break-all rounded px-3 py-2 text-left text-sm text-popover-foreground hover:bg-accent focus-visible:bg-accent" onClick={() => {
                              setField("model", model)
                              setModelPickerOpen(false)
                            }}>
                              {model}
                            </button>
                          ))}
                          {models.length === 0 ? <p className="px-3 py-2 text-xs text-muted-foreground">请先获取模型列表，也可以直接输入模型名称。</p> : null}
                          {models.length > 0 && !models.some((model) => model.toLowerCase().includes(modelSearch.toLowerCase())) ? <p className="px-3 py-2 text-xs text-muted-foreground">没有匹配的模型</p> : null}
                        </div>
                      </PopoverContent>
                    </Popover>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="shrink-0"
                    onClick={() => void fetchModels()}
                    disabled={fetchingModels || loading.hydrate}
                  >
                    {fetchingModels ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                    {fetchingModels ? "获取中…" : "获取模型"}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground" role="status">
                  {modelStatus || "填写 Base URL 和 API Key 后自动获取，也可点击获取模型。"}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="hermes-base-url">Base URL</Label>
                <Input
                  id="hermes-base-url"
                  value={form.baseUrl}
                  onChange={(event) => setField("baseUrl", event.target.value)}
                  placeholder="https://api.openai.com/v1"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="hermes-api-key">API Key</Label>
                <Input
                  id="hermes-api-key"
                  type="password"
                  value={form.apiKey}
                  onChange={(event) => setField("apiKey", event.target.value)}
                  placeholder="sk-..."
                />
              </div>

              <div className="space-y-2 md:max-w-[220px]">
                <Label htmlFor="hermes-max-turns">最大轮次</Label>
                <Input
                  id="hermes-max-turns"
                  type="number"
                  min={1}
                  max={90}
                  value={form.maxTurns}
                  onChange={(event) => setField("maxTurns", event.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-border/70 bg-card/30 p-4">
                <div className="text-xs uppercase tracking-[0.22em] text-foreground/40">当前提供商</div>
                <div className="mt-2 text-sm font-medium text-foreground">{savedConfig?.provider || providerLabel}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-card/30 p-4">
                <div className="text-xs uppercase tracking-[0.22em] text-foreground/40">Hermes Home</div>
                <div className="mt-2 break-all text-sm text-foreground/80">{savedConfig?.runtime?.home_path || "未检测到"}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-card/30 p-4">
                <div className="text-xs uppercase tracking-[0.22em] text-foreground/40">Dashboard</div>
                <div className="mt-2 break-all text-sm text-foreground/80">{dashboardUrl}</div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => void saveConfig()} disabled={loading.save}>
                {loading.save ? <Loader2 className="animate-spin" /> : <Save />}
                保存模型配置
              </Button>
              <Button variant="secondary" className="bg-foreground/10" onClick={() => void testConfig()} disabled={loading.test}>
                {loading.test ? <Loader2 className="animate-spin" /> : <TestTube2 />}
                测试连接
              </Button>
              <Button variant="secondary" className="bg-foreground/10" onClick={() => void hydrate()} disabled={loading.hydrate}>
                {loading.hydrate ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                刷新
              </Button>
              <Button variant="destructive" onClick={() => void clearConfig()} disabled={loading.clear}>
                {loading.clear ? <Loader2 className="animate-spin" /> : <Trash2 />}
                清除配置
              </Button>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}
