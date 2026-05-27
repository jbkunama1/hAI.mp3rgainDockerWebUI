FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates tar \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L https://github.com/M-Igashi/mp3rgain/releases/latest/download/mp3rgain-v1.2.0-linux-x86_64.tar.gz -o /tmp/mp3rgain.tar.gz \
    && tar -xzf /tmp/mp3rgain.tar.gz -C /usr/local/bin \
    && chmod +x /usr/local/bin/mp3rgain \
    && rm /tmp/mp3rgain.tar.gz

WORKDIR /app

RUN pip install --no-cache-dir flask==3.1.1 werkzeug==3.1.3

COPY app.py /app/app.py

EXPOSE 8099

CMD ["python", "/app/app.py"]
