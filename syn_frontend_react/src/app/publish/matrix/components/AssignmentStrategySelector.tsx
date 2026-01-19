"use client"

import React, { useState } from 'react'
import { Check, Grid3x3, Users, Share2, Settings, ChevronDown, ChevronUp } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// 分配策略类型定义
type AssignmentStrategy = "one_per_account" | "all_per_account" | "cross_platform_all" | "per_platform_custom"
type OnePerAccountMode = "random" | "round_robin" | "sequential"

// 策略配置接口
interface AssignmentConfig {
  assignmentStrategy: AssignmentStrategy
  onePerAccountMode: OnePerAccountMode
  perPlatformOverrides?: Record<string, string>
  allowDuplicatePublish: boolean
  dedupWindowDays: number
}

// 策略定义
interface StrategyDefinition {
  key: AssignmentStrategy
  title: string
  description: string
  icon: React.ReactNode
  badge?: string
  calculateTasks: (videos: number, accounts: number) => number
  preview: (v: number, a: number) => string
  color: string
}

const ASSIGNMENT_STRATEGIES: StrategyDefinition[] = [
  {
    key: "all_per_account",
    title: "全覆盖发布",
    description: "每个账号发布所有视频（推荐）",
    icon: <Grid3x3 className="w-5 h-5" />,
    badge: "默认",
    calculateTasks: (videos, accounts) => videos * accounts,
    preview: (v, a) => `${v} × ${a} = ${v * a}`,
    color: "from-green-500 to-emerald-500"
  },
  {
    key: "one_per_account",
    title: "账号单次发布",
    description: "每个账号只发布1个视频",
    icon: <Users className="w-5 h-5" />,
    calculateTasks: (videos, accounts) => Math.min(videos, accounts),
    preview: (v, a) => `min(${v}, ${a}) = ${Math.min(v, a)}`,
    color: "from-blue-500 to-cyan-500"
  },
  {
    key: "cross_platform_all",
    title: "跨平台全覆盖",
    description: "每个平台的账号发布所有视频",
    icon: <Share2 className="w-5 h-5" />,
    calculateTasks: (videos, accounts) => videos * accounts,
    preview: (v, a) => `${v} × ${a} = ${v * a}`,
    color: "from-purple-500 to-pink-500"
  },
  {
    key: "per_platform_custom",
    title: "平台自定义策略",
    description: "为每个平台设置不同的分配规则",
    icon: <Settings className="w-5 h-5" />,
    badge: "高级",
    calculateTasks: () => 0,
    preview: () => "动态计算",
    color: "from-orange-500 to-red-500"
  }
]

// 策略卡片组件
function StrategyCard({
  strategy,
  selected,
  onSelect,
  videoCount,
  accountCount
}: {
  strategy: StrategyDefinition
  selected: boolean
  onSelect: () => void
  videoCount: number
  accountCount: number
}) {
  const taskCount = strategy.calculateTasks(videoCount, accountCount)

  return (
    <button
      onClick={onSelect}
      className={cn(
        "relative p-5 rounded-xl border-2 text-left transition-all group",
        selected
          ? "border-primary bg-primary/10 shadow-[0_0_20px_rgba(94,234,212,0.3)]"
          : "border-white/10 bg-black/20 hover:border-white/30"
      )}
    >
      {/* 渐变顶部条 */}
      <div className={cn(
        "absolute top-0 left-0 right-0 h-1 rounded-t-xl bg-gradient-to-r transition-opacity",
        selected ? "opacity-100" : "opacity-0",
        strategy.color
      )} />

      <div className="flex items-start gap-4">
        {/* 图标 */}
        <div className={cn(
          "p-3 rounded-lg bg-gradient-to-r shrink-0",
          strategy.color,
          !selected && "opacity-50"
        )}>
          {strategy.icon}
        </div>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-semibold text-white">{strategy.title}</h4>
            {strategy.badge && (
              <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                {strategy.badge}
              </Badge>
            )}
          </div>
          <p className="text-sm text-white/60 mb-3">{strategy.description}</p>

          {/* 预览计算 */}
          <div className="text-xs text-primary/90 font-mono bg-primary/5 px-2 py-1.5 rounded">
            {strategy.preview(videoCount, accountCount)}
            {taskCount > 0 && <span className="font-bold ml-1">任务</span>}
          </div>
        </div>

        {/* 选择指示器 */}
        <div className={cn(
          "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0",
          selected ? "border-primary bg-primary" : "border-white/30"
        )}>
          {selected && <Check className="w-3 h-3 text-black" />}
        </div>
      </div>
    </button>
  )
}

