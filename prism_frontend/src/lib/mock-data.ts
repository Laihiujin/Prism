import { z } from "zod"

// Platform types
export type PlatformKey = "all" | "kuaishou" | "douyin" | "channels" | "xiaohongshu" | "bilibili"

// Material interface
export interface Material {
  id: string
  filename: string
  storageKey?: string
  filesize: number
  uploadTime: string
  type: "video" | "image" | "other"
  fileUrl: string
  status: "pending" | "published" | "failed"
  publishedAt?: string
  note?: string
  group?: string
  title?: string
  description?: string
  tags?: string
  cover_image?: string
  // 兼容旧字段，可选
  size?: number
  duration?: number
  uploadedAt?: string
  video_width?: number
  video_height?: number
  aspect_ratio?: string
  orientation?: "portrait" | "landscape" | "square" | string
}

// Account interface  
export interface Account {
  id: string
  name: string
  platform: PlatformKey
  avatar?: string
  status: "正常" | "异常" | "待激活"
  boundAt: string
  filePath?: string
  original_name?: string
  note?: string
  user_id?: string
}

// Mock data
export const mockMaterials: Material[] = []
export const mockAccounts: Account[] = []

// Quick Actions
export const quickActions = [
  {
    id: "publish-matrix",
    title: "矩阵发布",
    description: "批量发布到多平台账号",
    icon: "Send",
    href: "/publish/matrix",
  },
  {
    id: "upload-material",
    title: "上传素材",
    description: "整理并入库最新素材",
    icon: "Upload",
    href: "/materials",
  },
  {
    id: "task-center",
    title: "任务管理",
    description: "查看排队与失败任务",
    icon: "ClipboardList",
    href: "/tasks",
  },
  {
    id: "account-health",
    title: "账号管理",
    description: "账号健康检查与授权",
    icon: "Users",
    href: "/account",
  },
  {
    id: "analytics",
    title: "数据中心",
    description: "查看平台与作品数据",
    icon: "BarChart3",
    href: "/analytics",
  },
]

// Recommended Topics
export const recommendedTopics = [
  "生活vlog",
  "美食探店",
  "旅行日记",
  "科技数码",
  "时尚穿搭",
  "健身运动",
  "学习分享",
  "宠物日常",
]
