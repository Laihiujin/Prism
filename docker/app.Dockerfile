FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --break-system-packages --upgrade pip \
    && python -m pip install --break-system-packages -r requirements.txt \
    && python -m patchright install --with-deps chromium

# ── Persona Studio（Browser Identity / Fingerprint / Profile 层）──
# 构建期 clone 到镜像（不污染仓库）；persona serve 提供 HTTP API
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && git clone --depth 1 https://github.com/TechQaiser/persona-studio.git /opt/persona-studio \
    && cd /opt/persona-studio/engine \
    && python -m pip install --break-system-packages -e ".[api,launch]" \
    && python -m pip --version \
    && rm -rf /var/lib/apt/lists/*

COPY prism_backend ./prism_backend
COPY tools/hermes-agent ./tools/hermes-agent
COPY tools/hermes-webui ./tools/hermes-webui
COPY docker/start-app.sh ./docker/start-app.sh

# ── Hermes Agent + WebUI（开箱即用，部署后无需手动 reinstall）──
# [all] extra：CLI/终端/web/mcp/acp/google 等核心能力一次装齐；
# 其余后端（provider/search/tts/image）走 hermes 自带的 lazy-install，首次使用自动装。
# 独立 venv 建在 /app/prismenv（--system-site-packages 复用系统 patchright 等），
# 干净隔离不污染 Prism 系统环境。检查器经 PRISM_HERMES_PYTHON=/app/prismenv/bin/python
# 认该解释器 + .hermes-runtime-ready 标记 → agent_installed=True。
RUN python -m venv --system-site-packages /app/prismenv \
    && /app/prismenv/bin/pip install --no-build-isolation -e "/app/tools/hermes-agent[all]" \
    && /app/prismenv/bin/pip install -r /app/tools/hermes-webui/requirements.txt \
    && ln -sf /app/prismenv/bin/hermes /usr/local/bin/hermes \
    && ln -sf /app/prismenv/bin/hermes-agent /usr/local/bin/hermes-agent \
    && ln -sf /app/prismenv/bin/hermes-acp /usr/local/bin/hermes-acp \
    && touch /app/prismenv/.hermes-runtime-ready \
    && chmod +x ./docker/start-app.sh \
    && mkdir -p /app/runtime-data

EXPOSE 7000 7001 8787 9119 9131

ENTRYPOINT ["./docker/start-app.sh"]
