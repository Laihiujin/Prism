import { NextResponse } from "next/server"

import fs from "fs/promises"
import fsSync from "fs"
import path from "path"

import { formatBeijingClock, formatBeijingTime, getBeijingDayKey, parseLogTimestamp } from "@/lib/time"

const APP_ROOT = path.resolve(process.cwd(), "..")
const ENV_LOG_DIR = (process.env.LOG_DIR || "").trim()
const LOG_DIR_CANDIDATES = [
  ENV_LOG_DIR
    ? path.isAbsolute(ENV_LOG_DIR)
      ? ENV_LOG_DIR
      : path.resolve(APP_ROOT, ENV_LOG_DIR)
    : null,
  path.resolve(APP_ROOT, "syn_backend", "logs"),
  path.resolve(APP_ROOT, "logs"),
].filter(Boolean) as string[]
const LOG_DIR =
  LOG_DIR_CANDIDATES.find((candidate) => fsSync.existsSync(candidate)) ??
  path.resolve(APP_ROOT, "syn_backend", "logs")

const platforms = [
  { key: "kuaishou", label: "\u5feb\u624b", file: "kuaishou.log", account: "\u661f\u706b\u77e9\u9635" },
  { key: "tencent", label: "\u89c6\u9891\u53f7", file: "tencent.log", account: "\u89c6\u9891\u53f7\u77e9\u9635" },
  { key: "douyin", label: "\u6296\u97f3", file: "douyin.log", account: "\u77e9\u9635\u5b88\u62a4" },
]

interface ParsedLine {
  id: string
  timestamp: Date
  level: string
  message: string
  platform: string
}

async function readLogLines(fileName: string) {
  try {
    const file = await fs.readFile(path.join(LOG_DIR, fileName), "utf-8")
    return file.split(/\r?\n/).filter(Boolean)
  } catch {
    return []
  }
}

function parseLine(line: string, platform: string, index: number): ParsedLine | null {
  const match =
    line.match(
      /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{1,3})?) \| (\w+)\s+\|[^-]+-\s*(.+)$/
    ) ?? undefined
  if (!match) return null
  const timestamp = parseLogTimestamp(match[1])
  return {
    id: `${platform}-${index}`,
    timestamp,
    level: match[2].trim(),
    message: match[3].trim(),
    platform,
  }
}

export async function GET() {
  try {
    const parsed: ParsedLine[] = []
    const uploadTasks: ParsedLine[] = []
    const todayKey = getBeijingDayKey()

    for (const platform of platforms) {
      const lines = await readLogLines(platform.file)
      let lastFilename: string | null = null
      lines.forEach((line, lineIndex) => {
        const parsedLine = parseLine(line, platform.label, lineIndex)
        if (!parsedLine) return
        parsed.push(parsedLine)

        if (parsedLine.message.includes("\u6b63\u5728\u4e0a\u4f20")) {
          const fileNameMatch = parsedLine.message.split(/[-]+/).pop()
          lastFilename = fileNameMatch?.trim() ?? "\u6279\u91cf\u7d20\u6750"
        }

        if (parsedLine.message.includes("\u89c6\u9891\u53d1\u5e03\u6210\u529f")) {
          uploadTasks.push({
            ...parsedLine,
            message: lastFilename ?? "\u77e9\u9635\u5185\u5bb9",
            id: `${platform.key}-task-${lineIndex}`,
          })
          lastFilename = null
        }
      })
    }

    const tasks = uploadTasks
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, 6)
      .map((item) => ({
        id: item.id,
        title: item.message,
        platform: item.platform,
        account: `${item.platform} \u00b7 \u81ea\u52a8\u5316`,
        createTime: formatBeijingTime(item.timestamp),
        status: "\u5df2\u5b8c\u6210",
      }))

    const todaysPublish = uploadTasks.filter(
      (task) => getBeijingDayKey(task.timestamp) === todayKey
    ).length

    const timeline = parsed
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, 12)
      .map((item) => ({
        id: item.id,
        time: formatBeijingClock(item.timestamp),
        title: `${item.platform} \u00b7 ${item.level === "ERROR" ? "\u5f02\u5e38" : "\u4e8b\u4ef6"}`,
        detail: item.message,
      }))

    const alerts = parsed
      .filter((item) => item.level === "ERROR" || /\u5931\u6548|\u5931\u8d25|\u5f02\u5e38/.test(item.message))
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, 5)
      .map((item) => ({
        id: item.id,
        title: `${item.platform} \u00b7 ${item.message}`,
        action: item.message.includes("cookie")
          ? "\u524d\u5f80\u8d26\u53f7\u7ba1\u7406\u91cd\u65b0\u626b\u7801"
          : "\u67e5\u770b\u65e5\u5fd7\u8be6\u60c5",
        level: item.level === "ERROR" ? "error" : "warning",
      }))

    return NextResponse.json({
      tasks,
      timeline,
      alerts,
      summary: {
        todaysPublish,
        pendingAlerts: alerts.length,
      },
      timestamp: Date.now(),
    })
  } catch (error) {
    console.error("Failed to parse system feed:", error)
    return NextResponse.json(
      {
        tasks: [],
        timeline: [],
        alerts: [],
        summary: { todaysPublish: 0, pendingAlerts: 0 },
        timestamp: Date.now(),
      },
      { status: 500 }
    )
  }
}
