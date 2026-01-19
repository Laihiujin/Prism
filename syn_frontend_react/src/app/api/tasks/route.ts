import { NextResponse } from "next/server"
import crypto from "crypto"

import { backendBaseUrl } from "@/lib/env"
import type { TaskRecord, TaskStatus } from "./tasks-store"

const platformDisplay: Record<string, string> = {
  "1": "小红书",
  "2": "视频号",
  "3": "抖音",
  "4": "快手",
  "5": "B站",
}

const normalizeStatus = (value: unknown, hasSchedule: boolean): TaskStatus => {
  const raw = typeof value === "string" ? value.toLowerCase() : ""
  if (raw === "success" || raw === "published" || raw === "done") return "success"
  if (raw === "error" || raw === "failed" || raw === "fail") return "error"
  if (raw === "cancelled") return "cancelled"
  if (raw === "running") return "running"
  if (hasSchedule) return "scheduled"
  return "pending"
}

const resolvePlatformName = (value: unknown): string => {
  const key = typeof value === "number" ? String(value) : String(value || "").trim()
  if (platformDisplay[key]) return platformDisplay[key]
  const lower = key.toLowerCase()
  if (lower.includes("douyin")) return "抖音"
  if (lower.includes("kuaishou")) return "快手"
  if (lower.includes("hongshu") || lower.includes("redbook") || lower.includes("xhs")) return "小红书"
  if (lower.includes("bili")) return "B站"
  if (lower.includes("video") || lower.includes("channel") || lower.includes("shipin")) return "视频号"
  return key || "未知平台"
}



const buildSummaryFromTasks = (tasks: TaskRecord[]) => {
  const summary = { scheduled: 0, success: 0, error: 0, pending: 0, total: tasks.length }
  tasks.forEach((task) => {
    if (task.status === "success") summary.success += 1
    else if (task.status === "error") summary.error += 1
    else if (task.status === "scheduled") summary.scheduled += 1
    else summary.pending += 1
  })
  return summary
}

// 获取账号映射 Map<id, name>
const fetchAccountsMap = async () => {
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/accounts/`, { cache: "no-store" })
    if (!response.ok) return new Map<string, string>()
    const payload = await response.json().catch(() => ({}))
    const items = Array.isArray(payload?.items) ? payload.items : []
    const map = new Map<string, string>()
    items.forEach((item: {
      account_id?: string | number
      id?: string | number
      accountId?: string | number
      user_id?: string | number
      userId?: string | number
      original_name?: string
      name?: string
      nickname?: string
      note?: string
    }) => {
      const rawId = item.account_id ?? item.id ?? item.accountId
      const userId = item.user_id ?? item.userId
      if (!rawId && !userId) return
      const displayName =
        item.original_name ||
        item.name ||
        item.nickname ||
        item.note ||
        `账号 ${rawId ?? userId ?? ""}`
      if (rawId) {
        map.set(String(rawId), String(displayName))
      }
      if (userId) {
        map.set(String(userId), String(displayName))
      }
    })
    return map
  } catch (e) {
    console.error("Failed to fetch accounts map", e)
    return new Map<string, string>()
  }
}

// 获取素材映射 Map<id, filename>
const fetchMaterialsMap = async () => {
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/files/`, { cache: "no-store" })
    if (!response.ok) return new Map<string, string>()
    const payload = await response.json().catch(() => ({}))
    const items = Array.isArray(payload?.items) ? payload.items : []
    const map = new Map<string, string>()
    items.forEach((item: { id?: string | number; filename?: string }) => {
      if (item.id) map.set(String(item.id), item.filename || "未知文件")
    })
    return map
  } catch (e) {
    console.error("Failed to fetch materials map", e)
    return new Map<string, string>()
  }
}

