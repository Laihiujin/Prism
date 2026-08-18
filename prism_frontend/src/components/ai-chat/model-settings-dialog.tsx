"use client"

import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { RefreshCw, X } from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface ModelSettingsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function ModelSettingsDialog({ open, onOpenChange }: ModelSettingsDialogProps) {
    const [baseUrl, setBaseUrl] = useState("")
    const [apiKey, setApiKey] = useState("")
    const [selectedModel, setSelectedModel] = useState("")
    const [models, setModels] = useState<string[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [customModelInput, setCustomModelInput] = useState("")
    const [modelType, setModelType] = useState<string>("text")
    const [modelSubType, setModelSubType] = useState<string>("chat")

    // Load saved config on open
    useEffect(() => {
        if (open) {
            const savedBaseUrl = localStorage.getItem("ai.baseUrl") || ""
            const savedApiKey = localStorage.getItem("ai.apiKey") || ""
            const savedModel = localStorage.getItem("ai.model") || ""

            setBaseUrl(savedBaseUrl)
            setApiKey(savedApiKey)
            setSelectedModel(savedModel)
            setCustomModelInput(savedModel)
        }
    }, [open])

    const fetchModels = async () => {
        if (!apiKey) {
            alert("请先输入 API Key")
            return
        }

        setIsLoading(true)
        try {
            const response = await fetch("/api/v1/ai/fetch-models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    provider: "openai_compatible",
                    api_key: apiKey.trim(),
                    base_url: baseUrl.trim() || undefined,
                    type: modelType,
                    sub_type: modelSubType
                })
            })

            const data = await response.json()

            if (response.ok && data.models) {
                const modelList = data.models.map((m: any) => m.id)
                setModels(modelList)
                console.log(`成功获取 ${modelList.length} 个模型`)
                alert(`成功加载 ${modelList.length} 个模型！`)

                // 如果当前选中的模型不在列表中，且列表不为空，默认选中第一个
                if (modelList.length > 0 && !modelList.includes(selectedModel)) {
                    setSelectedModel(modelList[0])
                    setCustomModelInput(modelList[0])
                }
            } else {
                alert(`获取模型失败: ${data.detail || data.error || "未知错误"}`)
                setModels([])
            }
        } catch (error) {
            alert("网络请求失败")
        } finally {
            setIsLoading(false)
        }
    }

    const handleSave = async () => {
        const modelToSave = customModelInput || selectedModel

        if (!modelToSave) {
            alert("请选择或输入模型")
            return
        }

        try {
            // Save to local storage
            localStorage.setItem("ai.baseUrl", baseUrl)
            localStorage.setItem("ai.apiKey", apiKey)
            localStorage.setItem("ai.model", modelToSave)

            // Configure backend
            const response = await fetch("/api/v1/ai/add-provider", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    provider: "openai_compatible",
                    api_key: apiKey.trim(),
                    base_url: baseUrl.trim() || undefined
                })
            })

            if (response.ok) {
                // Also switch model
                await fetch("/api/v1/ai/switch-model", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ model: modelToSave })
                })

                console.log("配置已保存")
                onOpenChange(false)
                // Refresh page to apply changes (optional, but safer for now)
                window.location.reload()
            } else {
                const data = await response.json()
                alert(`配置失败: ${data.detail}`)
            }
        } catch (error) {
            alert("保存失败")
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>模型设置</DialogTitle>
                </DialogHeader>

                <div className="grid gap-6 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="base-url">OpenAI Compatible API Endpoint</Label>
                        <Input
                            id="base-url"
                            placeholder="https://api.siliconflow.cn/v1"
                            value={baseUrl}
                            onChange={(e) => setBaseUrl(e.target.value)}
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="grid gap-2">
                            <Label htmlFor="model-type">Type</Label>
                            <Select value={modelType} onValueChange={setModelType}>
                                <SelectTrigger id="model-type">
                                    <SelectValue placeholder="Select type" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="text">Text</SelectItem>
                                    <SelectItem value="image">Image</SelectItem>
                                    <SelectItem value="audio">Audio</SelectItem>
                                    <SelectItem value="video">Video</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="model-sub-type">Sub Type</Label>
                            <Select value={modelSubType} onValueChange={setModelSubType}>
                                <SelectTrigger id="model-sub-type">
                                    <SelectValue placeholder="Select sub type" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="chat">Chat</SelectItem>
                                    <SelectItem value="embedding">Embedding</SelectItem>
                                    <SelectItem value="reranker">Reranker</SelectItem>
                                    <SelectItem value="text-to-image">Text to Image</SelectItem>
                                    <SelectItem value="image-to-image">Image to Image</SelectItem>
                                    <SelectItem value="speech-to-text">Speech to Text</SelectItem>
                                    <SelectItem value="text-to-video">Text to Video</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="api-key">API Key</Label>
                        <Input
                            id="api-key"
                            type="password"
                            placeholder="sk-..."
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                        />
                    </div>

                    <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                            <Label>模型选择</Label>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-auto p-0 text-xs text-blue-500 hover:text-blue-600 disabled:opacity-50"
                                onClick={fetchModels}
                                disabled={isLoading}
                            >
                                {isLoading ? (
                                    <>
                                        <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
                                        加载中...
                                    </>
                                ) : (
                                    "刷新模型列表"
                                )}
                            </Button>
                        </div>

                        <div className="relative">
                            {models.length > 0 ? (
                                <Select
                                    value={selectedModel}
                                    onValueChange={(val) => {
                                        setSelectedModel(val)
                                        setCustomModelInput(val)
                                    }}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="选择模型" />
                                    </SelectTrigger>
                                    <SelectContent className="max-h-60 overflow-y-auto bg-neutral-900 border-white/10 text-white">
                                        {models.map((m) => (
                                            <SelectItem key={m} value={m} className="text-white hover:bg-white/10 focus:bg-white/10 cursor-pointer">
                                                {m}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            ) : null}

                            {/* Allow custom input if select is not enough or empty */}
                            <Input
                                className="mt-2"
                                placeholder="输入模型名称或从列表中选择"
                                value={customModelInput}
                                onChange={(e) => {
                                    setCustomModelInput(e.target.value)
                                }}
                            />
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="outline">取消</Button>
                    </DialogClose>
                    <Button onClick={handleSave}>保存</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
