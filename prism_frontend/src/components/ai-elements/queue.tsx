"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ChevronDown, ChevronRight, CheckCircle2, Circle, Clock } from "lucide-react"

export interface QueueItem {
  id: string
  content: string
  status?: "pending" | "in-progress" | "completed" | "failed"
  metadata?: Record<string, any>
}

interface QueueProps {
  /**
   * 队列项目列表
   */
  items: QueueItem[]

  /**
   * 队列标题
   */
  title?: string

  /**
   * 是否可折叠
   */
  collapsible?: boolean

  /**
   * 默认是否展开
   */
  defaultOpen?: boolean

  /**
   * 最大高度
   */
  maxHeight?: string

  /**
   * 自定义类名
   */
  className?: string

  /**
   * 项目点击回调
   */
  onItemClick?: (item: QueueItem) => void
}

/**
 * Queue 组件 - 显示任务队列、消息列表等
 *
 * 使用场景：
 * - 显示 Agent 的任务队列
 * - 显示工具调用列表
 * - 显示待办事项
 * - 显示消息历史
 */
export function Queue({
  items,
  title = "任务队列",
  collapsible = false,
  defaultOpen = true,
  maxHeight = "400px",
  className,
  onItemClick
}: QueueProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)

  const statusIcons = {
    pending: <Circle className="h-3 w-3 text-gray-400" />,
    "in-progress": <Clock className="h-3 w-3 text-blue-400 animate-spin" />,
    completed: <CheckCircle2 className="h-3 w-3 text-green-400" />,
    failed: <Circle className="h-3 w-3 text-red-400" />
  }

  const content = (
    <ScrollArea className={cn("w-full", maxHeight && `max-h-[${maxHeight}]`)}>
      <div className="space-y-1 p-2">
        {items.length === 0 ? (
          <div className="text-center text-xs text-white/40 py-4">
            暂无任务
          </div>
        ) : (
          items.map((item, index) => (
            <div
              key={item.id}
              onClick={() => onItemClick?.(item)}
              className={cn(
                "flex items-start gap-2 rounded p-2 text-xs transition-colors",
                "hover:bg-white/5",
                onItemClick && "cursor-pointer",
                item.status === "completed" && "opacity-60"
              )}
            >
              <div className="mt-0.5">
                {item.status ? statusIcons[item.status] : statusIcons.pending}
              </div>

              <div className="flex-1 space-y-1">
                <div className={cn(
                  "text-white/80",
                  item.status === "completed" && "line-through"
                )}>
                  {index + 1}. {item.content}
                </div>

                {item.metadata && Object.keys(item.metadata).length > 0 && (
                  <div className="text-[10px] text-white/40 font-mono">
                    {JSON.stringify(item.metadata, null, 2)}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </ScrollArea>
  )

  if (collapsible) {
    return (
      <Card className={cn("bg-black/40 border-white/10", className)}>
        <Collapsible open={isOpen} onOpenChange={setIsOpen}>
          <CollapsibleTrigger className="flex w-full items-center justify-between p-3 text-sm font-medium text-white/90 hover:bg-white/5 transition-colors">
            <div className="flex items-center gap-2">
              {isOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              <span>{title}</span>
              <span className="text-xs text-white/50">({items.length})</span>
            </div>
          </CollapsibleTrigger>

          <CollapsibleContent>
            {content}
          </CollapsibleContent>
        </Collapsible>
      </Card>
    )
  }

  return (
    <Card className={cn("bg-black/40 border-white/10", className)}>
      <div className="p-3 border-b border-white/10">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-white/90">{title}</span>
          <span className="text-xs text-white/50">{items.length} 项</span>
        </div>
      </div>
      {content}
    </Card>
  )
}

/**
 * QueueItem 组件 - 单个队列项
 */
export function QueueItemComponent({ item, onClick }: { item: QueueItem; onClick?: () => void }) {
  const statusIcons = {
    pending: <Circle className="h-3 w-3 text-gray-400" />,
    "in-progress": <Clock className="h-3 w-3 text-blue-400" />,
    completed: <CheckCircle2 className="h-3 w-3 text-green-400" />,
    failed: <Circle className="h-3 w-3 text-red-400" />
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-start gap-2 rounded p-2 text-xs hover:bg-white/5 transition-colors",
        onClick && "cursor-pointer"
      )}
    >
      <div className="mt-0.5">
        {item.status ? statusIcons[item.status] : statusIcons.pending}
      </div>
      <div className="flex-1 text-white/80">{item.content}</div>
    </div>
  )
}
