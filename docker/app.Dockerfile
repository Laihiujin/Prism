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

RUN python -m venv --system-site-packages /opt/hermes-venv \
    && /opt/hermes-venv/bin/pip install --no-build-isolation --no-deps -e ./tools/hermes-agent[web] \
    && /opt/hermes-venv/bin/pip install -r ./tools/hermes-webui/requirements.txt \
    && touch /opt/hermes-venv/.hermes-runtime-ready \
    && chmod +x ./docker/start-app.sh \
    && mkdir -p /app/runtime-data

EXPOSE 7000 7001 8787 9119 9131

ENTRYPOINT ["./docker/start-app.sh"]
