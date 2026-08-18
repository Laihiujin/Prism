export interface VideoAnalytics {
    id: number
    videoId: string
    title: string
    platform: string
    thumbnail: string
    videoUrl?: string
    publishDate: string
    playCount: number
    likeCount: number
    commentCount: number
    collectCount: number
    lastUpdated: string
}

export interface AnalyticsSummary {
    totalVideos: number
    totalPlays: number
    totalLikes: number
    totalComments: number
    totalCollects: number
    avgPlayCount: number
}
