import React, { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Settings, Plus, Copy, Check } from "lucide-react"

interface AIProviderConfig {
  provider: string
  apiKey: string
  isActive: boolean
}

interface AIProviderSetupDialogProps {
  onProviderAdded?: (provider: string, apiKey: string) => Promise<boolean>
}

export function AIProviderSetupDialog({ onProviderAdded }: AIProviderSetupDialogProps) {
  const [open, setOpen] = useState(false)
  const [provider, setProvider] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const providerInfo = {
    siliconflow: {
      name: "硅基流动 (SiliconFlow)",
      icon: "🚀",
      description: "开源模型集合，支持通义千问、Llama、DeepSeek",
      link: "https://cloud.siliconflow.cn/",
      placeholder: "sk-xxxxxxxxxxxxxxxxxxxxxx",
    },
    volcanoengine: {
      name: "火山引擎 (VolcanoEngine)",
      icon: "🌋",
      description: "豆包系列模型，支持长文本和多模态",
      link: "https://www.volcengine.com/",
      placeholder: "ak-xxxxxxxxxxxxxxxxxxxxxx",
    },
    tongyi: {
      name: "通义万象 (Tongyi)",
      icon: "💙",
      description: "阿里云通义系列，最新千问模型",
      link: "https://dashscope.aliyuncs.com/",
      placeholder: "sk-xxxxxxxxxxxxxxxxxxxxxx",
    },
  }

  const selectedInfo = provider ? providerInfo[provider as keyof typeof providerInfo] : null

  const handleCopyLink = () => {
    if (selectedInfo?.link) {
      navigator.clipboard.writeText(selectedInfo.link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleAddProvider = async () => {
    if (!provider || !apiKey.trim()) {
      alert("请选择提供商并输入 API Key")
      return
    }

    setIsLoading(true)
    try {
      const success = await onProviderAdded?.(provider, apiKey)
      if (success) {
        setProvider("")
        setApiKey("")
        setOpen(false)
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2 rounded-2xl border-white/20 text-white">
          <Plus className="h-4 w-4" />
          添加 AI 提供商
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px] bg-gradient-to-br from-slate-900 to-slate-800 border-white/10">
        <DialogHeader>
          <DialogTitle className="text-white">配置 AI 提供商</DialogTitle>
          <DialogDescription className="text-white/60">
            选择并配置你想使用的 AI 服务提供商
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* 提供商选择 */}
          <div>
            <label className="text-sm font-medium text-white mb-2 block">选择提供商</label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="h-10 bg-white/10 border-white/20 text-white">
                <SelectValue placeholder="选择 AI 提供商..." />
              </SelectTrigger>
              <SelectContent className="bg-slate-900 border-white/10">
                {Object.entries(providerInfo).map(([key, info]) => (
                  <SelectItem key={key} value={key} className="text-white">
                    <span>{info.icon} {info.name}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 提供商信息 */}
          {selectedInfo && (
            <div className="bg-white/5 rounded-lg p-4 border border-white/10 space-y-3">
              <div>
                <p className="text-sm text-white/80">{selectedInfo.description}</p>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-white/60">获取 API Key:</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-2 text-blue-400 hover:text-blue-300"
                  onClick={handleCopyLink}
                >
                  {copied ? (
                    <>
                      <Check className="h-4 w-4" />
                      已复制
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      复制链接
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          {/* API Key 输入 */}
          <div>
            <label className="text-sm font-medium text-white mb-2 block">API Key</label>
            <Input
              placeholder={selectedInfo?.placeholder || "输入 API Key..."}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              type="password"
              className="h-10 bg-white/10 border-white/20 text-white placeholder:text-white/40"
              disabled={!provider}
            />
            <p className="text-xs text-white/50 mt-2">
              你的 API Key 将被安全保存，不会被上传到服务器
            </p>
          </div>

          {/* 提示信息 */}
          {provider && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
              <p className="text-xs text-yellow-200">
                💡 请确保 API Key 有足够的配额。首次使用建议先执行健康检查测试连接。
              </p>
            </div>
          )}
        </div>

        <div className="flex gap-3 justify-end">
          <Button
            variant="outline"
            className="border-white/20 text-white hover:bg-white/10"
            onClick={() => setOpen(false)}
          >
            取消
          </Button>
          <Button
            className="bg-blue-600 hover:bg-blue-700 text-white gap-2"
            onClick={handleAddProvider}
            disabled={isLoading || !provider || !apiKey.trim()}
          >
            {isLoading ? "添加中..." : "添加提供商"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
