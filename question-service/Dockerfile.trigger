# Dockerfile for Question Generation Trigger Service
# This runs a web server that allows manual triggering of question generation
#
# Build context: /
# Dockerfile path: /question-service/Dockerfile.trigger
#
# Example build command (from repo root):
#   docker build -f question-service/Dockerfile.trigger -t question-service .
FROM python:3.11-slim

# Install system dependencies first (this layer changes rarely)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for build
WORKDIR /build

# Copy requirements and install Python dependencies
COPY question-service/requirements.txt .
# Upgrade pip and install with retry logic and increased timeout
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --retries 5 --timeout 300 -r requirements.txt

# Switch to application directory
WORKDIR /app

# Copy question-service application code
COPY question-service/ /app/question-service/

# Copy shared aiq-internal types (single source of truth for enums used by both services)
COPY aiq_types/ /app/aiq_types/

# Set working directory to question-service for runtime
WORKDIR /app/question-service

# Set PYTHONPATH to include question-service (for app imports) and /app (for aiq_types)
ENV PYTHONPATH=/app/question-service:/app

# Use delta temporality for OTLP metric export.
# This service runs as a short-lived batch job: cumulative counters cause Mimir to
# reject metrics with "invalid temporality and type combination" because the
# start_time_unix_nano resets on every run. Delta temporality sends per-run deltas
# that Grafana Cloud's OTLP gateway aggregates correctly into cumulative Prometheus counters.
ENV OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for Railway
# Note: Railway injects PORT environment variable at runtime based on this EXPOSE
EXPOSE 8080

# Run the trigger server
CMD ["python", "trigger_server.py"]
