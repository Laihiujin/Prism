"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/components/ui/use-toast"
import { Loader2, Key, Sparkles, Check, AlertCircle, Zap, Eye } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Badge } from "@/components/ui/badge"

interface Provider {
  id: string
  name: string
  base_url: string
  models: Array<{
    id: string
    name: string
    description: string
  }>
  vision_models: Array<{
    id: string
    name: string
    description: string
  }>
}

interface ManusLLMConfig {
  provider: string
  api_key: string
  base_url?: string
  model: string
  max_tokens: number
  temperature: number
}

interface ManusVisionConfig {
  model: string
  base_url?: string
  api_key?: string
}

interface ManusConfig {
  llm: ManusLLMConfig
  vision?: ManusVisionConfig
}

interface ManusConfigResponse {
  provider?: string
  model?: string
  base_url?: string
  max_tokens: number
  temperature: number
  vision_model?: string
  vision_base_url?: string
  is_configured: boolean
}

const providerEmojis: Record<string, string> = {
  siliconflow: "🚀",
  volcanoengine: "🌋",
  tongyi: "💙",
  openai: "🤖",
  anthropic: "🧠"
}

export function OpenManusConfigCard() {
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [providers, setProviders] = useState<Record<string, Provider>>({})
  const [currentConfig, setCurrentConfig] = useState<ManusConfigResponse | null>(null)
  const [visionEnabled, setVisionEnabled] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)

  // 表单状态
  const [formData, setFormData] = useState<ManusConfig>({
    llm: {
      provider: "siliconflow",
      api_key: "",
      model: "",
      max_tokens: 16384,
      temperature: 0.6
    }
  })

  // 加载支持的 Providers
  useEffect(() => {
    loadProviders()
    loadCurrentConfig()
  }, [])

  const loadProviders = async () => {
    try {
      const response = await fetch("/api/v1/agent/config/providers")
      const data = await response.json()

      if (data.success) {
        setProviders(data.data.providers)

        // 设置默认模型
        if (data.data.providers.siliconflow) {
          setFormData(prev => ({
            ...prev,
            llm: {
              ...prev.llm,
              model: data.data.providers.siliconflow.models[0]?.id || ""
            }
          }))
        }
      }
    } catch (error) {
      console.error("加载 Providers 失败:", error)
    }
  }

  const loadCurrentConfig = async () => {
    setLoading(true)
    try {
      const response = await fetch("/api/v1/agent/config/manus")
      const data = await response.json()

      if (data.success && data.data.is_configured) {
        setCurrentConfig(data.data)

        // 更新表单（不包括 API Key）
        setFormData(prev => ({
          llm: {
            ...prev.llm,
            provider: data.data.provider || prev.llm.provider,
            model: data.data.model || prev.llm.model,
            base_url: data.data.base_url,
            max_tokens: data.data.max_tokens,
            temperature: data.data.temperature
          },
          vision: data.data.vision_model ? {
            model: data.data.vision_model,
            base_url: data.data.vision_base_url
          } : undefined
        }))

        setVisionEnabled(!!data.data.vision_model)
      }
    } catch (error) {
      console.error("加载配置失败:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleProviderChange = (provider: string) => {
    const providerInfo = providers[provider]
    if (!providerInfo) return

    setFormData(prev => ({
      ...prev,
      llm: {
        ...prev.llm,
        provider,
        base_url: providerInfo.base_url,
        model: providerInfo.models[0]?.id || ""
      }
    }))
  }

  const handleSave = async () => {
    if (!formData.llm.api_key) {
      toast({
        title: "配置错误",
        description: "请输入 API Key",
        variant: "destructive"
      })
      return
    }

    if (!formData.llm.model) {
      toast({
        title: "配置错误",
        description: "请选择模型",
        variant: "destructive"
      })
      return
    }

    setSaving(true)
    try {
      const payload: ManusConfig = {
        llm: formData.llm
      }

      if (visionEnabled && formData.vision?.model) {
        payload.vision = formData.vision
      }

      const response = await fetch("/api/v1/agent/config/manus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })

      const data = await response.json()

      if (data.success) {
        toast({
          title: "保存成功",
          description: "OpenManus 配置已保存"
        })
        await loadCurrentConfig()
      } else {
        throw new Error(data.error || "保存失败")
      }
    } catch (error: any) {
      toast({
        title: "保存失败",
        description: error.message,
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    try {
      const response = await fetch("/api/v1/agent/config/manus/test", {
        method: "POST"
      })

      const data = await response.json()

      if (data.success && data.data.status === "success") {
        toast({
          title: "✅ 测试成功",
          description: "OpenManus 配置有效，连接正常"
        })
      } else {
        throw new Error(data.data?.message || "测试失败")
      }
    } catch (error: any) {
      toast({
        title: "测试失败",
        description: error.message,
        variant: "destructive"
      })
    } finally {
      setTesting(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm("确定要删除 OpenManus 配置吗？")) return

    try {
      const response = await fetch("/api/v1/agent/config/manus", {
        method: "DELETE"
      })

      const data = await response.json()

      if (data.success) {
        toast({
          title: "配置已删除",
          description: "OpenManus 配置已清除"
        })
        setCurrentConfig(null)
        setFormData({
          llm: {
            provider: "siliconflow",
            api_key: "",
            model: providers.siliconflow?.models[0]?.id || "",
            max_tokens: 16384,
            temperature: 0.6
          }
        })
      }
    } catch (error: any) {
      toast({
        title: "删除失败",
        description: error.message,
        variant: "destructive"
      })
    }
  }

  const currentProvider = providers[formData.llm.provider]

  if (loading) {
    return (
      <Card className="bg-white/5 border-white/10">
        <CardContent className="py-12">
          <div className="flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="bg-white/5 border-white/10">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-orange-400" />
            <CardTitle>OpenManus Agent 配置</CardTitle>
          </div>
          {currentConfig?.is_configured && (
            <Badge variant="outline" className="bg-green-500/20 text-green-400 border-green-500/30">
              <Check className="w-3 h-3 mr-1" />
              已配置
            </Badge>
          )}
        </div>
        <CardDescription className="text-white/60">
          配置 OpenManus Agent 的独立 LLM，用于复杂任务编排和工具调用
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Provider 选择 */}
        <div className="space-y-2">
          <Label className="flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            服务提供商
          </Label>
          <div className="grid grid-cols-5 gap-2">
            {Object.keys(providers).map(providerId => (
              <button
                key={providerId}
                onClick={() => handleProviderChange(providerId)}
                className={`p-3 rounded-lg border-2 transition-all ${
                  formData.llm.provider === providerId
                    ? "border-primary bg-primary/10"
                    : "border-white/10 bg-white/5 hover:border-white/20"
                }`}
              >
                <div className="text-2xl mb-1">{providerEmojis[providerId]}</div>
                <div className="text-xs text-white/70 truncate">
                  {providers[providerId].name.split(" ")[0]}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* API Key */}
        <div className="space-y-2">
          <Label className="flex items-center gap-2">
            <Key className="w-4 h-4" />
            API Key
          </Label>
          <div className="relative">
            <Input
              type={showApiKey ? "text" : "password"}
              value={formData.llm.api_key}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                llm: { ...prev.llm, api_key: e.target.value }
              }))}
              placeholder="请输入 API Key"
              className="bg-white/5 border-white/10 text-white placeholder:text-white/40 pr-10"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70"
            >
              <Eye className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 模型选择 */}
        <div className="space-y-2">
          <Label>LLM 模型</Label>
          <select
            value={formData.llm.model}
            onChange={(e) => setFormData(prev => ({
              ...prev,
              llm: { ...prev.llm, model: e.target.value }
            }))}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {currentProvider?.models.map(model => (
              <option key={model.id} value={model.id} className="bg-neutral-900">
                {model.name} - {model.description}
              </option>
            ))}
          </select>
        </div>

        {/* Base URL (可选) */}
        {formData.llm.provider !== "siliconflow" && (
          <div className="space-y-2">
            <Label>API Base URL (可选)</Label>
            <Input
              value={formData.llm.base_url || ""}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                llm: { ...prev.llm, base_url: e.target.value }
              }))}
              placeholder={currentProvider?.base_url}
              className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
            />
          </div>
        )}

        {/* Max Tokens */}
        <div className="space-y-2">
          <div className="flex justify-between">
            <Label>Max Tokens</Label>
            <span className="text-sm text-white/60">{formData.llm.max_tokens}</span>
          </div>
          <Slider
            value={[formData.llm.max_tokens] as any}
            onValueChange={(values: any) => setFormData(prev => ({
              ...prev,
              llm: { ...prev.llm, max_tokens: values[0] }
            }))}
            min={1024}
            max={32768}
            step={1024}
            className="w-full"
          />
        </div>

        {/* Temperature */}
        <div className="space-y-2">
          <div className="flex justify-between">
            <Label>Temperature</Label>
            <span className="text-sm text-white/60">{formData.llm.temperature.toFixed(1)}</span>
          </div>
          <Slider
            value={[formData.llm.temperature * 10] as any}
            onValueChange={(values: any) => setFormData(prev => ({
              ...prev,
              llm: { ...prev.llm, temperature: values[0] / 10 }
            }))}
            min={0}
            max={20}
            step={1}
            className="w-full"
          />
        </div>

        {/* Vision 配置 (可折叠) */}
        {currentProvider?.vision_models && currentProvider.vision_models.length > 0 && (
          <Collapsible open={visionEnabled} onOpenChange={setVisionEnabled}>
            <div className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10">
              <div>
                <Label className="text-base">启用 Vision 模型</Label>
                <p className="text-sm text-white/60 mt-1">用于图像理解和分析</p>
              </div>
              <Switch
                checked={visionEnabled}
                onCheckedChange={setVisionEnabled}
              />
            </div>

            <CollapsibleContent className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label>Vision 模型</Label>
                <select
                  value={formData.vision?.model || ""}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    vision: {
                      ...prev.vision,
                      model: e.target.value
                    }
                  }))}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  {currentProvider.vision_models.map(model => (
                    <option key={model.id} value={model.id} className="bg-neutral-900">
                      {model.name} - {model.description}
                    </option>
                  ))}
                </select>
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-3 pt-4">
          <Button
            onClick={handleSave}
            disabled={saving || !formData.llm.api_key || !formData.llm.model}
            className="flex-1"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                保存中...
              </>
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                保存配置
              </>
            )}
          </Button>

          {currentConfig?.is_configured && (
            <>
              <Button
                onClick={handleTest}
                disabled={testing}
                variant="outline"
                className="bg-white/5 border-white/10"
              >
                {testing ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4 mr-2" />
                )}
                测试连接
              </Button>

              <Button
                onClick={handleDelete}
                variant="destructive"
              >
                清除
              </Button>
            </>
          )}
        </div>

        {/* 配置提示 */}
        {currentProvider && (
          <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-white/70 space-y-1">
                <p className="text-blue-400 font-medium">💡 配置提示</p>
                {formData.llm.provider === "siliconflow" && (
                  <>
                    <p>• 硅基流动官网：<a href="https://siliconflow.cn" target="_blank" className="text-blue-400 hover:underline">https://siliconflow.cn</a></p>
                    <p>• 推荐模型：Qwen/QwQ-32B (高性能推理)</p>
                  </>
                )}
                {formData.llm.provider === "volcanoengine" && (
                  <>
                    <p>• 火山引擎控制台获取 API Key</p>
                    <p>• 推荐模型：doubao-pro</p>
                  </>
                )}
                {formData.llm.provider === "tongyi" && (
                  <>
                    <p>• 阿里云：<a href="https://dashscope.aliyun.com" target="_blank" className="text-blue-400 hover:underline">https://dashscope.aliyun.com</a></p>
                    <p>• 推荐模型：qwen-max</p>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
