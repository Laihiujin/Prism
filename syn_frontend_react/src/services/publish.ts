import { apiPost } from "@/lib/api"

export interface PublishItem {
    file_id: number
    title?: string
    description?: string
    topics?: string[]
    cover_path?: string
}

export interface BatchPublishPayload {
    file_ids: number[]
    accounts: string[]
    platform?: number
    title: string
    description?: string
    topics?: string[]
    cover_path?: string
    scheduled_time?: string
    priority?: number
    items?: PublishItem[]
}

export interface BatchPublishResponse {
    batch_id: string
    total_tasks: number
    success_count: number
    failed_count: number
    pending_count: number
}

export async function batchPublish(payload: BatchPublishPayload): Promise<BatchPublishResponse> {
    return apiPost<BatchPublishResponse>("/api/v1/publish/batch", payload)
}
