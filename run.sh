#!/bin/bash
# Meal Planner — local development startup

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

source .venv/bin/activate

# Copy .env.example if no .env exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/generate-a-long-random-string-here/$SECRET/" .env
    echo "Created .env — set APP_PASSWORD and CLAUDE_API_KEY before using."
fi

uvicorn app.main:app --reload --port 8080
