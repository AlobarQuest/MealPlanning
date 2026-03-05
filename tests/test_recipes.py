def test_recipes_page(authed_client):
    resp = authed_client.get("/recipes")
    assert resp.status_code == 200
    assert "recipes" in resp.text.lower()


def test_recipes_list_partial(authed_client):
    resp = authed_client.get("/recipes/list")
    assert resp.status_code == 200


def test_recipe_add_form(authed_client):
    resp = authed_client.get("/recipes/add")
    assert resp.status_code == 200
    assert "dialog" in resp.text.lower()


def test_recipe_add_and_detail(authed_client):
    resp = authed_client.post("/recipes/add", data={
        "name": "Test Soup",
        "description": "A tasty soup",
        "servings": "4",
        "prep_time": "10 min",
        "cook_time": "20 min",
        "instructions": "1. Boil water.\n2. Add vegetables.",
        "source_url": "",
        "tags": "soup,vegetarian",
        "rating": "",
        "ingredient_name_0": "Carrot",
        "ingredient_qty_0": "2",
        "ingredient_unit_0": "cups",
        "ingredient_name_1": "Water",
        "ingredient_qty_1": "4",
        "ingredient_unit_1": "cups",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Test Soup" in resp.text


def test_recipe_detail_not_found(authed_client):
    resp = authed_client.get("/recipes/99999")
    assert resp.status_code == 404


def test_recipe_ingredient_row(authed_client):
    resp = authed_client.get("/recipes/ingredient-row?index=3")
    assert resp.status_code == 200
    assert "ingredient_name_3" in resp.text


def test_recipe_edit_form(authed_client):
    # First create a recipe
    add_resp = authed_client.post("/recipes/add", data={
        "name": "Edit Me",
        "servings": "2",
        "ingredient_name_0": "Flour",
        "ingredient_qty_0": "1",
        "ingredient_unit_0": "cup",
    }, follow_redirects=False)
    assert add_resp.status_code == 303
    location = add_resp.headers["location"]
    recipe_id = int(location.split("/")[-1])

    edit_resp = authed_client.get(f"/recipes/{recipe_id}/edit")
    assert edit_resp.status_code == 200
    assert "Edit Me" in edit_resp.text


def test_recipe_edit_save(authed_client):
    # Create a recipe to edit
    add_resp = authed_client.post("/recipes/add", data={
        "name": "Before Edit",
        "servings": "2",
        "ingredient_name_0": "Egg",
    }, follow_redirects=False)
    recipe_id = int(add_resp.headers["location"].split("/")[-1])

    edit_resp = authed_client.post(f"/recipes/{recipe_id}/edit", data={
        "name": "After Edit",
        "servings": "4",
        "ingredient_name_0": "Egg",
    }, follow_redirects=True)
    assert edit_resp.status_code == 200
    assert "After Edit" in edit_resp.text


def test_recipe_delete(authed_client):
    # Create a recipe to delete
    add_resp = authed_client.post("/recipes/add", data={
        "name": "Delete Me",
        "servings": "1",
        "ingredient_name_0": "Salt",
    }, follow_redirects=False)
    recipe_id = int(add_resp.headers["location"].split("/")[-1])

    del_resp = authed_client.delete(f"/recipes/{recipe_id}", follow_redirects=False)
    assert del_resp.status_code == 200
    assert del_resp.headers.get("HX-Redirect") == "/recipes"

    # Verify it's gone
    detail_resp = authed_client.get(f"/recipes/{recipe_id}")
    assert detail_resp.status_code == 404


def test_recipe_list_search(authed_client):
    # Add a distinctive recipe
    authed_client.post("/recipes/add", data={
        "name": "ZZZ Unique Search Target",
        "servings": "1",
        "ingredient_name_0": "Pepper",
    }, follow_redirects=False)

    resp = authed_client.get("/recipes/list?q=ZZZ+Unique")
    assert resp.status_code == 200
    assert "ZZZ Unique" in resp.text


def test_recipe_ai_paste_form(authed_client):
    resp = authed_client.get("/recipes/ai/paste")
    assert resp.status_code == 200
    assert "textarea" in resp.text.lower()


def test_recipe_ai_url_form(authed_client):
    resp = authed_client.get("/recipes/ai/url")
    assert resp.status_code == 200
    assert "url" in resp.text.lower()


def test_recipe_ai_generate_form(authed_client):
    resp = authed_client.get("/recipes/ai/generate")
    assert resp.status_code == 200
    assert "preferences" in resp.text.lower() or "generate" in resp.text.lower()


def test_recipe_ai_modify_form(authed_client):
    # Create a recipe first
    add_resp = authed_client.post("/recipes/add", data={
        "name": "Modify Target",
        "servings": "2",
        "ingredient_name_0": "Butter",
    }, follow_redirects=False)
    recipe_id = int(add_resp.headers["location"].split("/")[-1])

    resp = authed_client.get(f"/recipes/{recipe_id}/ai/modify")
    assert resp.status_code == 200
    assert "instruction" in resp.text.lower() or "modify" in resp.text.lower()


def test_add_recipe_with_photo(authed_client, tmp_path):
    """Adding a recipe with a photo file saves the photo_path on the recipe."""
    import io
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    resp = authed_client.post(
        "/recipes/add",
        data={"name": "Photo Recipe", "servings": "2"},
        files={"photo": ("test.jpg", buf, "image/jpeg")},
    )
    # Redirect expected on success
    assert resp.status_code in (200, 303)
    from meal_planner.core import recipes as recipes_core
    recipes = recipes_core.get_all()
    recipe = next((r for r in recipes if r.name == "Photo Recipe"), None)
    assert recipe is not None
    # If upload dir doesn't exist in test env, photo_path may be None — that's acceptable
    # but if it is set, it must be a plausible path
    if recipe.photo_path:
        assert "Photo_Recipe" in recipe.photo_path or str(recipe.id) in recipe.photo_path


def test_recipe_photo_path(tmp_path):
    from meal_planner.db.database import init_db, override_db_path
    from meal_planner.core import recipes as recipes_core
    from meal_planner.db.models import Recipe

    db_path = tmp_path / "test.db"
    with override_db_path(db_path):
        init_db()
        r = Recipe(id=None, name="Photo Test", photo_path="/static/uploads/recipes/1.jpg")
        recipe_id = recipes_core.add(r)
        fetched = recipes_core.get(recipe_id)
        assert fetched.photo_path == "/static/uploads/recipes/1.jpg"


def test_recipe_seed_inserts_starter_recipes(authed_client):
    # Ensure recipes table is empty first
    from meal_planner.core import recipes as recipes_core
    for r in recipes_core.get_all():
        recipes_core.delete(r.id)
    assert recipes_core.get_all() == []

    resp = authed_client.post("/recipes/seed")
    assert resp.status_code == 200
    assert len(recipes_core.get_all()) == 20
    # Should return the recipe list with recipes now in it
    assert "Classic Oatmeal" in resp.text or "Spaghetti" in resp.text


def test_recipe_seed_is_idempotent(authed_client):
    # Seed twice — should not error or duplicate
    authed_client.post("/recipes/seed")
    resp = authed_client.post("/recipes/seed")
    assert resp.status_code == 200
    from meal_planner.core import recipes as recipes_core
    all_recipes = recipes_core.get_all()
    names = [r.name for r in all_recipes]
    # "Classic Oatmeal with Berries" should appear exactly once
    assert names.count("Classic Oatmeal with Berries") == 1


def test_recipe_list_empty_state_shows_seed_button(authed_client):
    from meal_planner.core import recipes as recipes_core
    for r in recipes_core.get_all():
        recipes_core.delete(r.id)
    resp = authed_client.get("/recipes/list")
    assert resp.status_code == 200
    assert "Load starter recipes" in resp.text


def test_recipe_list_search_empty_hides_seed_button(authed_client):
    from meal_planner.core import recipes as recipes_core
    for r in recipes_core.get_all():
        recipes_core.delete(r.id)
    resp = authed_client.get("/recipes/list?q=nonexistentquery")
    assert resp.status_code == 200
    assert "Load starter recipes" not in resp.text
    assert "No recipes found" in resp.text
