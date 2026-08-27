# Playwright's official image already bundles Python, browsers, and all
# OS-level dependencies required by Chromium/Firefox/WebKit - this avoids
# the notoriously large/fragile `playwright install-deps` step on Render.
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Prevent Python from buffering stdout/stderr (important for Render logs)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Browsers are already present in the base image, but this ensures the
# exact browser binaries/versions required by the pinned playwright package
# are installed (no-op if already satisfied).
RUN playwright install chromium --with-deps

# Copy application code.
COPY . .

# Render injects $PORT at runtime; default kept for local `docker run`.
ENV PORT=10000
EXPOSE 10000

CMD ["python", "main.py"]
