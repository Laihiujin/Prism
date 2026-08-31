FROM node:22-bookworm-slim AS deps

WORKDIR /app/prism_frontend

COPY prism_frontend/package.json prism_frontend/package-lock.json ./
# --force: lockfile 由 macOS 生成含 darwin 专属可选依赖（fsevents），Linux 构建跳过平台校验
RUN npm ci --ignore-scripts --force

FROM node:22-bookworm-slim AS builder

WORKDIR /app/prism_frontend

COPY --from=deps /app/prism_frontend/node_modules ./node_modules
COPY prism_frontend/ ./

ARG NEXT_PUBLIC_BACKEND_URL=http://localhost:7000
ARG PRISM_INTERNAL_BACKEND_URL=http://app:7000

ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL} \
    PRISM_INTERNAL_BACKEND_URL=${PRISM_INTERNAL_BACKEND_URL} \
    NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-bookworm-slim AS runner

WORKDIR /app

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_BACKEND_URL=http://localhost:7000 \
    PRISM_INTERNAL_BACKEND_URL=http://app:7000

COPY --from=builder /app/prism_frontend/public ./public
COPY --from=builder /app/prism_frontend/.next/standalone ./
COPY --from=builder /app/prism_frontend/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
