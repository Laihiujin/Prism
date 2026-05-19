"use client"

import { useCallback, useEffect, useState } from "react"
import { ChevronDown, Loader2, RefreshCw, Save, TestTube2, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
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
import { cn } from "@/lib/utils"

type ServiceType = "cover_generation" | "video_generation" | "speech_recognition"

type ProviderOption = {
  value: string
  label: string
}

type AIModelConfigResponse = {
  service_type: string
  provider: string
  api_key: string
  base_url?: string | null
  model_name?: string | null
  extra_config?: Record<string, unknown> | null
  is_active?: boolean
}

type ServiceFormState = {
  provider: string
  modelName: string
  baseUrl: string
  apiKey: string
}

type AIServiceProviderCardProps = {
  serviceType: ServiceType
  title: string
  description: string
  note?: string
  providerOptions: ProviderOption[]
  defaultOpen?: boolean
}

const DEFAULT_BASE_URLS: Record<ServiceType, Partial<Record<string, string>>> = {
  cover_generation: {
    siliconflow: "https://api.siliconflow.cn/v1",
    volcengine: "https://ark.cn-beijing.volces.com/api/v3",
    openai: "https://api.openai.com/v1",
    openai_compatible: "https://api.openai.com/v1",
  },
  video_generation: {
    runwayml: "https://api.runwayml.com/v1",
    siliconflow: "https://api.siliconflow.cn/v1",
    openai: "https://api.openai.com/v1",
    openai_compatible: "https://api.openai.com/v1",
  },
  speech_recognition: {
    siliconflow: "https://api.siliconflow.cn/v1",
    volcengine: "https://ark.cn-beijing.volces.com/api/v3",
    openai: "https://api.openai.com/v1",
    openai_compatible: "https://api.openai.com/v1",
  },
}

function buildDefaultForm(providerOptions: ProviderOption[]): ServiceFormState {
  return {
    provider: providerOptions[0]?.value || "openai_compatible",
    modelName: "",
    baseUrl: "",
    apiKey: "",
  }
}

export function AIServiceProviderCard({
  serviceType,
  title,
  description,
  note,
  providerOptions,
  defaultOpen = false,
}: AIServiceProviderCardProps) {
  const { toast } = useToast()
  const [open, setOpen] = useState(defaultOpen)
  const [form, setForm] = useState<ServiceFormState>(() => buildDefaultForm(providerOptions))
  const [savedConfig, setSavedConfig] = useState<AIModelConfigResponse | null>(null)
  const [loading, setLoading] = useState({
    hydrate: false,
    save: false,
    test: false,
    clear: false,
  })

  const setField = useCallback(<K extends keyof ServiceFormState>(key: K, value: ServiceFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }, [])

  const hydrate = useCallback(async () => {
    setLoading((prev) => ({ ...prev, hydrate: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.aiModelConfigs}/${serviceType}`)
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.detail || "读取配置失败")
      }

      const data = (payload?.data || null) as AIModelConfigResponse | null
      setSavedConfig(data)

      if (data) {
        setForm({
          provider: data.provider || providerOptions[0]?.value || "openai_compatible",
          modelName: data.model_name || "",
          baseUrl: data.base_url || "",
          apiKey: data.api_key || "",
        })
      } else {
        setForm(buildDefaultForm(providerOptions))
      }
    } catch (error) {
      console.error(`Failed to load ${serviceType} config:`, error)
      toast({
        title: `${title}配置读取失败`,
        description: error instanceof Error ? error.message : String(error),
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, hydrate: false }))
    }
  }, [providerOptions, serviceType, title, toast])

  useEffect(() => {
    void hydrate()
  }, [hydrate])

  const resolvedBaseUrl =
    form.baseUrl.trim() || DEFAULT_BASE_URLS[serviceType][form.provider] || ""

  const saveConfig = useCallback(async () => {
    if (!form.modelName.trim()) {
      toast({
        title: "模型名称不能为空",
        description: `请填写${title}对应的默认模型。`,
        variant: "destructive",
      })
      return
    }

    if (!form.apiKey.trim()) {
      toast({
        title: "API Key 不能为空",
        description: `请填写${title}提供商的认证信息。`,
        variant: "destructive",
      })
      return
    }

    setLoading((prev) => ({ ...prev, save: true }))
    try {
      const response = await fetch(API_ENDPOINTS.aiModelConfigs, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_type: serviceType,
          provider: form.provider,
          api_key: form.apiKey.trim(),
          base_url: form.baseUrl.trim() || null,
          model_name: form.modelName.trim(),
          extra_config: {},
          is_active: true,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "保存失败")
      }

      await hydrate()
      toast({
        title: `${title}已保存`,
        description: "新的提供商和模型配置已经写入系统设置。",
      })
    } catch (error) {
      toast({
        title: "保存失败",
        description: error instanceof Error ? error.message : String(error),
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, save: false }))
    }
  }, [form, hydrate, serviceType, title, toast])

  const testConfig = useCallback(async () => {
    if (!form.modelName.trim()) {
      toast({
        title: "模型名称不能为空",
        description: "测试连接前先填写模型名称。",
        variant: "destructive",
      })
      return
    }

    if (!form.apiKey.trim()) {
      toast({
        title: "API Key 不能为空",
        description: "测试连接前先填写 API Key。",
        variant: "destructive",
      })
      return
    }

    if (!resolvedBaseUrl) {
      toast({
        title: "Base URL 不能为空",
        description: "当前提供商没有默认地址，请手动填写 Base URL。",
        variant: "destructive",
      })
      return
    }

    setLoading((prev) => ({ ...prev, test: true }))
    try {
      const response = await fetch(API_ENDPOINTS.aiTestConnection, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_type: serviceType,
          provider: form.provider,
          api_key: form.apiKey.trim(),
          base_url: resolvedBaseUrl,
          model_name: form.modelName.trim(),
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload?.connected === false) {
        throw new Error(payload?.detail || payload?.message || "连接测试失败")
      }

      toast({
        title: `${title}连接正常`,
        description: payload?.message || "提供商与模型接口已经连通。",
      })
    } catch (error) {
      toast({
        title: "连接测试失败",
        description: error instanceof Error ? error.message : String(error),
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, test: false }))
    }
  }, [form, resolvedBaseUrl, serviceType, title, toast])

  const clearConfig = useCallback(async () => {
    setLoading((prev) => ({ ...prev, clear: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.aiModelConfigs}/${serviceType}`, {
        method: "DELETE",
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "清除失败")
      }

      setSavedConfig(null)
      setForm(buildDefaultForm(providerOptions))
      toast({
        title: `${title}已清除`,
        description: "当前服务的模型提供商配置已经删除。",
      })
    } catch (error) {
      toast({
        title: "清除失败",
        description: error instanceof Error ? error.message : String(error),
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, clear: false }))
    }
  }, [providerOptions, serviceType, title, toast])

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="border-white/10 bg-black">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-start justify-between gap-4 rounded-2xl px-5 py-4 text-left transition-colors hover:bg-white/5"
          >
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-medium text-white">{title}</div>
                <Badge
                  variant="outline"
                  className={savedConfig ? "border-white/20 bg-white/10 text-white" : "border-white/10 bg-black text-white/55"}
                >
                  {savedConfig ? "已配置" : "未配置"}
                </Badge>
              </div>
              <p className="text-xs leading-5 text-white/60">{description}</p>
            </div>
            <ChevronDown
              className={cn(
                "mt-0.5 h-4 w-4 shrink-0 text-white/55 transition-transform",
                open && "rotate-180"
              )}
            />
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="space-y-5 border-t border-white/10 pt-5">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor={`${serviceType}-provider`}>提供商</Label>
                <Select value={form.provider} onValueChange={(value) => setField("provider", value)}>
                  <SelectTrigger id={`${serviceType}-provider`}>
                    <SelectValue placeholder="选择提供商" />
                  </SelectTrigger>
                  <SelectContent>
                    {providerOptions.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor={`${serviceType}-model`}>默认模型</Label>
                <Input
                  id={`${serviceType}-model`}
                  value={form.modelName}
                  onChange={(event) => setField("modelName", event.target.value)}
                  placeholder="填写实际调用的模型名"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor={`${serviceType}-base-url`}>Base URL</Label>
                <Input
                  id={`${serviceType}-base-url`}
                  value={form.baseUrl}
                  onChange={(event) => setField("baseUrl", event.target.value)}
                  placeholder={DEFAULT_BASE_URLS[serviceType][form.provider] || "https://api.example.com/v1"}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor={`${serviceType}-api-key`}>API Key</Label>
                <Input
                  id={`${serviceType}-api-key`}
                  type="password"
                  value={form.apiKey}
                  onChange={(event) => setField("apiKey", event.target.value)}
                  placeholder="sk-..."
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-black p-4">
                <div className="text-[11px] uppercase tracking-[0.2em] text-white/40">当前提供商</div>
                <div className="mt-2 text-sm font-medium text-white">{savedConfig?.provider || form.provider || "-"}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black p-4">
                <div className="text-[11px] uppercase tracking-[0.2em] text-white/40">当前模型</div>
                <div className="mt-2 break-all text-sm text-white/80">{savedConfig?.model_name || form.modelName || "-"}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black p-4">
                <div className="text-[11px] uppercase tracking-[0.2em] text-white/40">测试地址</div>
                <div className="mt-2 break-all text-sm text-white/80">{resolvedBaseUrl || "未填写"}</div>
              </div>
            </div>

            {note ? (
              <div className="rounded-xl border border-dashed border-white/10 bg-black px-4 py-3 text-xs leading-5 text-white/55">
                {note}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={() => void saveConfig()}
                disabled={loading.save}
                className="border-white/20 bg-white/10 text-white hover:bg-white/15"
              >
                {loading.save ? <Loader2 className="animate-spin" /> : <Save />}
                保存配置
              </Button>
              <Button
                variant="secondary"
                className="border-white/10 bg-black text-white hover:bg-white/5"
                onClick={() => void testConfig()}
                disabled={loading.test}
              >
                {loading.test ? <Loader2 className="animate-spin" /> : <TestTube2 />}
                测试连接
              </Button>
              <Button
                variant="secondary"
                className="border-white/10 bg-black text-white hover:bg-white/5"
                onClick={() => void hydrate()}
                disabled={loading.hydrate}
              >
                {loading.hydrate ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                刷新
              </Button>
              <Button
                variant="secondary"
                className="border-white/10 bg-black text-white/70 hover:bg-white/5"
                onClick={() => void clearConfig()}
                disabled={loading.clear || !savedConfig}
              >
                {loading.clear ? <Loader2 className="animate-spin" /> : <Trash2 />}
                清除
              </Button>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}
