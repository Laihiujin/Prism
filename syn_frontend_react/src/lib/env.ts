function normalizeBackendBaseUrl(raw: string): string {
  const trimmed = (raw || "").trim().replace(/\/+$/, "")
  const normalized = (trimmed || "http://127.0.0.1:7000").replace(/\/api\/v1$/i, "")

  try {
    const url = new URL(normalized)
    if (url.hostname === "localhost") {
      url.hostname = "127.0.0.1"
    }
    return url.toString().replace(/\/+$/, "")
  } catch {
    return normalized
  }
}

export const backendBaseUrl = normalizeBackendBaseUrl(
  process.env.NEXT_PUBLIC_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:7000"
)

export const API_ENDPOINTS = {
  base: backendBaseUrl,

  getFiles: `${backendBaseUrl}/api/v1/files`,
  uploadFile: `${backendBaseUrl}/api/v1/files/upload`,
  uploadSave: `${backendBaseUrl}/api/v1/files/upload-save`,
  deleteFile: (fileId: number) => `${backendBaseUrl}/api/v1/files/${fileId}`,
  updateFileMeta: (fileId: number) => `${backendBaseUrl}/api/v1/files/${fileId}`,
  getFile: (fileId: number) => `${backendBaseUrl}/api/v1/files/${fileId}`,
  fileStats: `${backendBaseUrl}/api/v1/files/stats/summary`,

  getValidAccounts: `${backendBaseUrl}/api/v1/accounts`,
  deleteAccount: (accountId: string) => `${backendBaseUrl}/api/v1/accounts/${accountId}`,
  updateUserinfo: (accountId: string) => `${backendBaseUrl}/api/v1/accounts/${accountId}`,
  verifyAccount: (accountId: string) => `${backendBaseUrl}/api/v1/accounts/${accountId}/verify`,
  batchVerify: `${backendBaseUrl}/api/v1/accounts/batch-verify`,
  deepSync: `${backendBaseUrl}/api/v1/accounts/deep-sync`,
  accountStats: `${backendBaseUrl}/api/v1/accounts/stats/summary`,

  postVideo: `${backendBaseUrl}/api/v1/publish`,
  postVideoBatch: `${backendBaseUrl}/api/v1/publish/batch`,

  aiChat: `${backendBaseUrl}/api/v1/ai/chat`,
  aiProviders: `${backendBaseUrl}/api/v1/ai/providers`,
  aiModels: `${backendBaseUrl}/api/v1/ai/models`,
  aiHealth: `${backendBaseUrl}/api/v1/ai/health`,
  aiModelConfigs: `${backendBaseUrl}/api/v1/ai/model-configs`,
  aiTestConnection: `${backendBaseUrl}/api/v1/ai/test-connection`,

  agentContext: `${backendBaseUrl}/api/v1/agent/context`,
  agentSaveScript: `${backendBaseUrl}/api/v1/agent/save-script`,
  agentExecuteScript: `${backendBaseUrl}/api/v1/agent/execute-script`,
  agentScripts: `${backendBaseUrl}/api/v1/agent/scripts`,
  agentExecutions: `${backendBaseUrl}/api/v1/agent/executions`,
  agentOpenClawRun: `${backendBaseUrl}/api/v1/agent/openclaw-run`,
  agentHermesRun: `${backendBaseUrl}/api/v1/agent/hermes-run`,

  AI_PROMPTS: `${backendBaseUrl}/api/v1/ai-prompts`,

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
  [PLATFORM_CODES.DOUYIN]: "抖音",
  [PLATFORM_CODES.KUAISHOU]: "快手",
  [PLATFORM_CODES.BILIBILI]: "B 站",
} as const
