import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"
import type { Material } from "@/lib/mock-data"
import { formatBeijingDateTime } from "@/lib/time"

const VIDEO_EXTENSIONS = ["mp4", "avi", "mov", "wmv", "flv", "mkv"]
const IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "bmp", "webp"]

function detectType(filename: string | undefined): Material["type"] {
  if (!filename) return "other"
  const ext = filename.split(".").pop()?.toLowerCase()
  if (!ext) return "other"
  if (VIDEO_EXTENSIONS.includes(ext)) return "video"
  if (IMAGE_EXTENSIONS.includes(ext)) return "image"
  return "other"
}

function toFiniteNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0
  if (typeof value === "string" && value.trim()) {
    const cleaned = value.replace(/mb$/i, "").trim()
    const parsed = Number(cleaned)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function toOptionalInt(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value)
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return Math.trunc(parsed)
  }
  return undefined
}

function parseTags(value: unknown): string | undefined {
  if (!value) return undefined
  if (Array.isArray(value)) {
    const tags = value.map((t) => String(t).trim()).filter(Boolean)
    return tags.length ? tags.join(" ") : undefined
  }
  if (typeof value === "string") {
    const raw = value.trim()
    if (!raw) return undefined
    // 支持 JSON 数组形式
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        const tags = parsed.map((t) => String(t).trim()).filter(Boolean)
        return tags.length ? tags.join(" ") : undefined
      }
    } catch {
      // ignore
    }
    return raw
  }
  return undefined
}

function formatDate(value: unknown) {
  if (!value) return formatBeijingDateTime(new Date())
  const date = new Date(value as string)
  if (Number.isNaN(date.getTime())) {
    return formatBeijingDateTime(new Date())
  }
  return formatBeijingDateTime(date)
}

export async function GET(request: Request) {
  try {
    const url = new URL(request.url)
    const query = url.searchParams.toString()

    const response = await fetch(`${backendBaseUrl}/api/v1/files/${query ? `?${query}` : ""}`, {
      cache: "no-store",
    })

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`)
    }

    const payload = await response.json()
    const rows: unknown[] = Array.isArray(payload?.items) ? payload.items : Array.isArray(payload?.data) ? payload.data : []

    const materials: Material[] = rows.map((row, index) => {
      const record = row as Record<string, unknown>
      const id = record?.id ?? index
      const filename = (record?.filename as string) ?? (record?.name as string) ?? "未命名文件"
      const filePath = (record?.file_path as string) ?? ""
      const rawStatus = typeof record?.status === "string" ? record.status : ""
      const status: Material["status"] = rawStatus === "published" ? "published" : "pending"
      const filesizeMb = toFiniteNumber(record?.filesize)
      const durationSeconds = toFiniteNumber(record?.duration)
      const videoWidth = toOptionalInt(record?.video_width)
      const videoHeight = toOptionalInt(record?.video_height)
      const aspectRatio = typeof record?.aspect_ratio === "string" ? record.aspect_ratio : undefined
      const orientation = typeof record?.orientation === "string" ? record.orientation : undefined

      const title = (typeof record?.ai_title === "string" && record.ai_title.trim())
        ? (record.ai_title as string)
        : (typeof record?.title === "string" ? (record.title as string) : undefined)
      const description = (typeof record?.ai_description === "string" && record.ai_description.trim())
        ? (record.ai_description as string)
        : (typeof record?.description === "string" ? (record.description as string) : undefined)
      const tags = parseTags(record?.ai_tags) ?? parseTags(record?.tags)
      const coverImage = typeof record?.cover_image === "string" ? (record.cover_image as string) : undefined

      return {
        id: String(id),
        filename,
        filesize: filesizeMb,
        uploadTime: formatDate(record?.upload_time),
        type: detectType(filename),
        fileUrl: filePath
          ? `${backendBaseUrl}/getFile?filename=${encodeURIComponent(filePath)}`
          : "",
        storageKey: filePath || undefined,
        status,
        publishedAt: record?.published_at
          ? formatBeijingDateTime(record.published_at as string)
          : undefined,
        note: typeof record?.note === "string" ? (record.note as string) : undefined,
        group: typeof record?.group_name === "string" ? (record.group_name as string) : undefined,
        title,
        description,
        tags,
        cover_image: coverImage,
        duration: durationSeconds ? Math.round(durationSeconds) : undefined,
        video_width: videoWidth,
        video_height: videoHeight,
        aspect_ratio: aspectRatio,
        orientation,
      }
    })
    // 暂时移除视频过滤，显示所有素材
    // .filter((material) => material.type === "video")

    console.log(`[/api/materials] Returning ${materials.length} materials`)

    return NextResponse.json({
      code: 200,
      msg: "success",
      data: {
        data: materials,
        total: materials.length,
        timestamp: Date.now(),
      }
    })
  } catch (error) {
    console.error("Failed to load materials from backend:", error)
    return NextResponse.json({
      code: 500,
      msg: "error",
      data: {
        data: [],
        total: 0,
        timestamp: Date.now()
      }
    }, { status: 502 })
  }
}
