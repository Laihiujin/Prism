import { NextResponse } from "next/server"

interface GenerateBody {
  baseUrl: string
  apiKey: string
  model?: string
  task: "title" | "tags"
  description?: string
  filenames?: string[]
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as GenerateBody
    const baseUrl = (body.baseUrl || "").replace(/\/$/, "")
    const apiKey = body.apiKey || ""
    const model = body.model || "gpt-4o-mini"
    const task = body.task
    const description = body.description || ""
    const filenames = Array.isArray(body.filenames) ? body.filenames : []
    if (!baseUrl || !apiKey || !task) {
      return NextResponse.json({ error: "missing baseUrl/apiKey/task" }, { status: 400 })
    }

    const sys =
      task === "title"
        ? "你是短视频标题优化助手。根据素材名称，生成一个符合调性的富有创意的中文标题，长度不超过 27 字。"
        : "你是短视频标签生成助手。根据素材名称，返回 3-4 个中文标签，符合视频调性，去重，以逗号分隔。"
    const user = `${description}\n素材：${filenames.join("，")}`

    const response = await fetch(`${baseUrl}/v1/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: sys },
          { role: "user", content: user },
        ],
        temperature: 0.7,
      }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      return NextResponse.json({ error: payload?.error ?? "generate failed" }, { status: response.status })
    }
    const text: string = payload?.choices?.[0]?.message?.content || payload?.output_text || ""
    const result =
      task === "title"
        ? text.trim()
        : text
            .split(/[\s,，、#]+/)
            .map((t: string) => t.trim())
            .filter((t: string) => t.length > 0)
            .slice(0, 10)
    return NextResponse.json({ data: result })
  } catch (error) {
    return NextResponse.json({ error: "ai generate error" }, { status: 502 })
  }
}

