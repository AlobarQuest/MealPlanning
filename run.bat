@echo off
:: Meal Planner — local development startup (Windows)

if not exist ".venv\" (
    echo Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

if not exist ".env" (
    copy .env.example .env
    echo Created .env -- set APP_PASSWORD and CLAUDE_API_KEY before using.
)

.venv\Scripts\uvicorn app.main:app --reload --port 8080
