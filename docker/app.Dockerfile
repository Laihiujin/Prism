FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY syn_backend ./syn_backend
COPY tools/hermes-agent ./tools/hermes-agent
COPY tools/hermes-webui ./tools/hermes-webui
COPY docker/start-app.sh ./docker/start-app.sh

RUN python -m venv /opt/hermes-venv \
    && /opt/hermes-venv/bin/pip install -e ./tools/hermes-agent[web] \
    && /opt/hermes-venv/bin/pip install -r ./tools/hermes-webui/requirements.txt \
    && touch /opt/hermes-venv/.hermes-runtime-ready \
    && chmod +x ./docker/start-app.sh \
    && mkdir -p /app/runtime-data

EXPOSE 7000 7001 9119 9131

ENTRYPOINT ["./docker/start-app.sh"]
