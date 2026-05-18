FROM node:22-bookworm-slim AS deps

WORKDIR /app/syn_frontend_react

COPY syn_frontend_react/package.json syn_frontend_react/package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder

WORKDIR /app/syn_frontend_react

COPY --from=deps /app/syn_frontend_react/node_modules ./node_modules
COPY syn_frontend_react/ ./

ARG NEXT_PUBLIC_BACKEND_URL=http://localhost:7000
ARG SYNAPSE_INTERNAL_BACKEND_URL=http://app:7000

ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL} \
    SYNAPSE_INTERNAL_BACKEND_URL=${SYNAPSE_INTERNAL_BACKEND_URL} \
    NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-bookworm-slim AS runner

WORKDIR /app

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_BACKEND_URL=http://localhost:7000 \
    SYNAPSE_INTERNAL_BACKEND_URL=http://app:7000

COPY --from=builder /app/syn_frontend_react/public ./public
COPY --from=builder /app/syn_frontend_react/.next/standalone ./
COPY --from=builder /app/syn_frontend_react/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
