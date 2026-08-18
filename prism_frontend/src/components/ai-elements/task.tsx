"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { CheckCircle2, Circle, Clock, XCircle, ChevronDown, ChevronRight } from "lucide-react"

export interface TaskItem {
  id: string
  title: string
  description?: string
  status: "pending" | "in-progress" | "completed" | "failed"
  progress?: number
  metadata?: Record<string, any>
}

interface TaskProps {
  /**
   * 任务项
   */
  task: TaskItem

  /**
   * 是否可展开
   */
  collapsible?: boolean

  /**
   * 默认展开状态
   */
  defaultOpen?: boolean

  /**
   * 点击回调
   */
  onClick?: () => void

  /**
   * 自定义类名
   */
  className?: string
}

/**
 * Task 组件 - 显示单个任务
 */
export function Task({
  task,
  collapsible = true,
  defaultOpen = false,
  onClick,
  className
}: TaskProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)

  const statusConfig = {
    pending: {
      icon: Circle,
      color: "text-white/40",
      bgColor: "bg-white/5",
      borderColor: "border-white/10"
    },
    "in-progress": {
      icon: Clock,
      color: "text-blue-400",
      bgColor: "bg-blue-500/10",
      borderColor: "border-blue-500/30"
    },
    completed: {
      icon: CheckCircle2,
      color: "text-green-400",
      bgColor: "bg-green-500/10",
      borderColor: "border-green-500/30"
    },
    failed: {
      icon: XCircle,
      color: "text-red-400",
      bgColor: "bg-red-500/10",
      borderColor: "border-red-500/30"
    }
  }

  const config = statusConfig[task.status]
  const Icon = config.icon

  const content = (
    <div className="space-y-2">
      <div className="flex items-start gap-3">
        <Icon className={cn("h-5 w-5 mt-0.5", config.color, task.status === "in-progress" && "animate-spin")} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white/90">{task.title}</div>
          {task.description && (
            <div className="text-xs text-white/60 mt-1">{task.description}</div>
          )}
          {task.progress !== undefined && (
            <div className="mt-2">
              <div className="flex items-center justify-between text-xs text-white/50 mb-1">
                <span>进度</span>
                <span>{task.progress}%</span>
              </div>
              <div className="h-1.5 bg-black/40 rounded-full overflow-hidden">
                <div
                  className="h-full bg-white/60 rounded-full transition-all duration-300"
                  style={{ width: `${task.progress}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {task.metadata && Object.keys(task.metadata).length > 0 && collapsible && (
        <Collapsible open={isOpen} onOpenChange={setIsOpen}>
          <CollapsibleTrigger className="flex items-center gap-1 text-xs text-white/40 hover:text-white/60 transition-colors">
            {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            <span>详细信息</span>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            <pre className="text-xs bg-black/40 rounded p-2 text-white/60 font-mono overflow-x-auto">
              {JSON.stringify(task.metadata, null, 2)}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )

  return (
    <Card
      className={cn(
        "p-3 transition-all",
        config.bgColor,
        config.borderColor,
        onClick && "cursor-pointer hover:border-white/30",
        className
      )}
      onClick={onClick}
    >
      {content}
    </Card>
  )
}

/**
 * TaskList 组件 - 显示任务列表
 */
interface TaskListProps {
  tasks: TaskItem[]
  title?: string
  className?: string
  onTaskClick?: (task: TaskItem) => void
}

export function TaskList({ tasks, title = "任务列表", className, onTaskClick }: TaskListProps) {
  const pendingCount = tasks.filter(t => t.status === "pending").length
  const inProgressCount = tasks.filter(t => t.status === "in-progress").length
  const completedCount = tasks.filter(t => t.status === "completed").length

  return (
    <Card className={cn("bg-black/40 border-white/10", className)}>
      <div className="p-3 border-b border-white/10">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-white/90">{title}</span>
          <div className="flex items-center gap-2 text-xs text-white/50">
            {inProgressCount > 0 && (
              <span className="text-blue-400">{inProgressCount} 进行中</span>
            )}
            {pendingCount > 0 && (
              <span>{pendingCount} 待处理</span>
            )}
            {completedCount > 0 && (
              <span className="text-green-400">{completedCount} 已完成</span>
            )}
          </div>
        </div>
      </div>

      <div className="p-2 space-y-2">
        {tasks.length === 0 ? (
          <div className="text-center text-xs text-white/40 py-4">暂无任务</div>
        ) : (
          tasks.map((task) => (
            <Task
              key={task.id}
              task={task}
              onClick={() => onTaskClick?.(task)}
            />
          ))
        )}
      </div>
    </Card>
  )
}
