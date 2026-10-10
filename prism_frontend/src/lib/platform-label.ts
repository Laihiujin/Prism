const names: Record<string, string> = {
  "1": "小红书", "2": "视频号", "3": "抖音", "4": "快手", "5": "B站", "6": "TikTok", "7": "YouTube", "8": "百家号", "9": "X / Twitter",
  xiaohongshu: "小红书", xhs: "小红书", redbook: "小红书",
  channels: "视频号", wechat: "视频号", weixin: "视频号", shipinhao: "视频号", tencent: "视频号",
  douyin: "抖音", kuaishou: "快手", bilibili: "B站", bili: "B站",
  tiktok: "TikTok", youtube: "YouTube", baijiahao: "百家号", twitter: "X / Twitter", x: "X / Twitter", instagram: "Instagram",
}

export function platformLabel(value: unknown): string {
  const raw = String(value ?? "").trim()
  const key = raw.toLowerCase().replace(/^platform_/, "")
  return names[key] || (/^\d+$/.test(key) ? `未知平台（${key}）` : raw || "未知平台")
}
