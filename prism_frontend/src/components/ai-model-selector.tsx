import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Badge } from "@/components/ui/badge"
import { Check, ChevronsUpDown, Zap, Clock } from "lucide-react"
import { cn } from "@/lib/utils"

interface ModelInfo {
  id: string
  name: string
  provider: string
  description?: string
  contextWindow?: number
  maxTokens?: number
  speed?: "fast" | "medium" | "slow"
  costPerMTok?: number
}

interface AIModelSelectorProps {
  models: ModelInfo[]
  selectedModel: string | null
  onModelSelect: (modelId: string) => Promise<boolean>
  isLoading?: boolean
}

export function AIModelSelector({
  models,
  selectedModel,
  onModelSelect,
  isLoading = false,
}: AIModelSelectorProps) {
  const [open, setOpen] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)

  const selected = models.find((m) => m.id === selectedModel)

  const providerEmojis = {
    siliconflow: "🚀",
    volcanoengine: "🌋",
    tongyi: "💙",
  }

  const handleSelectModel = async (modelId: string) => {
    setIsProcessing(true)
    try {
      const success = await onModelSelect(modelId)
      if (success) {
        setOpen(false)
      }
    } finally {
      setIsProcessing(false)
    }
  }

  const groupedModels = models.reduce(
    (acc, model) => {
      const provider = model.provider
      if (!acc[provider]) {
        acc[provider] = []
      }
      acc[provider].push(model)
      return acc
    },
    {} as Record<string, ModelInfo[]>
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between bg-white/5 border-white/20 text-white hover:bg-white/10 hover:border-white/30"
          disabled={isLoading || isProcessing || models.length === 0}
        >
          <div className="flex items-center gap-2 max-w-xs truncate">
            {selected ? (
              <>
                <span className="text-lg">
                  {providerEmojis[selected.provider as keyof typeof providerEmojis] || "🤖"}
                </span>
                <span className="truncate text-sm">{selected.name}</span>
                {selected.speed === "fast" && (
                  <Zap className="h-3 w-3 text-yellow-400 flex-shrink-0" />
                )}
              </>
            ) : (
              <span className="text-white/50">选择模型...</span>
            )}
          </div>
          <ChevronsUpDown className="ml-2 h-4 w-4 opacity-50 flex-shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full p-0 bg-gradient-to-b from-slate-900 to-slate-800 border-white/10">
        <Command className="bg-transparent">
          <CommandInput
            placeholder="搜索模型..."
            className="border-white/10 text-white placeholder:text-white/40"
          />
          <CommandEmpty className="text-white/50 p-4">未找到相匹配的模型</CommandEmpty>
          <CommandList className="max-h-72">
            {Object.entries(groupedModels).map(([provider, providerModels]) => (
              <CommandGroup
                key={provider}
                heading={
                  <span className="text-white/60">
                    {providerEmojis[provider as keyof typeof providerEmojis]} {provider}
                  </span>
                }
                className="text-white/60 [&_[cmdk-group-heading]]:text-white/40"
              >
                {providerModels.map((model) => (
                  <CommandItem
                    key={model.id}
                    value={model.id}
                    onSelect={() => handleSelectModel(model.id)}
                    className="aria-selected:bg-blue-600/30 aria-selected:text-white text-white/70 cursor-pointer hover:bg-white/10"
                  >
                    <div className="flex items-center justify-between w-full gap-2">
                      <div className="flex items-center gap-2 flex-1">
                        <Check
                          className={cn(
                            "h-4 w-4 flex-shrink-0",
                            selectedModel === model.id
                              ? "opacity-100 text-blue-400"
                              : "opacity-0"
                          )}
                        />
                        <div className="flex-1">
                          <div className="font-medium text-white">{model.name}</div>
                          {model.description && (
                            <div className="text-xs text-white/40">{model.description}</div>
                          )}
                        </div>
                      </div>

                      {/* 模型特征标签 */}
                      <div className="flex gap-1 flex-shrink-0">
                        {model.speed && (
                          <Badge
                            variant="secondary"
                            className={cn(
                              "text-xs",
                              model.speed === "fast" && "bg-yellow-500/20 text-yellow-200",
                              model.speed === "medium" && "bg-blue-500/20 text-blue-200",
                              model.speed === "slow" && "bg-purple-500/20 text-purple-200"
                            )}
                          >
                            <Clock className="h-3 w-3 mr-1" />
                            {model.speed}
                          </Badge>
                        )}
                        {model.contextWindow && (
                          <Badge
                            variant="secondary"
                            className="text-xs bg-white/10 text-white/70"
                          >
                            {model.contextWindow}K
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
