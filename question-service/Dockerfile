# Multi-stage build for question generation service
# NOTE: This Dockerfile is built from the repo root to access shared libs
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY question-service/requirements.txt .
# Upgrade pip and install with retry logic and increased timeout
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user --retries 5 --timeout 300 -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN useradd -m -u 1000 appuser

# Copy Python dependencies from builder to appuser's home
COPY --from=builder /root/.local /home/appuser/.local

# Copy shared libraries
COPY libs/ /app/libs/

# Copy question-service application code
COPY question-service/ /app/question-service/

# Set working directory to question-service for app imports
WORKDIR /app/question-service

# Set PYTHONPATH to include both app root (for libs) and question-service
ENV PYTHONPATH=/app:/app/question-service

# Fix permissions
RUN chown -R appuser:appuser /app /home/appuser/.local

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Default command runs question generation with async parallelism
# Can be overridden with docker run arguments
CMD ["python", "run_generation.py", "--count", "50", "--async", "--async-judge", "--verbose", "--triggered-by", "scheduler"]
