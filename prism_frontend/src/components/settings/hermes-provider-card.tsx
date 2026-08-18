"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Loader2, RefreshCw, Save, TestTube2, Trash2 } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useToast } from "@/components/ui/use-toast"
import { API_ENDPOINTS } from "@/lib/env"

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
  const [form, setForm] = useState<HermesFormState>(DEFAULT_FORM)
  const [savedConfig, setSavedConfig] = useState<HermesConfigResponse | null>(null)
  const [loading, setLoading] = useState({
    hydrate: false,
    save: false,
    test: false,
    clear: false,
  })

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
        title: "Hermes 模型已保存",
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
    setLoading((prev) => ({ ...prev, test: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.base}/api/v1/agent/config/hermes/test`, {
        method: "POST",
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.data?.message || payload?.detail || payload?.error || "测试失败")
      }
      toast({
        title: "Hermes 连接正常",
        description: payload?.data?.test_result || "运行时已能调用当前模型。",
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
  }, [toast])

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
        title: "Hermes 配置已清除",
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
    <Card className="border-white/10 bg-white/0">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-white">
          Hermes 模型提供商
        </CardTitle>
        <CardDescription className="text-white/60">
          在系统页直接维护 Hermes Agent 的 provider、模型、API Key 和最大轮次，不再依赖旧的 Agent 设置页。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
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
            <Input
              id="hermes-model"
              value={form.model}
              onChange={(event) => setField("model", event.target.value)}
              placeholder="gpt-4.1 / claude-sonnet-4-5 / qwen-max"
            />
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
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-white/40">当前提供商</div>
            <div className="mt-2 text-sm font-medium text-white">{savedConfig?.provider || providerLabel}</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-white/40">Hermes Home</div>
            <div className="mt-2 break-all text-sm text-white/80">{savedConfig?.runtime?.home_path || "未检测到"}</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-white/40">Dashboard</div>
            <div className="mt-2 break-all text-sm text-white/80">{dashboardUrl}</div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => void saveConfig()} disabled={loading.save}>
            {loading.save ? <Loader2 className="animate-spin" /> : <Save />}
            保存模型配置
          </Button>
          <Button variant="secondary" className="bg-white/10" onClick={() => void testConfig()} disabled={loading.test}>
            {loading.test ? <Loader2 className="animate-spin" /> : <TestTube2 />}
            测试连接
          </Button>
          <Button variant="secondary" className="bg-white/10" onClick={() => void hydrate()} disabled={loading.hydrate}>
            {loading.hydrate ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            刷新
          </Button>
          <Button variant="destructive" onClick={() => void clearConfig()} disabled={loading.clear}>
            {loading.clear ? <Loader2 className="animate-spin" /> : <Trash2 />}
            清除配置
          </Button>
        </div>

      </CardContent>
    </Card>
  )
}
