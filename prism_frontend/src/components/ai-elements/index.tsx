"use client"

import * as React from "react"
import { Confirmation, type ConfirmationState } from "./confirmation"
import { Queue, type QueueItem } from "./queue"
import { Reasoning, ReasoningContent, ReasoningTrigger } from "./reasoning"
import { Tool, ToolHeader, ToolName, ToolStatus, ToolResult } from "./tool"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChevronDown, ChevronRight } from "lucide-react"

/**
 * 工具调用确认组件 - 使用 Confirmation
 */
interface ToolConfirmationProps {
  toolName?: string
  args?: Record<string, any>
  onAccept: () => void
  onReject: () => void
  state?: ConfirmationState
  disabled?: boolean
  taskSummary?: {
    goal?: string
    total_steps?: string | number
    tools?: Array<{ name: string; arguments?: any }>
  }
}

export function ToolConfirmation({
  toolName,
  args,
  onAccept,
  onReject,
  state = "request",
  disabled = false,
  taskSummary
}: ToolConfirmationProps) {
  const canAct = state === "request" && !disabled

  return (
    <Confirmation
      state={state}
      toolName={toolName}
      args={args}
      taskSummary={taskSummary}
      onAccept={canAct ? onAccept : undefined}
      onReject={canAct ? onReject : undefined}
    />
  )
}

/**
 * 工具调用结果显示 - 使用 Tool 组件
 */
interface ToolExecutionDisplayProps {
  name: string
  status?: "input-available" | "in-progress" | "completed"
  args?: Record<string, any>
  result?: any
  error?: string
}

export function ToolExecutionDisplay({
  name,
  status = "completed",
  args,
  result,
  error
}: ToolExecutionDisplayProps) {
  const [isOpen, setIsOpen] = React.useState(true)

  return (
    <div className="bg-card/40 rounded-lg border border-border/70 p-4 shadow-xl backdrop-blur-sm hover:border-border/80 transition-all">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger className="w-full">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-1.5 h-1.5 rounded-full ${status === "completed" ? "bg-foreground/80" : status === "in-progress" ? "bg-foreground/50 animate-pulse" : "bg-black"}`} />
              <span className="text-base font-semibold text-foreground/90">
                {name}
              </span>
              <span className="text-xs text-foreground/40">
                {status === "completed" ? "✓" : status === "in-progress" ? "⏳" : "✗"}
              </span>
            </div>
            <div className="text-foreground/40 hover:text-muted-foreground transition-colors">
              {isOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </div>
          </div>
        </CollapsibleTrigger>

        <CollapsibleContent className="space-y-3 mt-4">
          {args && Object.keys(args).length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wider">参数</div>
              <pre className="text-sm bg-card/60 rounded p-3 overflow-x-auto text-foreground/80 border border-border/40 font-mono">
{JSON.stringify(args, null, 2)}
              </pre>
            </div>
          )}

          {result && !error && (
            <div>
              <div className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wider">结果</div>
              <div className="bg-card/60 rounded p-3 border border-border/40">
                <pre className="text-sm text-foreground/80 font-mono overflow-x-auto">
{typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {error && (
            <div>
              <div className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wider">错误</div>
              <div className="text-sm bg-card/60 rounded p-3 text-foreground/70 font-mono border border-border/40">
                {error}
              </div>
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

/**
 * Agent 思考过程显示 - 使用 Reasoning
 */
interface AgentReasoningProps {
  content: string
  isThinking?: boolean
}

export function AgentReasoning({ content, isThinking = false }: AgentReasoningProps) {
  const [isOpen, setIsOpen] = React.useState(isThinking)

  React.useEffect(() => {
    if (isThinking) {
      setIsOpen(true)
    }
  }, [isThinking])

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger>
        <ReasoningTrigger />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <Reasoning duration={isThinking ? undefined : 0}>
          <ReasoningContent>
            {content}
          </ReasoningContent>
        </Reasoning>
      </CollapsibleContent>
    </Collapsible>
  )
}

/**
 * Agent 任务队列显示 - 使用 Queue
 */
interface AgentTaskQueueProps {
  tasks: Array<{
    id: string
    name: string
    status: "pending" | "in-progress" | "completed" | "failed"
    metadata?: Record<string, any>
  }>
  title?: string
  collapsible?: boolean
}

export function AgentTaskQueue({
  tasks,
  title = "任务队列",
  collapsible = true
}: AgentTaskQueueProps) {
  const queueItems: QueueItem[] = tasks.map(task => ({
    id: task.id,
    content: task.name,
    status: task.status,
    metadata: task.metadata
  }))

  return (
    <Queue
      items={queueItems}
      title={title}
      collapsible={collapsible}
      defaultOpen={tasks.some(t => t.status === "in-progress")}
    />
  )
}

/**
 * 批量工具调用显示
 */
interface BatchToolCallsDisplayProps {
  toolCalls: Array<{
    id: string
    name: string
    args: Record<string, any>
    result?: any
    error?: string
    status?: "pending" | "in-progress" | "completed" | "failed"
  }>
}

export function BatchToolCallsDisplay({ toolCalls }: BatchToolCallsDisplayProps) {
  if (toolCalls.length === 0) return null

  return (
    <div className="space-y-2">
      {toolCalls.map((call) => (
        <ToolExecutionDisplay
          key={call.id}
          name={call.name}
          status={call.status === "completed" ? "completed" : call.status === "in-progress" ? "in-progress" : "completed"}
          args={call.args}
          result={call.result}
          error={call.error}
        />
      ))}
    </div>
  )
}

// Export all components
export {
  Confirmation,
  Queue,
  Reasoning,
  Tool,
  ToolHeader,
  ToolName,
  ToolStatus,
  ToolResult
}
export { Task, TaskList } from "./task"

// Export types
export type { QueueItem, ConfirmationState }
export type { TaskItem } from "./task"
