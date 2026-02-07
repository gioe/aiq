# Dockerfile for Question Generation Trigger Service
# This runs a web server that allows manual triggering of question generation
#
# IMPORTANT: This Dockerfile must be built from the REPO ROOT directory
# to access the shared libs/ folder.
#
# Build context: /
# Dockerfile path: /question-service/Dockerfile.trigger
#
# Example build command (from repo root):
#   docker build -f question-service/Dockerfile.trigger -t question-service .
FROM python:3.11-slim

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
    pip install --no-cache-dir --retries 5 --timeout 300 -r requirements.txt

# Copy shared libraries (required for observability facade)
COPY libs/ /app/libs/

# Copy question-service application code
COPY question-service/ /app/question-service/

# Set working directory to question-service for app imports
WORKDIR /app/question-service

# Set PYTHONPATH to include repo root (for libs) and question-service (for app)
ENV PYTHONPATH=/app:/app/question-service

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for the web server
EXPOSE 8080

# Run the trigger server
CMD ["python", "trigger_server.py"]
