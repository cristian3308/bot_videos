# Cybercrime Studio — imagen para correr el panel 24/7 (Linux)
FROM python:3.11-slim

# FFmpeg + dependencias del sistema para Chromium/Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . .

# El panel debe escuchar en todas las interfaces dentro del contenedor
ENV WEB_HOST=0.0.0.0 \
    WEB_PORT=8000 \
    OUTPUT_DIR=output_videos

EXPOSE 8000

# Las API keys se pasan con -e OPENCODE_API_KEY=... o con --env-file .env
CMD ["python", "run.py"]
