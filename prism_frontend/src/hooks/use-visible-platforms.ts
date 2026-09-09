"use client"

import { useCallback, useEffect, useState } from "react"

export interface ChannelMeta {
    code: number
    name: string
    alias: string
    hidden: boolean
}

export type PlatformAlias =
    | "xiaohongshu"
    | "channels"
    | "douyin"
    | "kuaishou"
    | "bilibili"
    | "tiktok"
    | "youtube"
    | "twitter"
    | "x"
    | "xitter"

/** 平台 code/别名 → 前端 PlatformKey 兼容 key（channels 别名=tencent，保持与注册表一致） */
export function channelToPlatformKey(alias: string): string {
    const map: Record<string, string> = {
        xiaohongshu: "xiaohongshu",
        channels: "channels",
        tencent: "channels",
        wechat: "channels",
        douyin: "douyin",
        kuaishou: "kuaishou",
        ks: "kuaishou",
        bilibili: "bilibili",
        tiktok: "tiktok",
        youtube: "youtube",
        baijiahao: "baijiahao",
        twitter: "twitter",
        x: "twitter",
        xitter: "twitter",
    }
    return map[alias] || alias
}

/**
 * 读取 CMS「隐藏平台渠道」开关（/api/v1/system/channels）。
 * 返回可见平台的 code 集合与 alias 集合；未配置时为 null（表示全部可见）。
 */
export function useVisiblePlatforms() {
    const [hiddenCodes, setHiddenCodes] = useState<Set<number> | null>(null)
    const [loaded, setLoaded] = useState(false)

    useEffect(() => {
        let alive = true
        fetch("/api/v1/system/channels", { cache: "no-store" })
            .then((res) => (res.ok ? res.json() : Promise.resolve({})))
            .then((payload: { platforms?: ChannelMeta[] }) => {
                if (!alive) return
                if (Array.isArray(payload?.platforms)) {
                    setHiddenCodes(
                        new Set(
                            payload.platforms
                                .filter((p) => p.hidden)
                                .map((p) => p.code)
                        )
                    )
                } else {
                    setHiddenCodes(new Set())
                }
            })
            .catch(() => {
                if (alive) setHiddenCodes(new Set())
            })
            .finally(() => {
                if (alive) setLoaded(true)
            })
        return () => {
            alive = false
        }
    }, [])

    /** 平台 key（douyin/kuaishou/channels/xiaohongshu/bilibili/tiktok/youtube）或 code 是否可见 */
    const isVisible = useCallback(
        (keyOrCode: string | number): boolean => {
            if (hiddenCodes === null) return true
            const code =
                typeof keyOrCode === "number"
                    ? keyOrCode
                    : {
                          xiaohongshu: 1,
                          channels: 2,
                          tencent: 2,
                          douyin: 3,
                          kuaishou: 4,
                          bilibili: 5,
                          tiktok: 6,
                          youtube: 7,
                          baijiahao: 8,
                          twitter: 9,
                          x: 9,
                      }[keyOrCode]
            if (code === undefined) return true
            return !hiddenCodes.has(code)
        },
        [hiddenCodes]
    )

    return { loaded, hiddenCodes, isVisible }
}
