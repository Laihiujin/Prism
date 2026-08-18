import { NextRequest, NextResponse } from "next/server"

export const runtime = "edge"
export const maxDuration = 30

export async function POST(req: NextRequest) {
    try {
        const { messages } = await req.json()
        if (!Array.isArray(messages) || messages.length === 0) {
            return NextResponse.json({ error: "messages is required" }, { status: 400 })
        }

        // 获取最后一条用户消息
        const lastMessage = messages[messages.length - 1]

        // 调用后端 FastAPI AI 服务
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:7000"
        const response = await fetch(`${backendUrl}/api/v1/ai/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message: lastMessage.content,
                context: messages.slice(0, -1),
                role: "default",
                stream: false
            }),
        })

        if (!response.ok) {
            throw new Error(`Backend API error: ${response.statusText}`)
        }

        const data = await response.json()

        // 返回流式响应格式
        const encoder = new TextEncoder()
        const stream = new ReadableStream({
            start(controller) {
                // 发送 AI 响应
                const text = data.content || data.response || "抱歉，我无法回答这个问题。"
                controller.enqueue(encoder.encode(`0:${JSON.stringify(text)}\n`))
                controller.close()
            },
        })

        return new Response(stream, {
            headers: {
                "Content-Type": "text/plain; charset=utf-8",
                "X-Vercel-AI-Data-Stream": "v1",
            },
        })
    } catch (error: any) {
        console.error("AI Chat Error:", error)
        return NextResponse.json(
            { error: error.message || "AI 服务暂时不可用" },
            { status: 500 }
        )
    }
}
