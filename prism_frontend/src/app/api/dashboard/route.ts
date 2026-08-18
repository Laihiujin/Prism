import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"
import { dashboardSchema } from "@/lib/schemas"

export async function GET() {
  try {
    const [statsRes, tasksRes] = await Promise.all([
      fetch(`${backendBaseUrl}/api/v1/dashboard/stats`, { cache: "no-store" }),
      fetch(`${backendBaseUrl}/api/v1/publish/history?limit=500`, { cache: "no-store" }),
    ])

    const statsPayload = await statsRes.json().catch(() => ({}))
    const tasksPayload = await tasksRes.json().catch(() => ({}))

    // FastAPI 响应格式: { success: true, data: [...] }
    const rawTasks: any[] = Array.isArray(tasksPayload?.data) ? tasksPayload.data : []
    const tasks = rawTasks.map((row) => ({
      id: String(row?.task_id ?? row?.id ?? Math.random().toString(36).slice(2)),
      title: ((row?.title as string) ?? "发布任务").trim() || "发布任务",
      platform: (row?.platform as string) ?? "",
      account: (row?.account_id as string) ?? "-",
      material: (row?.material_id as string) ?? "-",
      status: (row?.status as string) ?? "pending",
      createdAt: (row?.created_at as string) ?? new Date().toISOString(),
      scheduledAt: (row?.schedule_time as string) || undefined,
      result: (row?.error_message as string) || undefined,
    }))

    const normalized = {
      accounts: {
        total: statsPayload?.data?.accounts?.total ?? 0,
        byStatus: statsPayload?.data?.accounts?.by_status ?? {},
        byPlatform: statsPayload?.data?.accounts?.by_platform ?? {},
      },
      materials: {
        total: statsPayload?.data?.materials?.total ?? 0,
        byStatus: statsPayload?.data?.materials?.by_status ?? {},
        lastUpload: statsPayload?.data?.materials?.last_upload ?? null,
      },
      publish: {
        todaysPublish: statsPayload?.data?.publish?.todays_publish ?? 0,
        pendingAlerts: statsPayload?.data?.publish?.pending_alerts ?? 0,
      },
      tasks,
      timestamp: Date.now(),
    }

    // validate shape (throws if invalid)
    dashboardSchema.parse({ code: 200, msg: null, data: normalized })

    return NextResponse.json({
      code: 200,
      msg: null,
      data: normalized,
    })
  } catch (error) {
    console.error("Failed to load dashboard data", error)
    return NextResponse.json(
      { code: 500, msg: "failed to load dashboard", data: null },
      { status: 500 }
    )
  }
}
