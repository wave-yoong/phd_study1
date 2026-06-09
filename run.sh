#!/bin/bash
# Launch the AI diet-planning agent (PhD Study 1 - Effect of User Control)
# Usage:
#   ./run.sh demo   # demo mode, no API key needed (mock agent)
#   ./run.sh        # real LLM (uses Azure/OpenAI creds from .env)

echo "======================================"
echo "AI Diet Planner Agent"
echo "======================================"
echo ""

# Create .env from template if missing
if [ ! -f .env ]; then
    echo "⚠️  .env not found. Creating from .env.example..."
    cp .env.example .env
    echo "✓ Created .env (edit it to add your API key for production mode)"
    echo ""
fi

# Run from the repository root so package imports and DATABASE_PATH resolve.
if [ "$1" = "demo" ] || [ "$1" = "--demo" ]; then
    echo "🎭 DEMO MODE (mock agent, no API key needed)"
    echo "   Open http://localhost:5000   (?group=control or ?group=auto to force a condition)"
    echo ""
    USE_MOCK_GPT=1 python -m backend.app
else
    echo "🚀 PRODUCTION MODE (real LLM via Azure/OpenAI)"
    echo "   Open http://localhost:5000   (?group=control or ?group=auto to force a condition)"
    echo ""
    python -m backend.app
fi
