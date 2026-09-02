"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import {
  Play,
  Check,
  X,
  ChevronDown,
  ChevronUp,
  Loader2,
  Code2,
  AlertCircle
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

export interface ToolCall {
  id: string
  name: string
  args: Record<string, any>
  status?: "pending" | "running" | "success" | "error" | "rejected"
  result?: string
  error?: string
}

interface ToolCallDisplayProps {
  toolCall: ToolCall
  onApprove?: (toolCall: ToolCall) => void
  onReject?: (toolCall: ToolCall) => void
  autoApprove?: boolean
  className?: string
}

export function ToolCallDisplay({
  toolCall,
  onApprove,
  onReject,
  autoApprove = false,
  className
}: ToolCallDisplayProps) {
  const [isOpen, setIsOpen] = React.useState(true)

  const status = toolCall.status || "pending"

  const getStatusIcon = () => {
    switch (status) {
      case "pending":
        return <Play className="h-4 w-4 text-white" />
      case "running":
        return <Loader2 className="h-4 w-4 text-white animate-spin" />
      case "success":
        return <Check className="h-4 w-4 text-white" />
      case "error":
        return <AlertCircle className="h-4 w-4 text-white" />
      case "rejected":
        return <X className="h-4 w-4 text-white" />
      default:
        return <Code2 className="h-4 w-4 text-white" />
    }
  }

  const getStatusText = () => {
    switch (status) {
      case "pending":
        return "等待执行"
      case "running":
        return "执行中"
      case "success":
        return "执行成功"
      case "error":
        return "执行失败"
      case "rejected":
        return "已拒绝"
      default:
        return "未知状态"
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case "pending":
        return "border-white/17 bg-black"
      case "running":
        return "border-white/17 bg-black animate-pulse"
      case "success":
        return "border-white/17 bg-black"
      case "error":
        return "border-white/17 bg-black"
      case "rejected":
        return "border-white/17 bg-black"
      default:
        return "border-white/17 bg-black"
    }
  }

  return (
    <div className={cn("rounded-lg border backdrop-blur-sm", getStatusColor(), className)}>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        {/* Header */}
        <div className="flex items-center gap-3 p-3">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {getStatusIcon()}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground truncate">
                  {toolCall.name}
                </span>
                <span className="text-xs text-muted-foreground">
                  {getStatusText()}
                </span>
              </div>
            </div>
          </div>

          <CollapsibleTrigger asChild>
            <Button size="icon" variant="ghost" className="h-6 w-6 shrink-0">
              {isOpen ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </Button>
          </CollapsibleTrigger>
        </div>

        {/* Content */}
        <CollapsibleContent>
          <div className="px-3 pb-3 space-y-2">
            {/* Arguments */}
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">参数:</div>
              <pre className="text-xs bg-card/30 rounded p-2 overflow-x-auto text-foreground/80 border border-border/70">
                {JSON.stringify(toolCall.args, null, 2)}
              </pre>
            </div>

            {/* Result */}
            {toolCall.result && (
              <div>
                <div className="text-xs font-medium text-muted-foreground mb-1">结果:</div>
                <pre className="text-xs bg-card/30 rounded p-2 overflow-x-auto text-foreground/80 border border-border/70 max-h-40">
                  {toolCall.result}
                </pre>
              </div>
            )}

            {/* Error */}
            {toolCall.error && (
              <div>
                <div className="text-xs font-medium text-white mb-1">错误:</div>
                <pre className="text-xs bg-black rounded p-2 overflow-x-auto text-white border border-white/17 max-h-40">
                  {toolCall.error}
                </pre>
              </div>
            )}

            {/* Actions */}
            {status === "pending" && !autoApprove && onApprove && onReject && (
              <div className="flex gap-2 pt-2">
                <Button
                  size="sm"
                  onClick={() => onApprove(toolCall)}
                  className="flex-1 bg-white hover:bg-white text-foreground"
                >
                  <Check className="mr-1 h-3 w-3" />
                  允许执行
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onReject(toolCall)}
                  className="flex-1 border-white/17 hover:bg-black text-white"
                >
                  <X className="mr-1 h-3 w-3" />
                  拒绝
                </Button>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

interface ThinkingProcessProps {
  content: string
  isThinking?: boolean
  className?: string
}

export function ThinkingProcess({
  content,
  isThinking = false,
  className
}: ThinkingProcessProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-white/17 bg-black p-3 backdrop-blur-sm",
        isThinking && "animate-pulse",
        className
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        {isThinking ? (
          <Loader2 className="h-4 w-4 text-white animate-spin" />
        ) : (
          <Code2 className="h-4 w-4 text-white" />
        )}
        <span className="text-sm font-medium text-white">
          {isThinking ? "思考中" : "思考过程"}
        </span>
      </div>
      <div className="text-sm text-foreground/70 whitespace-pre-wrap leading-relaxed">
        {content}
      </div>
    </div>
  )
}

interface MultiToolCallsDisplayProps {
  toolCalls: ToolCall[]
  onApprove?: (toolCall: ToolCall) => void
  onReject?: (toolCall: ToolCall) => void
  autoApprove?: boolean
  className?: string
}

export function MultiToolCallsDisplay({
  toolCalls,
  onApprove,
  onReject,
  autoApprove = false,
  className
}: MultiToolCallsDisplayProps) {
  if (toolCalls.length === 0) return null

  return (
    <div className={cn("space-y-2", className)}>
      {toolCalls.map((toolCall) => (
        <ToolCallDisplay
          key={toolCall.id}
          toolCall={toolCall}
          onApprove={onApprove}
          onReject={onReject}
          autoApprove={autoApprove}
        />
      ))}
    </div>
  )
}
