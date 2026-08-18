// 后端连接状态检测Hook
import { useEffect, useState } from 'react'

interface BackendStatus {
    connected: boolean
    checking: boolean
    lastCheck: number
    environment: 'development' | 'production'
}

export function useBackendStatus() {
    const [status, setStatus] = useState<BackendStatus>({
        connected: false,
        checking: true,
        lastCheck: 0,
        environment: process.env.NODE_ENV === 'production' ? 'production' : 'development'
    })

    useEffect(() => {
        let mounted = true
        let checkInterval: NodeJS.Timeout

        const checkBackend = async () => {
            if (!mounted) return

            setStatus(prev => ({ ...prev, checking: true }))

            try {
                const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:7000'
                const response = await fetch(`${baseUrl}/health`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    signal: AbortSignal.timeout(5000) // 5秒超时
                })

                if (!mounted) return

                const isConnected = response.ok
                setStatus({
                    connected: isConnected,
                    checking: false,
                    lastCheck: Date.now(),
                    environment: process.env.NODE_ENV === 'production' ? 'production' : 'development'
                })
            } catch (error) {
                if (!mounted) return

                setStatus({
                    connected: false,
                    checking: false,
                    lastCheck: Date.now(),
                    environment: process.env.NODE_ENV === 'production' ? 'production' : 'development'
                })
            }
        }

        // 立即检查
        checkBackend()

        // 每30秒检查一次
        checkInterval = setInterval(checkBackend, 30000)

        return () => {
            mounted = false
            if (checkInterval) clearInterval(checkInterval)
        }
    }, [])

    return status
}
