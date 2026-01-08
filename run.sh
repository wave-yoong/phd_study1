#!/bin/bash
# Simple script to run the Flask chatbot application

echo "======================================"
echo "Flask 3-Stage Chatbot Starter"
echo "======================================"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "Please edit .env and add your OPENAI_API_KEY"
    echo "Or run in DEMO mode (see below)"
    echo ""
fi

# Check which mode to run
if [ "$1" = "demo" ] || [ "$1" = "--demo" ]; then
    echo "🎭 Starting in DEMO MODE (mock responses)"
    echo ""
    cd backend && DEMO_MODE=true python run.py
else
    # Check if OPENAI_API_KEY is set
    if grep -q "your_openai_api_key_here" .env 2>/dev/null; then
        echo "⚠️  OPENAI_API_KEY not set in .env file"
        echo ""
        echo "Options:"
        echo "  1. Edit .env and add your OpenAI API key"
        echo "  2. Run in DEMO mode: ./run.sh demo"
        echo ""
        exit 1
    fi
    
    echo "🚀 Starting in PRODUCTION MODE (OpenAI API)"
    echo ""
    cd backend && python run.py
fi
