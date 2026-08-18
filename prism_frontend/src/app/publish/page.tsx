"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function PublishPage() {
  const router = useRouter()

  useEffect(() => {
    // 默认跳转到矩阵发布（单一发布暂时关闭）
    router.replace("/publish/matrix")
  }, [router])

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-white/60">正在跳转...</div>
    </div>
  )
}
