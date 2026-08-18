"use client"

import { useRouter, usePathname } from "next/navigation"
import { PublishModeSelector, PublishMode } from "./components/PublishModeSelector"
import React, { useEffect } from "react"

export default function PublishLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const router = useRouter()
    const pathname = usePathname()

    // 如果访问 /publish 根路径，自动跳转到矩阵发布
    useEffect(() => {
        if (pathname === "/publish" || pathname === "/publish/") {
            router.push("/publish/matrix")
        }
    }, [pathname, router])

    const activeMode: PublishMode = "matrix"

    const handleModeChange = (mode: PublishMode) => {
        router.push("/publish/matrix")
    }

    return (
        <div className="flex flex-col h-full bg-transparent text-white">
            <div className="px-6 pt-6 pb-4 border-b border-white/10 space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        {/* <h1 className="text-2xl font-bold tracking-tight">发布中心</h1> */}
                        {/* <p className="text-sm text-white/60 mt-1"> */}
                        {/* 多平台矩阵发布管理 */}
                        {/* </p> */}
                    </div>
                </div>

                <div className="2xl">
                    <PublishModeSelector
                        selected={activeMode}
                        onSelect={handleModeChange}
                    />
                </div>
            </div>

            <div className="flex-1 overflow-hidden">
                {children}
            </div>
        </div>
    )
}
