FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY syn_backend ./syn_backend
COPY docker/start-app.sh ./docker/start-app.sh

RUN chmod +x ./docker/start-app.sh \
    && mkdir -p /app/runtime-data

EXPOSE 7000 7001

ENTRYPOINT ["./docker/start-app.sh"]
