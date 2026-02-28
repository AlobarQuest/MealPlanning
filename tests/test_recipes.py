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
