import { NextRequest, NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"
import type { PlatformKey } from "@/lib/mock-data"
import { formatBeijingDateTime } from "@/lib/time"

const platformMap: Record<number, PlatformKey> = {
  1: "xiaohongshu",
  2: "channels",
  3: "douyin",
  4: "kuaishou",
  5: "bilibili",
  6: "tiktok",
  7: "youtube",
}

const statusMap: Record<string, "正常" | "异常" | "待激活" | "在线"> = {
  valid: "正常",
  expired: "异常",
  error: "异常",
  active: "正常",
  在线: "在线",
  正常: "正常",
  过期: "异常",
}

const ACCOUNT_PAGE_SIZE = 1000

export async function GET(request: NextRequest) {
  try {
    const requestedLimit = Number(request.nextUrl.searchParams.get("limit"))
    const fetchAll = request.nextUrl.searchParams.get("all") === "true"
    const limit = Number.isFinite(requestedLimit) && requestedLimit > 0
      ? Math.min(Math.floor(requestedLimit), ACCOUNT_PAGE_SIZE)
      : ACCOUNT_PAGE_SIZE

    const response = await fetch(
      `${backendBaseUrl}/api/v1/accounts/?skip=0&limit=${limit}`,
      { cache: "no-store" }
    )
    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`)
    }

    const payload = await response.json()
    const firstPage = Array.isArray(payload?.items) ? payload.items : []
    const total = Number(payload?.total ?? firstPage.length)
    let allItems = firstPage

    if (fetchAll && total > firstPage.length) {
      const pageRequests: Promise<unknown>[] = []
      for (let skip = firstPage.length; skip < total; skip += ACCOUNT_PAGE_SIZE) {
        pageRequests.push(
          fetch(`${backendBaseUrl}/api/v1/accounts/?skip=${skip}&limit=${ACCOUNT_PAGE_SIZE}`, {
            cache: "no-store",
          }).then(async (pageResponse) => {
            if (!pageResponse.ok) {
              throw new Error(`Backend responded with ${pageResponse.status}`)
            }
            return pageResponse.json()
          })
        )
      }
      const remainingPages = await Promise.all(pageRequests)
      allItems = [
        ...firstPage,
        ...remainingPages.flatMap((page: any) => Array.isArray(page?.items) ? page.items : []),
      ]
    }

    // FastAPI response format: { success: true, total: N, items: [...] }
    const rows: Array<Record<string, unknown>> = allItems.length > 0
      ? allItems
      : Array.isArray(payload?.accounts)
        ? payload.accounts.flatMap((group: any) => group?.accounts || [])
        : Array.isArray(payload?.result?.accounts)
          ? payload.result.accounts
          : Array.isArray(payload?.result)
            ? payload.result
            : []

    const accounts = await Promise.all(
      rows.map(async (row) => {
        const id = row?.id ?? row?.account_id
        const platformCode = row?.platform_code ?? row?.platformCode
        const filePath = (row?.filePath as string) ?? (row?.cookie_file as string) ?? undefined
        const userName = (row?.name as string) ?? (row?.userName as string)
        const statusValue = row?.status

        const codeNumber = Number(platformCode)
        const effectivePlatform = platformMap[codeNumber] ?? "douyin"
        const displayName = userName && String(userName).trim() ? String(userName) : `账号 ${id ?? ""}`
        let statusKey = typeof statusValue === "string" ? statusValue.toLowerCase() : undefined
        if (!statusKey && typeof statusValue === "number") {
          statusKey = statusValue === 1 ? "valid" : "expired"
        }
        const resolvedStatus = statusMap[statusKey ?? "valid"] ?? "待激活"

        return {
          id: String(id ?? ""),
          name: displayName,
          platform: effectivePlatform,
          status: resolvedStatus,
          avatar: (row?.avatar as string) || `https://api.dicebear.com/9.x/identicon/svg?seed=${encodeURIComponent(displayName)}`,
          boundAt: formatBeijingDateTime(
            typeof row?.last_checked === "string" || typeof row?.last_checked === "number"
              ? (row.last_checked as string | number)
              : Date.now()
          ),
          filePath,
          user_id: (row?.user_id as string) ?? null,
          original_name: (row?.original_name as string) ?? null,
          note: (row?.note as string) ?? null,
          login_status: (row?.login_status as string) ?? null,
        }
      })
    )

    return NextResponse.json({
      code: 200,
      msg: null,
      data: accounts,
    })
  } catch (error) {
    console.error("Failed to load accounts from backend:", error)
    return NextResponse.json({ code: 500, msg: "Failed to load accounts", data: [] }, { status: 500 })
  }
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url)
  const id = searchParams.get("id")

  if (!id) {
    return NextResponse.json({ error: "Missing account ID" }, { status: 400 })
  }

  try {
    // FastAPI DELETE endpoint: /api/v1/accounts/{id}
    const response = await fetch(`${backendBaseUrl}/api/v1/accounts/${id}`, {
      method: "DELETE",
      cache: "no-store",
    })
    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`)
    }
    const payload = await response.json()
    return NextResponse.json(payload)
  } catch (error) {
    console.error("Failed to delete account:", error)
    return NextResponse.json({ error: "Failed to delete account" }, { status: 500 })
  }
}
