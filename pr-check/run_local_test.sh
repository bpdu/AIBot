#!/bin/bash
# Quick Start Script for PR-Check Local Testing

set -e

echo "🚀 PR-Check Local Test Runner"
echo "================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running from correct directory
if [ ! -f "README.md" ]; then
    echo -e "${RED}❌ Error: Please run this script from pr-check directory${NC}"
    exit 1
fi

# Step 1: Check Python
echo -e "${YELLOW}Step 1: Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python version: $(python3 --version)${NC}"
echo ""

# Step 2: Check dependencies
echo -e "${YELLOW}Step 2: Checking dependencies...${NC}"
if ! python3 -c "import mcp" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 3: Check Ollama
echo -e "${YELLOW}Step 3: Checking Ollama...${NC}"
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama is not installed${NC}"
    echo "Install with: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Ollama is not running${NC}"
    echo "Starting Ollama in background..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
fi

if ! ollama list | grep -q "nomic-embed-text"; then
    echo "Downloading nomic-embed-text model..."
    ollama pull nomic-embed-text
fi
echo -e "${GREEN}✅ Ollama is ready${NC}"
echo ""

# Step 4: Check CODE_STYLE.md
echo -e "${YELLOW}Step 4: Checking CODE_STYLE.md...${NC}"
if [ ! -f "../CODE_STYLE.md" ]; then
    echo -e "${RED}❌ CODE_STYLE.md not found in parent directory${NC}"
    exit 1
fi
echo -e "${GREEN}✅ CODE_STYLE.md found${NC}"
echo ""

# Step 5: Index CODE_STYLE.md
echo -e "${YELLOW}Step 5: Indexing CODE_STYLE.md...${NC}"
if [ ! -f "rag/db.sqlite3" ]; then
    echo "Creating embeddings..."
    cd ..
    python3 pr-check/rag/index_code_style.py
    cd pr-check
else
    echo "Embeddings already exist"
fi
echo -e "${GREEN}✅ Embeddings ready${NC}"
echo ""

# Step 6: Start MCP Server
echo -e "${YELLOW}Step 6: Starting MCP Server...${NC}"
if lsof -i :8082 > /dev/null 2>&1; then
    echo "MCP Server already running on port 8082"
else
    echo "Starting MCP Server in background..."
    cd ..
    python3 pr-check/git_mcp_server.py > /tmp/mcp_server.log 2>&1 &
    MCP_PID=$!
    echo $MCP_PID > /tmp/mcp_server.pid
    cd pr-check
    sleep 3

    if curl -s http://localhost:8082/ > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MCP Server started (PID: $MCP_PID)${NC}"
    else
        echo -e "${RED}❌ MCP Server failed to start${NC}"
        cat /tmp/mcp_server.log
        exit 1
    fi
fi
echo ""

# Step 7: Run tests
echo -e "${YELLOW}Step 7: Running component tests...${NC}"
echo ""

echo "Test 1: RAG Search"
python3 assistant/pr_review/rag_code_style.py | head -20
echo ""

echo "Test 2: MCP Client"
python3 assistant/pr_review/mcp_client.py | head -20
echo ""

# Step 8: Summary
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ All components are ready!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "📝 Next steps:"
echo ""
echo "1. Set environment variables:"
echo "   export GITHUB_TOKEN='ghp_...'"
echo "   export DEEPSEEK_API_KEY='sk-...'"
echo "   export GITHUB_REPOSITORY='owner/repo'"
echo "   export PR_NUMBER=1"
echo "   export PR_BASE='main'"
echo "   export PR_HEAD='feature/branch'"
echo ""
echo "2. Run full review:"
echo "   cd .."
echo "   python3 pr-check/assistant/pr_review/review_orchestrator.py"
echo ""
echo "3. Stop MCP Server when done:"
echo "   kill \$(cat /tmp/mcp_server.pid)"
echo ""
