/**
 * OpenManus 流式执行 Hook
 * 处理 SSE 流式接收 Agent 执行状态
 */

import { useCallback, useRef, useState } from "react"
import { API_ENDPOINTS } from "@/lib/env"

export interface ManusEvent {
  type: "init" | "thinking" | "plan" | "confirmation_required" | "confirmation_received" | "tool_call" | "step_complete" | "final_result" | "error" | "done"
  status?: string
  message?: string
  content?: string
  plan?: {
    goal?: string
    estimated_steps?: string | number
    available_tools?: Array<{ name: string; description: string }>
    strategy?: string
  }
  step?: number
  tool_name?: string
  arguments?: string | object
  result?: any
  error?: string
  approved?: boolean
}

export interface ManusStreamState {
  isStreaming: boolean
  events: ManusEvent[]
  currentThinking: string
  currentPlan: any | null
  toolCalls: Array<{
    step?: number
    toolName: string
    arguments?: string | object
    result?: any
    error?: string
    status?: "pending" | "running" | "success" | "error"
  }>
  tasks: Array<{
    id: string
    name: string
    status: "pending" | "in-progress" | "completed" | "failed"
    metadata?: Record<string, any>
  }>
  finalResult: any | null
  error: string | null
}

export function useManusStream() {
  const [state, setState] = useState<ManusStreamState>({
    isStreaming: false,
    events: [],
    currentThinking: "",
    currentPlan: null,
    toolCalls: [],
    tasks: [],
    finalResult: null,
    error: null
  })

  const eventSourceRef = useRef<EventSource | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const resetState = useCallback(() => {
    // 终止正在进行的流，避免切换线程/模式后继续往旧 UI 写入事件
    try {
      abortControllerRef.current?.abort()
    } catch {
      // ignore
    }
    abortControllerRef.current = null
    setState({
      isStreaming: false,
        events: [],
      currentThinking: "",
      currentPlan: null,
      toolCalls: [],
      tasks: [],
      finalResult: null,
      error: null
    })
  }, [])

  const startStreaming = useCallback(
    async (
      goal: string,
      context?: any,
      requireConfirmation: boolean = false,
      threadId?: string
    ) => {
      // 重置状态
      resetState()

      // 终止旧的流
      abortControllerRef.current?.abort()
      const controller = new AbortController()
      abortControllerRef.current = controller

      // 创建 POST 请求发送数据
      const response = await fetch(
        `${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/agent/manus-stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          signal: controller.signal,
          body: JSON.stringify({
            goal,
            context,
            thread_id: threadId,
            require_confirmation: requireConfirmation
          })
        }
      )

      if (!response.ok) {
        const errorText = await response.text()
        const message = `HTTP ${response.status}: ${errorText}`
        setState(prev => ({
          ...prev,
          isStreaming: false,
          error: message,
          events: [...prev.events, { type: "error", error: message } as ManusEvent]
        }))
        return
      }

      // 创建 EventSource 从 streaming response 读取
      const reader = response.body?.getReader()
      if (!reader) {
        const message = "No response body"
        setState(prev => ({
          ...prev,
          isStreaming: false,
          error: message,
          events: [...prev.events, { type: "error", error: message } as ManusEvent]
        }))
        return
      }

      setState(prev => ({ ...prev, isStreaming: true }))

      const decoder = new TextDecoder()
      let buffer = ""

      try {
        while (true) {
          const { value, done } = await reader.read()

          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // 处理可能的多个事件
          const lines = buffer.split("\n\n")
          buffer = lines.pop() || ""

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const eventData = JSON.parse(line.substring(6)) as ManusEvent
                handleEvent(eventData)
              } catch (parseError) {
                console.error("Failed to parse SSE event:", parseError, line)
              }
            }
          }
        }
      } catch (error) {
        // Abort 属于正常中断（切线程/切模式/用户停止），不当做错误展示
        if (error instanceof DOMException && error.name === "AbortError") {
          setState(prev => ({ ...prev, isStreaming: false }))
          return
        }
        console.error("Stream reading error:", error)
        const message = error instanceof Error ? error.message : String(error)
        setState(prev => ({
          ...prev,
          isStreaming: false,
          error: message,
          events: [...prev.events, { type: "error", error: message } as ManusEvent]
        }))
      }
    },
    [resetState]
  )

  const handleEvent = useCallback((event: ManusEvent) => {
    setState(prev => {
      const newEvents = [...prev.events, event]

      // 根据事件类型更新状态
      switch (event.type) {
        case "init":
          return {
            ...prev,
            events: newEvents,
            currentThinking: event.message || ""
          }

        case "thinking":
          return {
            ...prev,
            events: newEvents,
            currentThinking: event.content || ""
          }

        case "plan":
          return {
            ...prev,
            events: newEvents,
            currentPlan: event.plan
          }

        case "tool_call":
          // 添加新的工具调用
          const newToolCall = {
            step: event.step,
            toolName: event.tool_name || "unknown",
            arguments: event.arguments,
            status: "running" as const
          }

          // 同时添加到任务队列
          const newTask = {
            id: `task-${event.step}`,
            name: event.tool_name || "unknown",
            status: "in-progress" as const,
            metadata: { args: event.arguments }
          }

          return {
            ...prev,
            events: newEvents,
            toolCalls: [...prev.toolCalls, newToolCall],
            tasks: [...prev.tasks, newTask]
          }

        case "step_complete":
          // 更新对应步骤的工具调用结果
          const updatedToolCalls = prev.toolCalls.map((call, idx) =>
            call.step === event.step
              ? { ...call, result: event.result, status: "success" as const }
              : call
          )

          const updatedTasks = prev.tasks.map((task, idx) =>
            task.id === `task-${event.step}`
              ? { ...task, status: "completed" as const, metadata: { ...task.metadata, result: event.result } }
              : task
          )

          return {
            ...prev,
            events: newEvents,
            toolCalls: updatedToolCalls,
            tasks: updatedTasks
          }

        case "final_result":
          return {
            ...prev,
            events: newEvents,
            finalResult: event.result,
            isStreaming: false
          }

        case "error":
          return {
            ...prev,
            events: newEvents,
            error: event.error || event.message || "Unknown error",
            isStreaming: false
          }

        case "done":
          return {
            ...prev,
            events: newEvents,
            isStreaming: false
          }

        default:
          return {
            ...prev,
            events: newEvents
          }
      }
    })
  }, [])

  const stopStreaming = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    try {
      abortControllerRef.current?.abort()
    } catch {
      // ignore
    }
    abortControllerRef.current = null

    // 调用后端停止 API
    fetch(`${API_ENDPOINTS.base || 'http://localhost:7000'}/api/v1/agent/manus-stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).catch(err => console.error('Failed to stop Manus task:', err))

    setState(prev => ({ ...prev, isStreaming: false }))
  }, [])



  return {
    ...state,
    startStreaming,
    stopStreaming,
    resetState
  }
}