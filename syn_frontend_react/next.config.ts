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

const publicBackendUrl = normalizeBackendUrl(
  process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:7000"
)

const internalBackendUrl = normalizeBackendUrl(
  process.env.SYNAPSE_INTERNAL_BACKEND_URL ||
    process.env.SYN_BACKEND_URL ||
    process.env.NEXT_PUBLIC_SYN_BACKEND_URL ||
    publicBackendUrl
)

function toRemotePattern(
  rawUrl: string
): { protocol: "http" | "https"; hostname: string; port?: string; pathname?: string } {
  const url = new URL(rawUrl)
  return {
    protocol: url.protocol.replace(":", "") as "http" | "https",
    hostname: url.hostname,
    ...(url.port ? { port: url.port } : {}),
  }
}

const backendPatterns = [publicBackendUrl, internalBackendUrl].map(toRemotePattern)

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
  webpack(config, { dev }) {
    if (
      !dev &&
      process.env.SYNAPSE_DISABLE_CSS_MINIFY === "1" &&
      Array.isArray(config.optimization?.minimizer)
    ) {
      config.optimization.minimize = false
      config.optimization.minimizer = config.optimization.minimizer.filter((minimizer: unknown) => {
        const name = (minimizer as { constructor?: { name?: string } })?.constructor?.name
        return name !== "CssMinimizerPlugin"
      })
    }
    return config
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
        hostname: "res.wx.qq.com",
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
      ...backendPatterns,
    ],
  },

  async rewrites() {
    const docsRewrites = [
      {
        source: "/docs",
        destination: `${internalBackendUrl}/apidocs/`,
      },
      {
        source: "/apidocs/:path*",
        destination: `${internalBackendUrl}/apidocs/:path*`,
      },
      {
        source: "/flasgger_static/:path*",
        destination: `${internalBackendUrl}/flasgger_static/:path*`,
      },
    ]

    const backendRewrites = [
      {
        source: "/api/chat",
        destination: `${internalBackendUrl}/api/v1/ai/chat`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${internalBackendUrl}/api/v1/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${internalBackendUrl}/api/v1/:path*`,
      },
      {
        source: "/getFiles",
        destination: `${internalBackendUrl}/getFiles`,
      },
      {
        source: "/getValidAccounts",
        destination: `${internalBackendUrl}/getValidAccounts`,
      },
      {
        source: "/uploadSave",
        destination: `${internalBackendUrl}/uploadSave`,
      },
      {
        source: "/deleteFile",
        destination: `${internalBackendUrl}/deleteFile`,
      },
      {
        source: "/updateFileMeta",
        destination: `${internalBackendUrl}/updateFileMeta`,
      },
      {
        source: "/health",
        destination: `${internalBackendUrl}/health`,
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