const formatTaskQueueRow = (row: any, accountMap: Map<string, string>, materialMap: Map<string, string>): TaskRecord => {
  const payload = row?.data && typeof row.data === "object" ? (row.data as Record<string, unknown>) : {}
  const schedule = (payload.schedule_time as string) ?? (payload.scheduleTime as string)
  const status = normalizeStatus(row?.status, Boolean(schedule))
  const platformRaw = payload.platform ?? payload.platform_code ?? payload.platformCode ?? row?.task_type

  const materialId = String(payload.material_id ?? payload.file_id ?? payload.video_path ?? payload.file_path ?? payload.material ?? "")
  const accountId = String(payload.account_id ?? payload.account ?? payload.user_id ?? "")

  // 尝试从映射获取，如果失败则尝试解析文件名
  let materialName = materialMap.get(materialId)
  if (!materialName && materialId) {
    materialName = materialId.split('\\').pop()?.split('/').pop() || "-"
  }

  return {
    id: String(row?.task_id ?? crypto.randomUUID()),
    title: ((payload.title as string) ?? (payload.name as string) ?? (row?.task_type as string) ?? "任务").trim() || "任务",
    platform: resolvePlatformName(platformRaw),
    account: accountMap.get(accountId) || accountId || "-",
    material: materialName || "-",
    status,
    createdAt: (row?.created_at as string) ?? new Date().toISOString(),
    scheduledAt: schedule ? String(schedule) : undefined,
    result: undefined,
    source: "queue" as const,
  }
}

const fetchTaskQueueRecords = async (accountMap: Map<string, string>, materialMap: Map<string, string>) => {
  try {
    console.log("[fetchTaskQueueRecords] Fetching from:", `${backendBaseUrl}/api/v1/tasks/`)
    const response = await fetch(`${backendBaseUrl}/api/v1/tasks/`, { cache: "no-store" })
    console.log("[fetchTaskQueueRecords] Response status:", response.status, response.ok)

    if (!response.ok) {
      console.log("[fetchTaskQueueRecords] Response not ok, returning null")
      return null
    }

    const payload = await response.json().catch(() => ({}))
    console.log("[fetchTaskQueueRecords] Raw payload:", JSON.stringify(payload).slice(0, 500))
    console.log("[fetchTaskQueueRecords] Payload keys:", Object.keys(payload))
    console.log("[fetchTaskQueueRecords] payload.data type:", Array.isArray(payload?.data), "length:", payload?.data?.length)

    const rows: any[] = Array.isArray(payload?.data) ? payload.data : []
    console.log("[fetchTaskQueueRecords] Rows count:", rows.length)

    if (rows.length > 0) {
      console.log("[fetchTaskQueueRecords] First row sample:", JSON.stringify(rows[0]).slice(0, 300))
    }

    const tasks = rows.map(row => formatTaskQueueRow(row, accountMap, materialMap))
    console.log("[fetchTaskQueueRecords] Formatted tasks count:", tasks.length)

    const rawSummary = payload?.summary
    const summary = rawSummary ? {
      scheduled: rawSummary.scheduled ?? 0,
      success: rawSummary.success ?? rawSummary.completed ?? 0,
      error: rawSummary.error ?? rawSummary.failed ?? 0,
      pending: (rawSummary.pending ?? 0) + (rawSummary.retry ?? 0) + (rawSummary.queued ?? 0),
      total: rawSummary.total ?? tasks.length
    } : buildSummaryFromTasks(tasks)

    console.log("[fetchTaskQueueRecords] Final summary:", summary)
    return { tasks, summary }
  } catch (error) {
    console.error("Failed to load task queue records", error)
    return null
  }
}

