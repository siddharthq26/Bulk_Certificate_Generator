#!/bin/bash

# Ensure Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Starting Redis..."
    brew services start redis
    sleep 1
fi

echo "=================================================="
echo " Starting Bulk Certificate Generator (Dev Server)"
echo "=================================================="
echo "API Docs (Swagger UI): http://localhost:8000/docs"
echo "API Health Check:      http://localhost:8000/health"
echo "=================================================="
echo ""

# Activate virtualenv
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Trap SIGINT/SIGTERM to gracefully stop background celery worker
cleanup() {
    echo ""
    echo "Stopping Celery worker..."
    kill "$CELERY_PID" 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Celery worker in the background (using solo pool for macOS Python 3.14 compatibility)
celery -A app.tasks.celery_app worker --pool=solo --loglevel=info &
CELERY_PID=$!

# Start FastAPI server (hot-reloads on file change, just like npm run dev)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

