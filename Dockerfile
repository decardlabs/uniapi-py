FROM python:3.12-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY app/ app/
COPY alembic.ini alembic/ alembic/

# Copy frontend build (if available at build time)
COPY web/build/modern/ web/build/modern/ 2>/dev/null || true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
