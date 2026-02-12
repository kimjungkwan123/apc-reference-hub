FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV APC_HUB_DATA_DIR=/app/data_store

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libasound2 \
    libxss1 \
    libgbm1 \
    libxrandr2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libu2f-udev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN python -m playwright install chromium

COPY . .

EXPOSE 8511

CMD ["./run_web.sh"]
