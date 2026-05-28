FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System-Deps + mp3rgain v2.7.3 via .deb (kein tar nötig, robuster)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://github.com/M-Igashi/mp3rgain/releases/download/v2.7.3/mp3rgain_2.7.3-1_amd64.deb \
       -o /tmp/mp3rgain.deb \
    && apt-get install -y --no-install-recommends /tmp/mp3rgain.deb \
    && rm /tmp/mp3rgain.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir flask==3.1.1 werkzeug==3.1.3

COPY app.py /app/app.py
COPY logo_mp3gainUI.png /app/logo_mp3gainUI.png
COPY banner_mp3gain.png /app/banner_mp3gain.png

EXPOSE 8099

CMD ["python", "/app/app.py"]
