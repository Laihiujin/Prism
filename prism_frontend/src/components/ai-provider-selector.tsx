import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { RefreshCw, CheckCircle2, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface ProviderHealthCheck {
  provider: string
  status: "success" | "failed" | "loading" | "idle"
  message?: string
  models?: Array<{
    id: string
    name: string
    max_tokens?: number
  }>
  lastChecked?: string
}

export function AIProviderSelector() {
  const [providers, setProviders] = useState<ProviderHealthCheck[]>([
    { provider: "siliconflow", status: "idle", message: "未检测" },
    { provider: "volcanoengine", status: "idle", message: "未检测" },
    { provider: "tongyi", status: "idle", message: "未检测" },
  ])
  const [isChecking, setIsChecking] = useState(false)

  const providerInfo = {
    siliconflow: { name: "硅基流动", emoji: "🚀", color: "bg-orange-500/20 text-orange-200" },
    volcanoengine: { name: "火山引擎", emoji: "🌋", color: "bg-red-500/20 text-red-200" },
    tongyi: { name: "通义千问", emoji: "💙", color: "bg-blue-500/20 text-blue-200" },
  }

  const checkProviders = async () => {
    setIsChecking(true)
    try {
      // 并行检测所有提供商
      const results = await Promise.allSettled(
        providers.map(async (p) => {
          const result: ProviderHealthCheck = {
            ...p,
            status: "loading",
          }

          try {
            const response = await fetch("/api/v1/ai/health-check", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
            })
            const data = await response.json()

            if (data.health_check_results && data.health_check_results[p.provider]) {
              const healthData = data.health_check_results[p.provider]
              result.status = healthData.status === "success" ? "success" : "failed"
              result.message = healthData.status === "success" ? "连接成功" : "连接失败"
            } else {
              result.status = "failed"
              result.message = "无法获取检测结果"
            }
          } catch (error) {
            result.status = "failed"
            result.message = `错误: ${error instanceof Error ? error.message : "未知错误"}`
          }

          result.lastChecked = new Date().toLocaleTimeString("zh-CN")
          return result
        })
      )

      const updatedProviders = providers.map((p, idx) => {
        const result = results[idx]
        if (result.status === "fulfilled") {
          return result.value
        }
        return {
          ...p,
          status: "failed" as const,
          message: "检测失败",
        }
      })

      setProviders(updatedProviders)

      // 如果检测成功，获取模型列表
      const successProviders = updatedProviders.filter((p) => p.status === "success")
      if (successProviders.length > 0) {
        try {
          const modelsResponse = await fetch("/api/v1/ai/models")
          const modelsData = await modelsResponse.json()

          if (modelsData.providers) {
            setProviders((prev) =>
              prev.map((p) => {
                const providerModels = modelsData.providers[p.provider]?.models || []
                return {
                  ...p,
                  models: providerModels.map((m: any) => ({
                    id: m.model_id,
                    name: m.name,
                    max_tokens: m.max_tokens,
                  })),
                }
              })
            )
          }
        } catch (error) {
          console.error("Failed to fetch models:", error)
        }
      }
    } finally {
      setIsChecking(false)
    }
  }

  useEffect(() => {
    // 组件挂载时自动检测
    checkProviders()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">AI 提供商检测</h3>
        <Button
          size="sm"
          onClick={checkProviders}
          disabled={isChecking}
          className="gap-2 bg-blue-600 hover:bg-blue-700"
        >
          <RefreshCw className={cn("h-4 w-4", isChecking && "animate-spin")} />
          刷新检测
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {providers.map((provider) => {
          const info = providerInfo[provider.provider as keyof typeof providerInfo]
          const isSuccess = provider.status === "success"

          return (
            <Card
              key={provider.provider}
              className={cn(
                "p-4 border transition-all",
                isSuccess
                  ? "bg-green-500/10 border-green-500/30"
                  : provider.status === "loading"
                    ? "bg-yellow-500/10 border-yellow-500/30"
                    : provider.status === "failed"
                      ? "bg-red-500/10 border-red-500/30"
                      : "bg-white/5 border-white/10"
              )}
            >
              <div className="space-y-3">
                {/* 提供商信息 */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{info.emoji}</span>
                    <div>
                      <div className="font-medium text-white">{info.name}</div>
                      <div className="text-xs text-white/50">{provider.provider}</div>
                    </div>
                  </div>

                  {/* 状态徽章 */}
                  <Badge
                    className={cn(
                      "gap-1.5",
                      isSuccess
                        ? "bg-green-500/30 text-green-200"
                        : provider.status === "loading"
                          ? "bg-yellow-500/30 text-yellow-200"
                          : provider.status === "failed"
                            ? "bg-red-500/30 text-red-200"
                            : "bg-gray-500/30 text-gray-200"
                    )}
                  >
                    {provider.status === "success" && (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        连接成功
                      </>
                    )}
                    {provider.status === "loading" && (
                      <>
                        <div className="h-3.5 w-3.5 rounded-full border-2 border-current border-r-transparent animate-spin" />
                        检测中...
                      </>
                    )}
                    {provider.status === "failed" && (
                      <>
                        <AlertCircle className="h-3.5 w-3.5" />
                        连接失败
                      </>
                    )}
                    {provider.status === "idle" && <>未检测</>}
                  </Badge>
                </div>

                {/* 消息和时间 */}
                {provider.message && (
                  <div className="text-sm text-white/70">
                    {provider.message}
                    {provider.lastChecked && (
                      <span className="text-white/50 ml-2">({provider.lastChecked})</span>
                    )}
                  </div>
                )}

                {/* 模型列表 */}
                {isSuccess && provider.models && provider.models.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-white/10">
                    <div className="text-xs font-semibold text-white/70 uppercase">可用模型</div>
                    <div className="flex flex-wrap gap-2">
                      {provider.models.map((model) => (
                        <Badge
                          key={model.id}
                          variant="secondary"
                          className="bg-white/10 text-white/80 text-xs"
                        >
                          <span className="truncate max-w-[150px]">{model.name}</span>
                          {model.max_tokens && (
                            <span className="text-white/50 ml-1">({model.max_tokens}k)</span>
                          )}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )
        })}
      </div>


    </div>
  )
}
