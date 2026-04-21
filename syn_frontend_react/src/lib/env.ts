function normalizeBackendBaseUrl(raw: string): string {
  const trimmed = (raw || "").trim().replace(/\/+$/, "")
  if (!trimmed) return "http://localhost:7000"
  // Some envs mistakenly include /api/v1; strip it to avoid /api/v1/v1 duplication.
  return trimmed.replace(/\/api\/v1$/i, "")
}

// 鍚庣API鍩虹URL锛屾寜浼樺厛绾у洖閫€
export const backendBaseUrl = normalizeBackendBaseUrl(
  process.env.NEXT_PUBLIC_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:7000"
)

// API endpoints (FastAPI RESTful style)
export const API_ENDPOINTS = {
  // Base URL
  base: backendBaseUrl,

  // 鏂囦欢绠＄悊
  getFiles: `${backendBaseUrl}/api/v1/files`,
  uploadFile: `${backendBaseUrl}/api/v1/files/upload`,
  uploadSave: `${backendBaseUrl}/api/v1/files/upload-save`,
  deleteFile: (fileId: number) => `${backendBaseUrl}/api/v1/files/${fileId}`,
  updateFileMeta: (fileId: number) => `${backendBaseUrl}/api/v1/files/${fileId}`,
  getFile: (fileId: number) => `${backendBaseUrl}/api/v1/files/${fileId}`,
  fileStats: `${backendBaseUrl}/api/v1/files/stats/summary`,

  // 璐﹀彿绠＄悊
  getValidAccounts: `${backendBaseUrl}/api/v1/accounts`,
  deleteAccount: (accountId: string) => `${backendBaseUrl}/api/v1/accounts/${accountId}`,
  updateUserinfo: (accountId: string) => `${backendBaseUrl}/api/v1/accounts/${accountId}`,
  verifyAccount: (accountId: string) => `${backendBaseUrl}/api/v1/accounts/${accountId}/verify`,
  batchVerify: `${backendBaseUrl}/api/v1/accounts/batch-verify`,
  deepSync: `${backendBaseUrl}/api/v1/accounts/deep-sync`,
  accountStats: `${backendBaseUrl}/api/v1/accounts/stats/summary`,

  // 瑙嗛鍙戝竷
  postVideo: `${backendBaseUrl}/api/v1/publish`,
  postVideoBatch: `${backendBaseUrl}/api/v1/publish/batch`,

  // AI鏈嶅姟
  aiChat: `${backendBaseUrl}/api/v1/ai/chat`,
  aiProviders: `${backendBaseUrl}/api/v1/ai/providers`,
  aiModels: `${backendBaseUrl}/api/v1/ai/models`,
  aiHealth: `${backendBaseUrl}/api/v1/ai/health`,
  aiModelConfigs: `${backendBaseUrl}/api/v1/ai/model-configs`,
  aiTestConnection: `${backendBaseUrl}/api/v1/ai/test-connection`,

  // AI Agent
  agentContext: `${backendBaseUrl}/api/v1/agent/context`,
  agentSaveScript: `${backendBaseUrl}/api/v1/agent/save-script`,
  agentExecuteScript: `${backendBaseUrl}/api/v1/agent/execute-script`,
  agentScripts: `${backendBaseUrl}/api/v1/agent/scripts`,
  agentExecutions: `${backendBaseUrl}/api/v1/agent/executions`,
  agentOpenClawRun: `${backendBaseUrl}/api/v1/agent/openclaw-run`,
  
  // AI prompts
  AI_PROMPTS: `${backendBaseUrl}/api/v1/ai-prompts`,

  // 绯荤粺
  health: `${backendBaseUrl}/health`,
  ping: `${backendBaseUrl}/api/v1/ping`,
}

export const PLATFORM_CODES = {
  XIAOHONGSHU: 1,
  TENCENT: 2,
  DOUYIN: 3,
  KUAISHOU: 4,
  BILIBILI: 5,
} as const

export const PLATFORM_NAMES = {
  [PLATFORM_CODES.XIAOHONGSHU]: "小红书",
  [PLATFORM_CODES.TENCENT]: "视频号",
  [PLATFORM_CODES.DOUYIN]: "鎶栭煶",
  [PLATFORM_CODES.KUAISHOU]: "蹇墜",
  [PLATFORM_CODES.BILIBILI]: "B站",
} as const