const fetchPublishHistory = async (accountMap: Map<string, string>, materialMap: Map<string, string>) => {
  try {
    console.log("[fetchPublishHistory] Fetching from:", `${backendBaseUrl}/api/v1/publish/history?limit=200`)
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/history?limit=200`, { cache: "no-store" })
    console.log("[fetchPublishHistory] Response status:", response.status, response.ok)

    if (!response.ok) {
      console.log("[fetchPublishHistory] Response not ok, returning null")
      return null
    }

    const payload = await response.json().catch(() => ({}))
    console.log("[fetchPublishHistory] Success:", payload.success, "Data count:", payload.data?.length)

    if (!payload.success || !Array.isArray(payload.data)) {
      console.log("[fetchPublishHistory] Invalid payload format")
      return null
    }

    const rows: any[] = payload.data

    const tasks: TaskRecord[] = rows.map((row) => {
      const platform = String(row?.platform ?? "")
      const platformName = platformDisplay[platform] || platform || "未知平台"
      const schedule = (row?.schedule_time as string) || undefined
      const status = normalizeStatus(row?.status, Boolean(schedule))

      const accountId = String(row?.account_id ?? "")
      const materialId = String(row?.material_id ?? "")

      // 改进素材显示：如果找不到映射，显示友好提示
      let materialDisplay = materialMap.get(materialId)
      if (!materialDisplay && materialId) {
        // 如果素材ID不在映射中，可能是已删除的素材
        materialDisplay = `素材 #${materialId} (已删除)`
      }
      if (!materialDisplay) {
        materialDisplay = "-"
      }

      return {
        id: String(row?.task_id ?? crypto.randomUUID()),
        title: (String(row?.title ?? "发布任务").trim() || "发布任务"),
        platform: platformName,
        account: accountMap.get(accountId) || accountId || "-",
        material: materialDisplay,
        status,
        createdAt: (row?.created_at as string) ?? new Date().toISOString(),
        scheduledAt: schedule,
        result: (row?.error_message as string) ?? undefined,
        source: "history" as const,
      }
    })

    console.log("[fetchPublishHistory] Formatted tasks count:", tasks.length)
    return { tasks, summary: buildSummaryFromTasks(tasks) }
  } catch (error) {
    console.error("[fetchPublishHistory] Failed to load publish history", error)
    return null
  }
}

export async function GET() {
  try {
    console.log("[/api/tasks] ========== START ==========")
    console.log("[/api/tasks] Backend URL:", backendBaseUrl)

    // 并行获取辅助数据
    const [accountMap, materialMap] = await Promise.all([
      fetchAccountsMap(),
      fetchMaterialsMap()
    ])
    console.log("[/api/tasks] AccountMap size:", accountMap.size)
    console.log("[/api/tasks] MaterialMap size:", materialMap.size)

    const queueData = await fetchTaskQueueRecords(accountMap, materialMap)
    console.log("[/api/tasks] Queue data fetched:", queueData ? "success" : "failed")
    if (queueData) {
      console.log("[/api/tasks] Queue data tasks count:", queueData.tasks.length)
    }

    // 如果队列为空（没有任务或者查询失败），则加载历史记录
    let finalData = queueData
    if (!queueData || queueData.tasks.length === 0) {
      console.log("[/api/tasks] Queue is empty, fetching publish history...")
      const historyData = await fetchPublishHistory(accountMap, materialMap)
      console.log("[/api/tasks] History data fetched:", historyData ? "success" : "failed")
      if (historyData) {
        console.log("[/api/tasks] History data tasks count:", historyData.tasks.length)
        finalData = historyData
      }
    }

    const tasks = finalData?.tasks ?? []
    const finalSummary = finalData?.summary ?? buildSummaryFromTasks(tasks)

    console.log(`[/api/tasks] ========== 返回 ${tasks.length} 个任务 ==========`)
    console.log(`[/api/tasks] Final summary:`, finalSummary)

    return NextResponse.json({
      code: 200,
      msg: null,
      data: tasks,
      total: tasks.length,
      summary: finalSummary,
      updatedAt: Date.now(),
    })
  } catch (error) {
    console.error("[/api/tasks] ========== ERROR ==========", error)
    return NextResponse.json({ code: 500, msg: "failed to load tasks", data: [] }, { status: 500 })
  }
}

export async function POST() {
  return NextResponse.json({ code: 405, msg: "Not supported" }, { status: 405 })
}
