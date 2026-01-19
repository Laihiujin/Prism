"use client"

import React from 'react'
import { Clock, Zap, Video } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

// 时间轴预览组件的属性接口
interface IntervalTimelinePreviewProps {
  mode: "account_first" | "video_first"
  intervalSeconds?: number
  randomOffset?: number
  videoCount: number
  accountCount: number
}

// 单个任务调度信息
interface ScheduledTask {
  videoIdx: number
  accountIdx: number
  time: Date
  offset: number
  label: string
}

// 格式化持续时间
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  if (hours > 0) {
    return `${hours}h${minutes}m`
  } else if (minutes > 0) {
    return `${minutes}m${secs > 0 ? `${secs}s` : ''}`
  } else {
    return `${secs}s`
  }
}

// 按时间分组辅助函数
function groupBy<T>(array: T[], keyFn: (item: T) => any): Record<string, T[]> {
  return array.reduce((acc, item) => {
    const key = String(keyFn(item))
    if (!acc[key]) acc[key] = []
    acc[key].push(item)
    return acc
  }, {} as Record<string, T[]>)
}

export default function IntervalTimelinePreview({
  mode,
  intervalSeconds = 300,
  randomOffset = 0,
  videoCount,
  accountCount
}: IntervalTimelinePreviewProps) {
  // 计算调度时间表
  const calculateSchedule = (): ScheduledTask[] => {
    const baseTime = new Date()
    const schedule: ScheduledTask[] = []

    // 限制显示数量以避免UI过载
    const maxVideos = Math.min(videoCount, 10)
    const maxAccounts = Math.min(accountCount, 5)

    for (let fileIdx = 0; fileIdx < maxVideos; fileIdx++) {
      for (let accountIdx = 0; accountIdx < maxAccounts; accountIdx++) {
        let offset = 0

        if (mode === "video_first") {
          // 所有账号同时发布同一视频
          offset = fileIdx * intervalSeconds
        } else {
          // account_first: 账号交错，每个账号的视频顺序发布
          offset = (accountIdx * intervalSeconds) + (fileIdx * intervalSeconds * maxAccounts)
        }

        const scheduledTime = new Date(baseTime.getTime() + offset * 1000)
        schedule.push({
          videoIdx: fileIdx,
          accountIdx,
          time: scheduledTime,
          offset,
          label: `A${accountIdx + 1}/V${fileIdx + 1}`
        })
      }
    }

    return schedule.sort((a, b) => a.offset - b.offset)
  }

  const schedule = calculateSchedule()
  const groupedByTime = groupBy(schedule, s => Math.floor(s.offset / 60)) // 按分钟分组

  // 计算总时长
  const totalDuration = schedule[schedule.length - 1]?.offset || 0
  const hours = Math.floor(totalDuration / 3600)
  const minutes = Math.floor((totalDuration % 3600) / 60)

  // 如果视频或账号数量为0，显示提示
  if (videoCount === 0 || accountCount === 0) {
    return (
      <div className="p-5 rounded-xl border border-white/10 bg-black/20 text-center text-white/40">
        <Clock className="w-8 h-8 mx-auto mb-2" />
        <p className="text-sm">请先选择视频和账号</p>
      </div>
    )
  }

  return (
    <div className="p-5 rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 to-purple-500/5">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold text-white flex items-center gap-2">
          <Clock className="w-4 h-4 text-primary" />
          发布时间轴预览
        </h4>
        <div className="text-xs text-white/60">
          {mode === "video_first" ? "视频优先" : "账号优先"} · 间隔 {intervalSeconds / 60}分钟
        </div>
      </div>

      {/* 时间轴可视化 */}
      <ScrollArea className="h-64 pr-4">
        <div className="space-y-2">
          {Object.entries(groupedByTime).map(([timeSlot, tasks]) => {
            const firstTask = tasks[0]
            const displayTime = firstTask.time.toLocaleTimeString('zh-CN', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            })

            return (
              <div key={timeSlot} className="flex items-start gap-3 group">
                {/* 时间标签 */}
                <div className="w-20 shrink-0">
                  <p className="text-sm font-mono text-primary font-medium">
                    {displayTime}
                  </p>
                  <p className="text-[10px] text-white/40">
                    +{formatDuration(firstTask.offset)}
                  </p>
                </div>

                {/* 任务徽章 */}
                <div className="flex-1 flex flex-wrap gap-1.5">
                  {tasks.map((task, idx) => (
                    <div
                      key={idx}
                      className="px-2 py-1 rounded-md text-[10px] font-medium bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 transition"
                      title={`账号${task.accountIdx + 1} 发布视频${task.videoIdx + 1}`}
                    >
                      A{task.accountIdx + 1}/V{task.videoIdx + 1}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>

        {/* 显示提示（如果有更多任务未显示） */}
        {(videoCount > 10 || accountCount > 5) && (
          <div className="mt-4 p-3 rounded-lg bg-white/5 border border-white/10 text-xs text-white/60 text-center">
            <Video className="w-4 h-4 inline mr-2" />
            仅显示前 {Math.min(videoCount, 10)} 个视频 × {Math.min(accountCount, 5)} 个账号的时间轴预览
          </div>
        )}
      </ScrollArea>

      {/* 汇总页脚 */}
      <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between text-xs">
        <div className="text-white/60 space-x-4">
          <span>总任务: <span className="text-white font-medium">{schedule.length}</span> 个</span>
          <span>总时长: <span className="text-white font-medium">{hours}h {minutes}m</span></span>
        </div>
        {randomOffset > 0 && (
          <div className="text-orange-400">
            <Zap className="inline w-3 h-3 mr-1" />
            包含 ±{randomOffset}s 随机偏移
          </div>
        )}
      </div>
    </div>
  )
}
