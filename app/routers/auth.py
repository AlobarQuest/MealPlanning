import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.dependencies import create_session_token, SESSION_COOKIE, SESSION_MAX_AGE

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

def _app_password() -> str:
    """Read APP_PASSWORD at call time so tests can set it via env."""
    return os.environ.get("APP_PASSWORD", "")


@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/pantry", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password and password == _app_password():
        resp = RedirectResponse(url="/pantry", status_code=302)
        resp.set_cookie(
            SESSION_COOKIE,
            create_session_token(),
            httponly=True,
            samesite="lax",
            max_age=SESSION_MAX_AGE,
        )
        return resp
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "Invalid password"},
        status_code=200,
    )


@router.post("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp
