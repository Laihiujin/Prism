export function parseMaterialAIResult(content: string): { title: string; tags: string[]; coverPrompt: string } {
    const text = content.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "")
    const start = text.indexOf("{")
    const end = text.lastIndexOf("}")
    if (start < 0 || end < start) throw new Error("模型未返回结构化内容，请重新生成")
    let raw = JSON.parse(text.slice(start, end + 1))
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("模型返回格式无效")
    for (const key of ["data", "result", "output"]) {
        if (raw[key] && typeof raw[key] === "object" && !Array.isArray(raw[key])) { raw = raw[key]; break }
    }
    const title = raw.title ?? raw.标题 ?? raw.titles?.[0] ?? raw.标题列表?.[0]
    const tags = raw.tags ?? raw.标签 ?? raw.hashtags ?? raw.topics
    const cover = raw.coverPrompt ?? raw.cover_prompt ?? raw.封面提示词 ?? raw.prompt
    return {
        title: typeof title === "string" ? title.trim() : "",
        tags: (Array.isArray(tags) ? tags : typeof tags === "string" ? tags.split(/[\s,，]+/) : []).filter((tag): tag is string => typeof tag === "string").map(tag => tag.trim().replace(/^#/, "")).filter(Boolean),
        coverPrompt: typeof cover === "string" ? cover.trim() : "",
    }
}
