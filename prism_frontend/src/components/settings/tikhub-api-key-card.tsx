"use client"

import { useCallback, useEffect, useState } from "react"
import { ChevronDown, KeyRound, Loader2, RefreshCw, Save, TestTube2, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/components/ui/use-toast"
import { API_ENDPOINTS } from "@/lib/env"
import { cn } from "@/lib/utils"

const DEFAULT_TIKHUB_BASE_URL = "https://api.tikhub.io"

type TikHubConfigResponse = {
  service_type: string
  provider: string
  api_key: string
  base_url?: string | null
  is_active?: boolean
}

type TikHubApiKeyCardProps = {
  defaultOpen?: boolean
}

export function TikHubApiKeyCard({ defaultOpen = false }: TikHubApiKeyCardProps) {
  const { toast } = useToast()
  const [open, setOpen] = useState(defaultOpen)
  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState(DEFAULT_TIKHUB_BASE_URL)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState({
    hydrate: false,
    save: false,
    test: false,
    clear: false,
  })

  const hydrate = useCallback(async () => {
    setLoading((prev) => ({ ...prev, hydrate: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.aiModelConfigs}/tikhub`)
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.detail || "读取配置失败")
      }

      const data = (payload?.data || null) as TikHubConfigResponse | null
      if (data) {
        setApiKey(data.api_key || "")
        setBaseUrl(data.base_url || DEFAULT_TIKHUB_BASE_URL)
        setSaved(Boolean(data.api_key))
      } else {
        setApiKey("")
        setBaseUrl(DEFAULT_TIKHUB_BASE_URL)
        setSaved(false)
      }
    } catch (error) {
      console.error("Failed to load TikHub config:", error)
      toast({
        title: "TikHub 配置读取失败",
        description: error instanceof Error ? error.message : String(error),
        variant: "destructive",
      })
    } finally {
      setLoading((prev) => ({ ...prev, hydrate: false }))
    }
  }, [toast])

  useEffect(() => {
    void hydrate()
  }, [hydrate])

  const saveConfig = useCallback(async () => {
    if (!apiKey.trim()) {
      toast({
        title: "API Key 不能为空",
        description: "请填写 TikHub 数据接口的 API Key。",
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
          service_type: "tikhub",
          provider: "tikhub",
          api_key: apiKey.trim(),
          base_url: baseUrl.trim() || null,
          model_name: "tikhub",
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
        title: "TikHub 配置已保存",
        description: "新的数据接口密钥已经写入系统设置。",
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
  }, [apiKey, baseUrl, hydrate, toast])

  const testConfig = useCallback(async () => {
    if (!apiKey.trim()) {
      toast({
        title: "API Key 不能为空",
        description: "测试连接前先填写 API Key。",
        variant: "destructive",
      })
      return
    }

    setLoading((prev) => ({ ...prev, test: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.base}/api/v1/tikhub/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey.trim(),
          base_url: baseUrl.trim() || null,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload?.connected === false) {
        throw new Error(payload?.detail || payload?.message || "连接测试失败")
      }

      toast({
        title: "TikHub 连接正常",
        description: payload?.message || "数据接口已经连通。",
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
  }, [apiKey, baseUrl, toast])

  const clearConfig = useCallback(async () => {
    setLoading((prev) => ({ ...prev, clear: true }))
    try {
      const response = await fetch(`${API_ENDPOINTS.aiModelConfigs}/tikhub`, {
        method: "DELETE",
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "清除失败")
      }

      setApiKey("")
      setBaseUrl(DEFAULT_TIKHUB_BASE_URL)
      setSaved(false)
      toast({
        title: "TikHub 配置已清除",
        description: "数据接口密钥已经删除。",
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
  }, [toast])

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="border-border/70 bg-card">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-start justify-between gap-4 rounded-2xl px-5 py-4 text-left transition-colors hover:bg-accent/40"
          >
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <KeyRound className="h-4 w-4 text-foreground/70" />
                  TikHub 数据接口
                </div>
                <Badge
                  variant="outline"
                  className={saved ? "border-border/80 bg-black text-foreground" : "border-border/70 bg-card text-muted-foreground"}
                >
                  {saved ? "已配置" : "未配置"}
                </Badge>
              </div>
              <p className="text-xs leading-5 text-muted-foreground">
                用于快手、小红书、视频号（及 B 站）等平台的作品数据采集。密钥保存在 ai_model_configs 的 tikhub 配置中。
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
                <Label htmlFor="tikhub-base-url">Base URL</Label>
                <Input
                  id="tikhub-base-url"
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  placeholder={DEFAULT_TIKHUB_BASE_URL}
                />
                <p className="text-[11px] text-muted-foreground">默认 https://api.tikhub.io，无需改动。</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="tikhub-api-key">API Key</Label>
                <Input
                  id="tikhub-api-key"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="tkh_..."
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={() => void saveConfig()}
                disabled={loading.save}
                className="border-border/80 bg-black text-foreground hover:bg-accent/50"
              >
                {loading.save ? <Loader2 className="animate-spin" /> : <Save />}
                保存配置
              </Button>
              <Button
                variant="secondary"
                className="border-border/70 bg-card text-foreground hover:bg-accent/40"
                onClick={() => void testConfig()}
                disabled={loading.test}
              >
                {loading.test ? <Loader2 className="animate-spin" /> : <TestTube2 />}
                测试连接
              </Button>
              <Button
                variant="secondary"
                className="border-border/70 bg-card text-foreground hover:bg-accent/40"
                onClick={() => void hydrate()}
                disabled={loading.hydrate}
              >
                {loading.hydrate ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                刷新
              </Button>
              <Button
                variant="secondary"
                className="border-border/70 bg-card text-foreground/70 hover:bg-accent/40"
                onClick={() => void clearConfig()}
                disabled={loading.clear || !saved}
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
