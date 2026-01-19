import { z } from "zod"

// Material (视频文件) Schema
export const materialSchema = z.object({
  id: z.union([z.number(), z.string()]),
  filename: z.string(),
  filesize: z.number(),
  upload_time: z.string(),
  file_path: z.string(),
  status: z.string().default("ready"), // 放宽 status 验证，后端返回 "ready"
  published_at: z.string().nullable().optional(),
  last_platform: z.number().nullable().optional(),
  last_accounts: z.string().nullable().optional(),
  note: z.string().nullable().optional(),
  group_name: z.string().nullable().optional(),
  title: z.string().optional(),
  cover_image: z.string().nullable().optional(),
}).passthrough()

export const materialsResponseSchema = z.object({
  code: z.number(),
  msg: z.string().nullable(),
  data: z.array(materialSchema),
})

// 前端转换后的 Material Schema (用于 /api/materials)
export const frontendMaterialSchema = z.object({
  id: z.string(),
  filename: z.string(),
  filesize: z.coerce.number(),
  uploadTime: z.string(),
  type: z.string(), // "video" | "image" | "other"
  fileUrl: z.string(),
  status: z.string(),
  publishedAt: z.string().optional(),
  note: z.string().optional(),
  group: z.string().optional(),
}).passthrough()

export const frontendMaterialsResponseSchema = z.object({
  code: z.number(),
  msg: z.string().nullable(),
  data: z.object({
    data: z.array(frontendMaterialSchema),
    total: z.number().optional(),
    timestamp: z.number().optional(),
  })
})

export type Material = z.infer<typeof materialSchema>
export type MaterialsResponse = z.infer<typeof materialsResponseSchema>

// Account Schema
export const accountSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional().default(""),
  original_name: z.string().nullable().optional().default(""),
  note: z.string().nullable().optional(),
  user_id: z.coerce.string().nullable().optional(),
  platform: z.string().nullable().optional().default(""),
  status: z.string().nullable().optional().default("待激活"),
  avatar: z.string().nullable().optional().default(""),
  boundAt: z.string().nullable().optional().default(""),
  filePath: z.string().nullable().optional(),
  login_status: z.string().nullable().optional(),
}).passthrough()

export const accountsResponseSchema = z.object({
  code: z.number(),
  msg: z.string().nullable(),
  data: z.array(accountSchema),
})

export type Account = z.infer<typeof accountSchema>
export type AccountsResponse = z.infer<typeof accountsResponseSchema>

// Publish Request Schema
export const publishRequestSchema = z.object({
  type: z.number(), // platform code
  fileList: z.array(z.string()),
  accountList: z.array(z.string()),
  title: z.string().optional(),
  tags: z.array(z.string()).optional(),
  category: z.number().nullable().optional(),
  enableTimer: z.boolean().optional(),
  videosPerDay: z.number().optional(),
  dailyTimes: z.array(z.number()).optional(),
  startDays: z.number().optional(),
  productLink: z.string().optional(),
  productTitle: z.string().optional(),
  thumbnail: z.string().optional(),
})

export type PublishRequest = z.infer<typeof publishRequestSchema>

// AI Chat Schema
export const aiMessageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
  timestamp: z.number().optional(),
})

export const aiChatRequestSchema = z.object({
  message: z.string(),
  provider: z.string().optional(),
  model: z.string().optional(),
  history: z.array(aiMessageSchema).optional(),
})

export type AIMessage = z.infer<typeof aiMessageSchema>
export type AIChatRequest = z.infer<typeof aiChatRequestSchema>

// Publish Meta Schema
export const publishMetaResponseSchema = z.object({
  code: z.number(),
  msg: z.string().nullable(),
  data: z.object({
    platforms: z.array(z.object({
      code: z.number(),
      name: z.string(),
      enabled: z.boolean(),
    })),
    categories: z.array(z.object({
      id: z.number(),
      name: z.string(),
    })),
    presets: z
      .array(
        z.object({
          id: z.union([z.string(), z.number()]).optional(),
          label: z.string(),
          platform: z.string(),
          accounts: z.array(z.string()).default([]),
          fileList: z
            .array(
              z.object({
                name: z.string(),
              })
            )
            .optional(),
          title: z.string().optional(),
          description: z.string().optional(),
          topics: z.array(z.string()).optional(),
          scheduleEnabled: z.boolean().optional(),
          videosPerDay: z.number().optional(),
          timePoint: z.string().optional(),
        })
      )
      .optional(),
    recommendedTopics: z.array(z.string()).optional(),
    quickActions: z
      .array(
        z.object({
          id: z.string(),
          title: z.string(),
          description: z.string(),
          icon: z.string().optional(),
          href: z.string().optional(),
          accent: z.string().optional(),
        })
      )
      .optional(),
    timestamp: z.number().optional(),
  }),
})

export type PublishMetaResponse = z.infer<typeof publishMetaResponseSchema>

// System Feed Schema
export const systemFeedSchema = z.object({
  id: z.string(),
  type: z.enum(["info", "warning", "error", "success"]),
  title: z.string(),
  message: z.string(),
  timestamp: z.number(),
  read: z.boolean().default(false),
})

export type SystemFeed = z.infer<typeof systemFeedSchema>

// Tasks Response Schema
export const tasksResponseSchema = z.object({
  code: z.number(),
  msg: z.string().nullable(),
  data: z.array(z.object({
    id: z.string(),
    title: z.string(),
    platform: z.string(),
    account: z.string(),
    material: z.string(),
    status: z.enum(["pending", "success", "error", "scheduled", "running", "cancelled"]),
    createdAt: z.string(),
    scheduledAt: z.string().optional(),
    result: z.string().optional(),
    source: z.enum(["queue", "history"]).optional(),
  })),
  total: z.number().optional(),
  summary: z.object({
    scheduled: z.number(),
    success: z.number(),
    error: z.number(),
    pending: z.number(),
    total: z.number(),
  }).optional(),
  updatedAt: z.number().optional(),
})

export type TasksResponse = z.infer<typeof tasksResponseSchema>

// Dashboard summary schema
export const dashboardSchema = z.object({
  code: z.number(),
  msg: z.string().nullable(),
  data: z.object({
    accounts: z.object({
      total: z.coerce.number(),
      byStatus: z.record(z.string(), z.coerce.number()).optional(),
      byPlatform: z.record(z.string(), z.coerce.number()).optional(),
    }),
    materials: z.object({
      total: z.coerce.number(),
      byStatus: z.record(z.string(), z.coerce.number()).optional(),
      lastUpload: z.string().nullable().optional(),
    }),
    publish: z.object({
      todaysPublish: z.number(),
      pendingAlerts: z.number(),
    }),
    tasks: z.array(z.object({
      id: z.string(),
      title: z.string(),
      platform: z.string(),
      account: z.string(),
      material: z.string(),
      status: z.string(),
      createdAt: z.string(),
      scheduledAt: z.string().optional(),
      result: z.string().optional(),
    })),
    timestamp: z.number(),
  }),
})

export type DashboardResponse = z.infer<typeof dashboardSchema>
