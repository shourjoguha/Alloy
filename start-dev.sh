#!/bin/bash
set -e

echo "🚀 Starting Gainsly development environment..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Ollama...${NC}"
cd "$(dirname "$0")"
ollama serve > ollama.log 2>&1 &
OLLAMA_PID=$!
echo -e "${GREEN}✓ Ollama started (PID: $OLLAMA_PID)${NC}"

echo -e "${BLUE}Starting PostgreSQL (Docker)...${NC}"
CONTAINER_NAME="alloy"
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Starting existing container ${CONTAINER_NAME}..."
        docker start ${CONTAINER_NAME}
    else
        echo "Creating new container ${CONTAINER_NAME}..."
        docker run -d \
            --name ${CONTAINER_NAME} \
            -p 5433:5432 \
            -e POSTGRES_USER=gainsly \
            -e POSTGRES_PASSWORD=gainslypass \
            -e POSTGRES_DB=gainslydb \
            --health-cmd="pg_isready -U gainsly -d gainslydb" \
            --health-interval=5s \
            --health-timeout=5s \
            --health-retries=5 \
            pgvector/pgvector:pg16
    fi
    echo -e "${GREEN}✓ PostgreSQL container started${NC}"
    sleep 3
else
    echo -e "${GREEN}✓ PostgreSQL container already running${NC}"
fi

echo -e "${BLUE}Starting backend (FastAPI)...${NC}"
source .venv/bin/activate
echo -e "${BLUE}Running migrations (Alembic)...${NC}"
alembic upgrade head || echo "Migration check completed"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
sleep 5

# Start frontend
echo ""
echo -e "${BLUE}Starting frontend (Vite)...${NC}"
cd frontend
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"

echo ""
echo -e "${GREEN}✓ Development environment ready!${NC}"
echo ""
echo "Ollama:   http://localhost:11434"
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Log files:"
echo "  - ollama.log"
echo "  - backend.log"
echo "  - frontend.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Handle cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $OLLAMA_PID 2>/dev/null || true
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    echo "All services stopped"
    wait
}

trap cleanup EXIT INT TERM

# Keep script running
wait
