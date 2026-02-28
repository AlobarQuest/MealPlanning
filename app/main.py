import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from meal_planner.db.database import init_db
from app.dependencies import verify_session_token, is_public, SESSION_COOKIE
from app.routers import auth, pantry, recipes, meal_plan, shopping, stores, settings, demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize main DB
    init_db()
    # Initialize and seed demo DB if DEMO_DB_URL is set
    demo_url = os.environ.get("DEMO_DB_URL")
    if demo_url:
        from meal_planner.db.database import override_db_path
        from demo.seed import seed_if_empty
        with override_db_path(Path(demo_url)):
            init_db()
            seed_if_empty()
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not is_public(request.url.path):
        token = request.cookies.get(SESSION_COOKIE)
        if not token or not verify_session_token(token):
            return RedirectResponse(url="/login", status_code=302)
    return await call_next(request)


app.include_router(auth.router)
app.include_router(pantry.router)
app.include_router(recipes.router)
app.include_router(meal_plan.router)
app.include_router(shopping.router)
app.include_router(stores.router)
app.include_router(settings.router)
app.include_router(demo.router)
