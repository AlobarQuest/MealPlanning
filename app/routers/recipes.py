import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import recipes as recipes_core
from meal_planner.core.ai_assistant import (
    parse_recipe_text, parse_recipe_url, generate_recipe, modify_recipe,
)
from meal_planner.db.models import Recipe, RecipeIngredient

router = APIRouter(prefix="/recipes", tags=["recipes"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _ctx(request: Request, **kwargs) -> dict:
    return {"active_tab": "recipes", "demo": False, **kwargs}


def _collect_ingredients(form) -> list:
    """Collect indexed ingredient fields, tolerating gaps from deleted rows."""
    indices = set()
    for key in form.keys():
        m = re.match(r"ingredient_name_(\d+)$", key)
        if m:
            indices.add(int(m.group(1)))
    ingredients = []
    for i in sorted(indices):
        ing_name = (form.get(f"ingredient_name_{i}") or "").strip()
        if ing_name:
            qty_str = (form.get(f"ingredient_qty_{i}") or "").strip()
            ingredients.append(RecipeIngredient(
                id=None, recipe_id=None,
                name=ing_name,
                quantity=float(qty_str) if qty_str else None,
                unit=form.get(f"ingredient_unit_{i}") or None,
            ))
    return ingredients


def _recipe_from_form(form, recipe_id=None) -> Recipe:
    rating_str = (form.get("rating") or "").strip()
    servings_str = (form.get("servings") or "4").strip()
    return Recipe(
        id=recipe_id,
        name=form["name"],
        description=form.get("description") or None,
        servings=int(servings_str) if servings_str else 4,
        prep_time=form.get("prep_time") or None,
        cook_time=form.get("cook_time") or None,
        instructions=form.get("instructions") or None,
        source_url=form.get("source_url") or None,
        tags=form.get("tags") or None,
        rating=int(rating_str) if rating_str else None,
        ingredients=_collect_ingredients(form),
    )


# ── List & search ──────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def recipes_page(request: Request):
    recipe_list = recipes_core.get_all()
    return templates.TemplateResponse(request, "recipes.html", _ctx(
        request, recipes=recipe_list,
    ))


@router.get("/list", response_class=HTMLResponse)
def recipes_list(request: Request, q: str = ""):
    recipe_list = recipes_core.search(q) if q else recipes_core.get_all()
    return templates.TemplateResponse(request, "partials/recipe_list.html", {
        "recipes": recipe_list, "q": q,
    })


# ── Add ────────────────────────────────────────────────────────────────────────

@router.get("/add", response_class=HTMLResponse)
def recipes_add_form(request: Request):
    return templates.TemplateResponse(request, "partials/recipe_dialog.html", {
        "recipe": None, "ingredients": [],
    })


@router.post("/add")
async def recipes_add(request: Request):
    form = await request.form()
    recipe = _recipe_from_form(form)
    recipe_id = recipes_core.add(recipe)
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=303)


# ── Ingredient row helper ──────────────────────────────────────────────────────

@router.get("/ingredient-row", response_class=HTMLResponse)
def ingredient_row(request: Request, index: int = 0):
    return templates.TemplateResponse(request, "partials/ingredient_row.html", {
        "i": index, "ing": None,
    })


# ── AI — paste text ───────────────────────────────────────────────────────────

@router.get("/ai/paste", response_class=HTMLResponse)
def ai_paste_form(request: Request):
    return templates.TemplateResponse(request, "partials/recipe_ai_form.html", {
        "mode": "paste", "recipe_id": None,
    })


@router.post("/ai/parse-text", response_class=HTMLResponse)
def ai_parse_text(request: Request, text: str = Form(...)):
    recipe = parse_recipe_text(text)
    return templates.TemplateResponse(request, "partials/recipe_dialog.html", {
        "recipe": recipe,
        "ingredients": recipe.ingredients if recipe else [],
        "is_ai_preview": True,
    })


# ── AI — from URL ─────────────────────────────────────────────────────────────

@router.get("/ai/url", response_class=HTMLResponse)
def ai_url_form(request: Request):
    return templates.TemplateResponse(request, "partials/recipe_ai_form.html", {
        "mode": "url", "recipe_id": None,
    })


@router.post("/ai/parse-url", response_class=HTMLResponse)
def ai_parse_url(request: Request, url: str = Form(...)):
    recipe = parse_recipe_url(url)
    return templates.TemplateResponse(request, "partials/recipe_dialog.html", {
        "recipe": recipe,
        "ingredients": recipe.ingredients if recipe else [],
        "is_ai_preview": True,
    })


# ── AI — generate ─────────────────────────────────────────────────────────────

@router.get("/ai/generate", response_class=HTMLResponse)
def ai_generate_form(request: Request):
    return templates.TemplateResponse(request, "partials/recipe_ai_form.html", {
        "mode": "generate", "recipe_id": None,
    })


@router.post("/ai/generate", response_class=HTMLResponse)
def ai_generate(request: Request, preferences: str = Form("")):
    recipe = generate_recipe(preferences)
    return templates.TemplateResponse(request, "partials/recipe_dialog.html", {
        "recipe": recipe,
        "ingredients": recipe.ingredients if recipe else [],
        "is_ai_preview": True,
    })


# ── Detail, edit, delete ──────────────────────────────────────────────────────

@router.get("/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(request: Request, recipe_id: int):
    recipe = recipes_core.get(recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "partials/recipe_detail.html", {
        "recipe": recipe, "demo": False,
    })


@router.get("/{recipe_id}/edit", response_class=HTMLResponse)
def recipe_edit_form(request: Request, recipe_id: int):
    recipe = recipes_core.get(recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "partials/recipe_dialog.html", {
        "recipe": recipe, "ingredients": recipe.ingredients,
    })


@router.post("/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit(request: Request, recipe_id: int):
    form = await request.form()
    recipe = _recipe_from_form(form, recipe_id=recipe_id)
    recipes_core.update(recipe)
    updated = recipes_core.get(recipe_id)
    return templates.TemplateResponse(request, "partials/recipe_detail.html", {
        "recipe": updated, "demo": False,
    })


@router.delete("/{recipe_id}")
def recipe_delete(recipe_id: int):
    recipes_core.delete(recipe_id)
    return HTMLResponse("", headers={"HX-Redirect": "/recipes"})


# ── AI — modify ───────────────────────────────────────────────────────────────

@router.get("/{recipe_id}/ai/modify", response_class=HTMLResponse)
def ai_modify_form(request: Request, recipe_id: int):
    return templates.TemplateResponse(request, "partials/recipe_ai_form.html", {
        "mode": "modify", "recipe_id": recipe_id,
    })


@router.post("/{recipe_id}/ai/modify", response_class=HTMLResponse)
def ai_modify(request: Request, recipe_id: int, instruction: str = Form(...)):
    recipe = recipes_core.get(recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404)
    modified = modify_recipe(recipe, instruction)
    result = modified or recipe
    if modified:
        result.id = recipe_id
    return templates.TemplateResponse(request, "partials/recipe_dialog.html", {
        "recipe": result,
        "ingredients": result.ingredients,
        "is_ai_preview": True,
    })
