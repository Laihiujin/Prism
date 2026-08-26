"use client"

import * as React from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { AlertCircle, CheckCircle2, XCircle } from "lucide-react"

export type ConfirmationState = "request" | "accepted" | "rejected"

interface ConfirmationProps {
  /**
   * 当前确认状态
   */
  state?: ConfirmationState

  /**
   * 工具名称
   */
  toolName?: string

  /**
   * 工具调用的参数
   */
  args?: Record<string, any>

  /**
   * 确认消息
   */
  message?: string

  /**
   * 任务摘要（包含所有计划的工具）
   */
  taskSummary?: {
    goal?: string
    total_steps?: string | number
    tools?: Array<{ name: string; arguments?: any }>
  }

  /**
   * 接受回调
   */
  onAccept?: () => void

  /**
   * 拒绝回调
   */
  onReject?: () => void

  /**
   * 子元素
   */
  children?: React.ReactNode
}

/**
 * Confirmation 组件 - 用于工具执行前的用户确认
 *
 * 使用场景：
 * - Agent 需要执行敏感操作前请求用户确认
 * - 显示工具调用的详细信息
 * - 提供接受/拒绝按钮
 */
export function Confirmation({
  state = "request",
  toolName,
  args,
  message,
  taskSummary,
  onAccept,
  onReject,
  children
}: ConfirmationProps) {
  const stateConfig = {
    request: {
      icon: AlertCircle,
      iconColor: "text-yellow-500",
      borderColor: "border-yellow-500/30",
      bgColor: "bg-yellow-500/10"
    },
    accepted: {
      icon: CheckCircle2,
      iconColor: "text-green-500",
      borderColor: "border-green-500/30",
      bgColor: "bg-green-500/10"
    },
    rejected: {
      icon: XCircle,
      iconColor: "text-red-500",
      borderColor: "border-red-500/30",
      bgColor: "bg-red-500/10"
    }
  }

  const config = stateConfig[state]
  const Icon = config.icon

  return (
    <Alert className={`${config.borderColor} ${config.bgColor} border`}>
      <div className="flex items-start gap-3">
        <Icon className={`h-4 w-4 mt-0.5 ${config.iconColor}`} />

        <div className="flex-1 space-y-2">
          <AlertDescription className="text-foreground/90">
            {children || message || (
              <>
                {state === "request" && (
                  <>
                    <div className="font-semibold mb-2">
                      🤖 执行计划确认
                    </div>
                    {taskSummary ? (
                      <div className="space-y-3">
                        {taskSummary.goal && (
                          <div className="text-sm">
                            <span className="text-muted-foreground">目标：</span>
                            <span className="text-foreground/90">{taskSummary.goal}</span>
                          </div>
                        )}
                        {taskSummary.tools && taskSummary.tools.length > 0 && (
                          <div className="space-y-2">
                            <div className="text-sm text-muted-foreground">
                              计划执行 {taskSummary.tools.length} 个工具调用：
                            </div>
                            <div className="space-y-1 max-h-60 overflow-y-auto">
                              {taskSummary.tools.map((tool, idx) => (
                                <div key={idx} className="text-xs bg-card/30 p-2 rounded">
                                  <div className="font-mono text-foreground/80">
                                    {idx + 1}. {tool.name}
                                  </div>
                                  {tool.arguments && Object.keys(tool.arguments).length > 0 && (
                                    <div className="mt-1 text-muted-foreground text-[11px] font-mono">
                                      {JSON.stringify(tool.arguments, null, 2).split('\n').slice(0, 3).join('\n')}
                                      {JSON.stringify(tool.arguments, null, 2).split('\n').length > 3 && '...'}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="text-sm text-green-400/80 bg-green-500/10 border border-green-500/20 rounded p-2">
                          ✓ 确认后将自动执行所有步骤，无需再次确认
                        </div>
                      </div>
                    ) : (
                      <>
                        {toolName && (
                          <div className="text-sm text-foreground/70 mb-2">
                            工具: <code className="bg-card/30 px-1 py-0.5 rounded">{toolName}</code>
                          </div>
                        )}
                        {args && Object.keys(args).length > 0 && (
                          <div className="text-xs text-muted-foreground bg-card/20 p-2 rounded font-mono">
                            {JSON.stringify(args, null, 2)}
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}
                {state === "accepted" && "✅ 已确认，正在自动执行所有步骤..."}
                {state === "rejected" && "❌ 已拒绝执行"}
              </>
            )}
          </AlertDescription>

          {state === "request" && (onAccept || onReject) && (
            <div className="flex gap-2 pt-1">
              {onAccept && (
                <Button
                  size="sm"
                  onClick={onAccept}
                  className="bg-green-600 hover:bg-green-700 text-foreground h-8 text-sm px-4"
                >
                  ✓ 确认执行
                </Button>
              )}
              {onReject && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onReject}
                  className="border-red-500/30 hover:bg-red-500/20 text-foreground/80 h-8 text-sm px-4"
                >
                  ✗ 拒绝
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </Alert>
  )
}
