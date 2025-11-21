#!/bin/bash
set -e

echo "Starting AIQ Backend..."

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Add local bin to PATH
export PATH="/root/.local/bin:$PATH"

# Run database migrations
echo "Running database migrations..."
python -m pip show alembic > /dev/null 2>&1
if [ $? -eq 0 ]; then
    python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
else
    echo "Warning: alembic not found, skipping migrations"
fi

# Start the application
echo "Starting gunicorn..."
exec gunicorn app.main:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --access-logfile - \
    --error-logfile -
