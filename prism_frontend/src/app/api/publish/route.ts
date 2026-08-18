import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"
import { quickActions, recommendedTopics } from "@/lib/mock-data"

interface PublishTask {
  platformCode: number
  fileList: string[]
  accountList: string[]
  title: string
  description?: string  // 添加description字段
  tags: string[]
  enableTimer?: boolean
  videosPerDay?: number
  scheduleTime?: string
  scheduleTimes?: string[]
  startDays?: number
  category?: number | null
  productLink?: string
  productTitle?: string
  thumbnail?: string
}

const timeToNumber = (value: string) => {
  if (!value) return null
  const normalized = value.replace(/：/g, ":").trim()
  const [hour, minute] = normalized.split(":")
  if (!hour) return null
  const h = Number.parseInt(hour, 10)
  const m = minute ? Number.parseInt(minute, 10) : 0
  if (Number.isNaN(h) || Number.isNaN(m)) return null
  return h * 100 + m
}

const normalizeTasks = (tasks: PublishTask[]) =>
  tasks.map((task) => {
    let dailyTimes =
      task.scheduleTimes
        ?.map((time) => timeToNumber(time))
        .filter((value): value is number => typeof value === "number") ?? []
    if (!dailyTimes.length && task.scheduleTime) {
      const slot = timeToNumber(task.scheduleTime)
      if (slot !== null) dailyTimes = [slot]
    }

    return {
      type: task.platformCode,
      fileList: task.fileList,
      accountList: task.accountList,
      title: task.title,
      description: task.description || "",  // 添加description字段
      tags: task.tags,
      enableTimer: Boolean(task.enableTimer),
      videosPerDay: task.videosPerDay ?? 1,
      dailyTimes,
      startDays: task.startDays ?? 0,
      category: task.category ?? null,
      productLink: task.productLink ?? "",
      productTitle: task.productTitle ?? "",
      thumbnail: task.thumbnail ?? "",
    }
  })

export async function GET() {
  const defaultPlatforms = [
    { code: 3, name: "抖音", enabled: true },
    { code: 4, name: "快手", enabled: true },
    { code: 2, name: "视频号", enabled: true },
    { code: 1, name: "小红书", enabled: true },
  ]

  const defaultCategories = [
    { id: 0, name: "默认" },
    { id: 160, name: "B站-生活" },
  ]

  const normalizeArray = (value: any): string[] => {
    if (Array.isArray(value)) return value.map(String)
    if (typeof value === "string") {
      try {
        const parsed = JSON.parse(value)
        return Array.isArray(parsed) ? parsed.map(String) : value.split(',').map((v) => v.trim()).filter(Boolean)
      } catch {
        return value.split(',').map((v) => v.trim()).filter(Boolean)
      }
    }
    return []
  }

  const normalizePlatform = (value: any): string => {
    const map: Record<string, string> = {
      "1": "xiaohongshu",
      "2": "channels",
      "3": "douyin",
      "4": "kuaishou",
    }
    const first = Array.isArray(value) ? value[0] : value
    const key = String(first ?? "douyin").toLowerCase()
    if (map[key]) return map[key]
    if (key.includes("douyin")) return "douyin"
    if (key.includes("kuaishou")) return "kuaishou"
    if (key.includes("xhs") || key.includes("hongshu")) return "xiaohongshu"
    if (key.includes("video") || key.includes("shipinhao") || key.includes("channels")) return "channels"
    return "douyin"
  }

  const normalizeTopics = (value: any): string[] => {
    if (Array.isArray(value)) return value.map((v) => String(v).trim()).filter(Boolean)
    if (typeof value === "string") return value.split(/[，,\s]+/).map((v) => v.trim()).filter(Boolean)
    return []
  }

  const normalizePresets = (presets: any[]) =>
    presets.map((preset, index) => {
      const accounts = normalizeArray(preset.accounts)
      const materialIds = normalizeArray(preset.material_ids ?? preset.fileList)
      const topics = normalizeTopics(preset.topics ?? preset.tags ?? preset.default_tags)
      return {
        id: preset.id ?? preset.preset_id ?? `preset-${index + 1}`,
        label: preset.label || preset.name || `预设 ${index + 1}`,
        platform: normalizePlatform(preset.platform ?? preset.platforms ?? preset.platform_code),
        accounts,
        fileList: materialIds.map((name: string) => ({ name })),
        title: preset.title ?? preset.default_title ?? "",
        description: preset.description ?? "",
        topics,
        scheduleEnabled: Boolean(preset.schedule_enabled ?? preset.scheduleEnabled),
        videosPerDay: Number(preset.videos_per_day ?? preset.videosPerDay ?? 1) || 1,
        timePoint: preset.time_point ?? preset.timePoint ?? "10:00",
      }
    })

  let presets: any[] = []
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/presets`, { cache: "no-store" })
    const payload = await response.json().catch(() => ({}))
    const rawPresets = Array.isArray(payload?.data) ? payload.data : []
    presets = normalizePresets(rawPresets)
  } catch (error) {
    console.error("Failed to load publish presets from backend", error)
  }

  return NextResponse.json({
    code: 200,
    msg: null,
    data: {
      platforms: defaultPlatforms,
      categories: defaultCategories,
      presets,
      recommendedTopics,
      quickActions,
      timestamp: Date.now(),
    },
  })
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const tasks: PublishTask[] = Array.isArray(body?.tasks) ? body.tasks : []

    if (!tasks.length) {
      return NextResponse.json({ error: "tasks array is required" }, { status: 400 })
    }

    const sanitized = normalizeTasks(tasks).filter(
      (task) => task.fileList.length && task.accountList.length
    )

    if (!sanitized.length) {
      return NextResponse.json({ error: "No valid publish tasks" }, { status: 400 })
    }

    const response = await fetch(`${backendBaseUrl}/api/v1/publish/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sanitized),
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    console.error("Failed to dispatch publish tasks:", error)
    return NextResponse.json({ error: "Failed to dispatch publish tasks" }, { status: 500 })
  }
}
