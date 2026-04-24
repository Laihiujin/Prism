import type { NextConfig } from "next"

function normalizeBackendUrl(raw: string): string {
  const fallback = "http://127.0.0.1:7000"
  const trimmed = (raw || "").trim().replace(/\/+$/, "")
  const candidate = trimmed || fallback

  try {
    const url = new URL(candidate)
    if (url.hostname === "localhost") {
      url.hostname = "127.0.0.1"
    }
    return url.toString().replace(/\/+$/, "")
  } catch {
    return fallback
  }
}

const resolvedBackendUrl = normalizeBackendUrl(
  process.env.SYN_BACKEND_URL ||
    process.env.NEXT_PUBLIC_SYN_BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "http://127.0.0.1:7000"
)

const backendUrl = new URL(resolvedBackendUrl)
const backendPattern: { protocol: "http" | "https"; hostname: string; port?: string; pathname?: string } = {
  protocol: backendUrl.protocol.replace(":", "") as "http" | "https",
  hostname: backendUrl.hostname,
  ...(backendUrl.port ? { port: backendUrl.port } : {}),
}

const localhostPatterns: Array<{ protocol: "http" | "https"; hostname: string; port?: string }> = [
  { protocol: "http", hostname: "localhost" },
  { protocol: "http", hostname: "127.0.0.1" },
  { protocol: "https", hostname: "localhost" },
  { protocol: "https", hostname: "127.0.0.1" },
]

const nextConfig: NextConfig = {
  output: "standalone",
  typescript: {
    // Skip type-checking during desktop packaging builds.
    ignoreBuildErrors: true,
  },
  turbopack: {
    root: __dirname,
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "api.dicebear.com",
      },
      {
        protocol: "https",
        hostname: "api.qrserver.com",
      },
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "wx.qlogo.cn",
      },
      {
        protocol: "https",
        hostname: "p3-pc.douyinpic.com",
      },
      {
        protocol: "https",
        hostname: "p9-pc.douyinpic.com",
      },
      {
        protocol: "https",
        hostname: "p11.douyinpic.com",
      },
      {
        protocol: "https",
        hostname: "**.yximgs.com",
      },
      {
        protocol: "https",
        hostname: "**.xhscdn.com",
      },
      {
        protocol: "https",
        hostname: "i0.hdslb.com",
      },
      {
        protocol: "https",
        hostname: "i1.hdslb.com",
      },
      {
        protocol: "https",
        hostname: "i2.hdslb.com",
      },
      ...localhostPatterns,
      backendPattern,
    ],
  },

  async rewrites() {
    const docsRewrites = [
      {
        source: "/docs",
        destination: `${resolvedBackendUrl}/apidocs/`,
      },
      {
        source: "/apidocs/:path*",
        destination: `${resolvedBackendUrl}/apidocs/:path*`,
      },
      {
        source: "/flasgger_static/:path*",
        destination: `${resolvedBackendUrl}/flasgger_static/:path*`,
      },
    ]

    const backendRewrites = [
      {
        source: "/api/chat",
        destination: `${resolvedBackendUrl}/api/v1/ai/chat`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${resolvedBackendUrl}/api/v1/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${resolvedBackendUrl}/api/v1/:path*`,
      },
      {
        source: "/getFiles",
        destination: `${resolvedBackendUrl}/getFiles`,
      },
      {
        source: "/getValidAccounts",
        destination: `${resolvedBackendUrl}/getValidAccounts`,
      },
      {
        source: "/uploadSave",
        destination: `${resolvedBackendUrl}/uploadSave`,
      },
      {
        source: "/deleteFile",
        destination: `${resolvedBackendUrl}/deleteFile`,
      },
      {
        source: "/updateFileMeta",
        destination: `${resolvedBackendUrl}/updateFileMeta`,
      },
      {
        source: "/health",
        destination: `${resolvedBackendUrl}/health`,
      },
    ]

    return {
      beforeFiles: docsRewrites,
      afterFiles: [],
      fallback: backendRewrites,
    }
  },
}

export default nextConfig
