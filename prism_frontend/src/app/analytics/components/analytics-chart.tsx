"use client"

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'

interface AnalyticsChartProps {
    data: Array<any>
    dataKey?: string
    color?: string
    title?: string
}

export function AnalyticsChart({ data, dataKey = "playCount", color = "#3b82f6", title = "数据" }: AnalyticsChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="h-[350px] flex items-center justify-center text-white/50 border border-dashed border-white/10 rounded-xl bg-gradient-to-br from-white/[0.02] to-transparent">
                <div className="text-center space-y-3">
                    <div className="w-16 h-16 mx-auto rounded-full bg-white/5 flex items-center justify-center">
                        <svg className="w-8 h-8 text-white/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-base font-medium text-white/60">暂无趋势数据</p>
                        <p className="text-sm text-white/30 mt-1">请尝试调整筛选条件或采集数据</p>
                    </div>
                </div>
            </div>
        )
    }

    const formatValue = (value: number) => {
        if (value >= 10000) {
            return (value / 10000).toFixed(1) + 'w'
        }
        if (value >= 1000) {
            return (value / 1000).toFixed(1) + 'k'
        }
        return value.toLocaleString()
    }

    const maxValue = Math.max(...data.map(d => d[dataKey] || 0))
    const minValue = Math.min(...data.map(d => d[dataKey] || 0))

    return (
        <ResponsiveContainer width="100%" height={350}>
            <AreaChart
                data={data}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
            >
                <defs>
                    <linearGradient id={`gradient-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={color} stopOpacity={0.01} />
                    </linearGradient>
                </defs>

                <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.06)"
                    vertical={false}
                />

                <XAxis
                    dataKey="date"
                    stroke="rgba(255,255,255,0.4)"
                    fontSize={12}
                    tickLine={false}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    dy={8}
                    tickFormatter={(value) => {
                        const date = new Date(value)
                        return `${date.getMonth() + 1}/${date.getDate()}`
                    }}
                />

                <YAxis
                    stroke="rgba(255,255,255,0.4)"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={formatValue}
                    dx={-10}
                    domain={[0, 'auto']}
                />

                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(10, 10, 10, 0.95)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '12px',
                        color: '#fff',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                        backdropFilter: 'blur(12px)',
                        padding: '12px'
                    }}
                    itemStyle={{
                        color: color,
                        fontSize: '13px',
                        fontWeight: '600'
                    }}
                    labelStyle={{
                        color: 'rgba(255, 255, 255, 0.7)',
                        marginBottom: '6px',
                        fontSize: '12px'
                    }}
                    formatter={(value: number) => [
                        formatValue(value),
                        title
                    ]}
                    labelFormatter={(label) => {
                        const date = new Date(label)
                        return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
                    }}
                />

                <Area
                    type="monotone"
                    dataKey={dataKey}
                    stroke={color}
                    strokeWidth={2.5}
                    fill={`url(#gradient-${dataKey})`}
                    dot={false}
                    activeDot={{
                        r: 5,
                        strokeWidth: 2,
                        stroke: color,
                        fill: '#fff',
                        style: { filter: `drop-shadow(0 0 4px ${color})` }
                    }}
                    animationDuration={1000}
                    animationEasing="ease-out"
                />
            </AreaChart>
        </ResponsiveContainer>
    )
}
