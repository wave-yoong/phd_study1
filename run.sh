#!/bin/bash
# Launch a user-control agent for PhD Study 1 (Effect of User Control).
#
# Study versions in this repo (pick with the STUDY env var):
#   STUDY=stock (default)   : stock-report agent, EXECUTION-VERSION control.
#                             Agent offers 2-3 versions (length/model/time); user
#                             picks which to run, report is identical regardless.
#                             Conditions: version vs auto. (fixed content, no API key)
#   STUDY=hiring            : hiring-decision agent, DECISIONAL control
#                             ("deciding WHAT to do"). Conditions: decision vs auto.
#   STUDY=finance           : finance allocation agent, also decisional control.
#   STUDY=diet              : diet/exercise agent, PROCESS control (control vs auto).
#
# Usage:
#   ./run.sh demo               # demo mode, no API key, stock study
#   ./run.sh                    # real LLM (Azure/OpenAI creds from .env)
#   STUDY=hiring ./run.sh demo  # run a different study

STUDY="${STUDY:-stock}"
export STUDY

echo "======================================"
echo "User-Control Agent  (STUDY=$STUDY)"
echo "======================================"
echo ""

# Create .env from template if missing
if [ ! -f .env ]; then
    echo "⚠️  .env not found. Creating from .env.example..."
    cp .env.example .env
    echo "✓ Created .env (edit it to add your API key for production mode)"
    echo ""
fi

if [ "$STUDY" = "diet" ]; then
    GROUPS="?group=control or ?group=auto"
elif [ "$STUDY" = "stock" ]; then
    GROUPS="?group=version or ?group=auto"
else
    GROUPS="?group=decision or ?group=auto"   # hiring / finance
fi

# Run from the repository root so package imports and DATABASE_PATH resolve.
if [ "$1" = "demo" ] || [ "$1" = "--demo" ]; then
    echo "🎭 DEMO MODE (mock agent, no API key needed)"
    echo "   Open http://localhost:5000   ($GROUPS to force a condition)"
    echo ""
    USE_MOCK_GPT=1 python -m backend.app
else
    echo "🚀 PRODUCTION MODE (real LLM via Azure/OpenAI)"
    echo "   Open http://localhost:5000   ($GROUPS to force a condition)"
    echo ""
    python -m backend.app
fi
