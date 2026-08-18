"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/components/ui/use-toast"
import { ArrowLeft, Save, Loader2, RotateCcw, ChevronRight, FileText, Sparkles, Wand2, Tag, Image, MessageSquare, Settings, AlertCircle } from "lucide-react"
import { Textarea } from "@/components/ui/textarea"
import { API_ENDPOINTS } from "@/lib/env"
import { PageHeader } from "@/components/layout/page-scaffold"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

interface PromptConfigItem {
  key: string
  label: string
  description: string
  editable: boolean
  version: string
}

interface PromptCategory {
  category: string
  label: string
  items: PromptConfigItem[]
}

interface PromptConfig {
  key: string
  category_path: string[]
  config: {
    category: string
    label: string
    description: string
    version: string
    editable: boolean
    system_prompt: string
    [key: string]: any
  }
}

const CATEGORY_ICONS: Record<string, any> = {
  content_generation: FileText,
  chat_assistant: MessageSquare,
  automation: Settings,
  system: Settings,
}

export default function AIPromptsManagementPage() {
  const router = useRouter()
  const { toast } = useToast()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [structure, setStructure] = useState<PromptCategory[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedItem, setSelectedItem] = useState<string | null>(null)
  const [currentConfig, setCurrentConfig] = useState<PromptConfig | null>(null)
  const [editedPrompt, setEditedPrompt] = useState<string>("")
  const [hasChanges, setHasChanges] = useState(false)

  // 加载配置结构
  useEffect(() => {
    loadStructure()
  }, [])

  // 当选择配置项时加载详细信息
  useEffect(() => {
    if (selectedItem) {
      loadConfig(selectedItem)
    }
  }, [selectedItem])

  const loadStructure = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_ENDPOINTS.AI_PROMPTS}/structure`)
      const result = await response.json()

      if (result.status === "success") {
        setStructure(result.data)

        // 自动选择第一个分类和第一个配置项
        if (result.data.length > 0) {
          const firstCategory = result.data[0]
          setSelectedCategory(firstCategory.category)

          if (firstCategory.items.length > 0) {
            setSelectedItem(firstCategory.items[0].key)
          }
        }
      } else {
        toast({
          title: "加载失败",
          description: "无法加载AI配置结构",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error("加载配置结构失败:", error)
      toast({
        title: "加载失败",
        description: "网络错误，请稍后重试",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const loadConfig = async (configKey: string) => {
    try {
      const response = await fetch(`${API_ENDPOINTS.AI_PROMPTS}/config/${configKey}`)
      const result = await response.json()

      if (result.status === "success") {
        setCurrentConfig(result.data)
        setEditedPrompt(result.data.config.system_prompt || "")
        setHasChanges(false)
      } else {
        toast({
          title: "加载失败",
          description: `无法加载配置项: ${configKey}`,
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error("加载配置失败:", error)
      toast({
        title: "加载失败",
        description: "网络错误，请稍后重试",
        variant: "destructive",
      })
    }
  }

  const handleSave = async () => {
    if (!currentConfig || !selectedItem) return

    if (!currentConfig.config.editable) {
      toast({
        title: "无法保存",
        description: "此配置项不可编辑",
        variant: "destructive",
      })
      return
    }

    try {
      setSaving(true)

      const response = await fetch(`${API_ENDPOINTS.AI_PROMPTS}/config/${selectedItem}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          system_prompt: editedPrompt,
        }),
      })

      const result = await response.json()

      if (result.status === "success") {
        toast({
          title: "保存成功",
          description: "AI提示词配置已更新",
        })
        setHasChanges(false)

        // 重新加载配置
        await loadConfig(selectedItem)
      } else {
        toast({
          title: "保存失败",
          description: result.message || "保存配置时出错",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error("保存配置失败:", error)
      toast({
        title: "保存失败",
        description: "网络错误，请稍后重试",
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!selectedItem) return

    if (!confirm("确定要重置此配置到默认值吗？此操作不可撤销。")) {
      return
    }

    try {
      setSaving(true)

      const response = await fetch(`${API_ENDPOINTS.AI_PROMPTS}/config/${selectedItem}/reset`, {
        method: "POST",
      })

      const result = await response.json()

      if (result.status === "success") {
        toast({
          title: "重置成功",
          description: "配置已恢复到默认值",
        })

        // 重新加载配置
        await loadConfig(selectedItem)
      } else {
        toast({
          title: "重置失败",
          description: result.message || "重置配置时出错",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error("重置配置失败:", error)
      toast({
        title: "重置失败",
        description: "网络错误，请稍后重试",
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  const handlePromptChange = (value: string) => {
    setEditedPrompt(value)
    setHasChanges(value !== currentConfig?.config.system_prompt)
  }

  const getCategoryIcon = (category: string) => {
    const Icon = CATEGORY_ICONS[category] || Settings
    return <Icon className="h-4 w-4" />
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* 头部 */}
      <PageHeader
        title="AI 提示词配置"
        description="管理和自定义所有AI模块的系统提示词"
        actions={
          <Button variant="ghost" size="sm" onClick={() => router.push("/ai-agent/settings")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回设置
          </Button>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧导航 */}
        <aside className="w-64 border-r bg-muted/30 overflow-y-auto">
          <div className="p-4 space-y-4">
            {structure.map((category) => (
              <div key={category.category}>
                <div className="flex items-center gap-2 px-2 py-1 text-sm font-semibold text-muted-foreground">
                  {getCategoryIcon(category.category)}
                  <span>{category.label}</span>
                </div>
                <div className="mt-2 space-y-1">
                  {category.items.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => {
                        setSelectedCategory(category.category)
                        setSelectedItem(item.key)
                      }}
                      className={`
                        w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                        ${selectedItem === item.key
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted"
                        }
                      `}
                    >
                      <div className="flex items-center justify-between">
                        <span>{item.label}</span>
                        {!item.editable && (
                          <Badge variant="secondary" className="text-xs">只读</Badge>
                        )}
                      </div>
                      <p className="text-xs opacity-70 mt-1 line-clamp-1">
                        {item.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* 右侧编辑区域 */}
        <main className="flex-1 overflow-y-auto">
          {currentConfig ? (
            <div className="p-6 max-w-5xl mx-auto space-y-6">
              {/* 面包屑 */}
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <BreadcrumbLink href="/ai-agent">AI</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbLink href="/ai-agent/settings">AI配置</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbPage>{currentConfig.config.label}</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>

              {/* 配置信息卡片 */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        {currentConfig.config.label}
                        <Badge variant="outline">{currentConfig.config.version}</Badge>
                      </CardTitle>
                      <CardDescription className="mt-2">
                        {currentConfig.config.description}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
              </Card>

              {/* 不可编辑提示 */}
              {!currentConfig.config.editable && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    此配置项为系统级配置，不可编辑。如需修改，请联系管理员。
                  </AlertDescription>
                </Alert>
              )}

              {/* 编辑器 */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>系统提示词</CardTitle>
                    <div className="flex gap-2">
                      {currentConfig.config.editable && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleReset}
                            disabled={saving}
                          >
                            <RotateCcw className="mr-2 h-4 w-4" />
                            重置
                          </Button>
                          <Button
                            size="sm"
                            onClick={handleSave}
                            disabled={!hasChanges || saving}
                          >
                            {saving ? (
                              <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                保存中...
                              </>
                            ) : (
                              <>
                                <Save className="mr-2 h-4 w-4" />
                                保存更改
                              </>
                            )}
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <Textarea
                    value={editedPrompt}
                    onChange={(e) => handlePromptChange(e.target.value)}
                    disabled={!currentConfig.config.editable}
                    className="min-h-[500px] font-mono text-sm"
                    placeholder="输入系统提示词..."
                  />
                  {hasChanges && (
                    <p className="text-sm text-muted-foreground mt-2">
                      * 有未保存的更改
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* 额外配置信息 */}
              {currentConfig.config.platform_tuning && (
                <Card>
                  <CardHeader>
                    <CardTitle>平台优化配置</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto">
                      {JSON.stringify(currentConfig.config.platform_tuning, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <div className="text-center">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>请从左侧选择一个配置项</p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
