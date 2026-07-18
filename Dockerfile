FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# tesseract-ocr for scanned PDF OCR, libgl for pymupdf image handling, curl
# for the api healthcheck. Chromium and its OS deps are already bundled in
# this base image (avoids relying on Debian's apt package list for browser
# deps, which broke previously when a package Playwright expects there,
# ttf-unifont, was renamed upstream).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scripts/entrypoint.sh scripts/backup.sh

# NOTE: this container runs as root. A stricter setup would create and
# switch to a non-root user here. Deliberately left as-is for now: this base
# image's Chromium sandbox behaves differently under a non-root user, and on
# Windows/Mac Docker Desktop, non-root containers writing to bind-mounted
# volumes (the ".:/app" mount in docker-compose.yml) commonly hit host/
# container UID permission mismatches. Given this runs as a single-user
# local deployment rather than a multi-tenant internet-facing server, that
# tradeoff is acceptable for now -- revisit if this ever gets deployed
# somewhere more exposed (see docs/AUTONOMY.md on where to actually deploy).

ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