// 任务数量预览组件
function TaskCountPreview({
  strategy,
  videoCount,
  accountCount
}: {
  strategy: AssignmentStrategy
  videoCount: number
  accountCount: number
}) {
  const calculateTotalTasks = () => {
    switch (strategy) {
      case "all_per_account":
        return videoCount * accountCount
      case "one_per_account":
        return Math.min(videoCount, accountCount)
      case "cross_platform_all":
        return videoCount * accountCount
      case "per_platform_custom":
        return "动态"
      default:
        return 0
    }
  }

  const taskCount = calculateTotalTasks()

  return (
    <div className="p-5 rounded-xl bg-gradient-to-r from-primary/10 via-purple-500/10 to-pink-500/10 border border-primary/20">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-white/60 mb-1">预计生成任务数</p>
          <p className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-primary to-purple-400">
            {taskCount}
          </p>
        </div>
        <div className="text-right text-sm text-white/60 space-y-1">
          <p>{videoCount} 个视频</p>
          <p>{accountCount} 个账号</p>
        </div>
      </div>
    </div>
  )
}

// 主组件
interface AssignmentStrategySelectorProps {
  config: AssignmentConfig
  onChange: (config: AssignmentConfig) => void
  videoCount: number
  accountCount: number
}

export default function AssignmentStrategySelector({
  config,
  onChange,
  videoCount,
  accountCount
}: AssignmentStrategySelectorProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const updateConfig = (updates: Partial<AssignmentConfig>) => {
    onChange({ ...config, ...updates })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Label className="text-base font-medium">任务分配策略</Label>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setAdvancedOpen(!advancedOpen)}
          className="text-white/70 hover:text-white"
        >
          {advancedOpen ? (
            <>收起高级配置 <ChevronUp className="ml-2 w-4 h-4" /></>
          ) : (
            <>展开高级配置 <ChevronDown className="ml-2 w-4 h-4" /></>
          )}
        </Button>
      </div>

      {advancedOpen && (
        <div className="rounded-2xl border border-white/10 bg-black p-6 space-y-6 animate-in fade-in slide-in-from-top-2">
          {/* 策略选择网格 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {ASSIGNMENT_STRATEGIES.map(strategy => (
              <StrategyCard
                key={strategy.key}
                strategy={strategy}
                selected={config.assignmentStrategy === strategy.key}
                onSelect={() => updateConfig({ assignmentStrategy: strategy.key })}
                videoCount={videoCount}
                accountCount={accountCount}
              />
            ))}
          </div>

          {/* 任务数量预览 */}
          <TaskCountPreview
            strategy={config.assignmentStrategy}
            videoCount={videoCount}
            accountCount={accountCount}
          />

          {/* 策略特定选项 */}
          {config.assignmentStrategy === "one_per_account" && (
            <div className="p-4 rounded-xl border border-blue-500/20 bg-blue-500/5 space-y-3">
              <Label className="text-sm font-medium text-blue-400">分配方式</Label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { key: "random" as const, label: "随机分配" },
                  { key: "round_robin" as const, label: "轮询分配" },
                  { key: "sequential" as const, label: "顺序分配" }
                ].map(mode => (
                  <button
                    key={mode.key}
                    onClick={() => updateConfig({ onePerAccountMode: mode.key })}
                    className={cn(
                      "px-3 py-2 rounded-lg text-xs transition",
                      config.onePerAccountMode === mode.key
                        ? "bg-blue-500/30 border border-blue-400/50 text-blue-300"
                        : "bg-white/5 border border-white/10 text-white/60 hover:border-white/30"
                    )}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 去重设置 */}
          <div className="p-4 rounded-xl border border-white/10 bg-black/20 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">智能去重</Label>
                <p className="text-xs text-white/50 mt-1">
                  防止同一账号在同一平台重复发布相同视频
                </p>
              </div>
              <Switch
                checked={!config.allowDuplicatePublish}
                onCheckedChange={(checked) =>
                  updateConfig({ allowDuplicatePublish: !checked })
                }
              />
            </div>

            {!config.allowDuplicatePublish && (
              <div className="flex items-center gap-3 pt-3 border-t border-white/10">
                <Label className="text-xs text-white/60 shrink-0">去重时间窗口</Label>
                <Input
                  type="number"
                  min="0"
                  max="365"
                  value={config.dedupWindowDays}
                  onChange={(e) =>
                    updateConfig({ dedupWindowDays: parseInt(e.target.value) || 7 })
                  }
                  className="w-20 h-8 text-sm"
                />
                <span className="text-xs text-white/50">
                  天内不重复（0=永久）
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
