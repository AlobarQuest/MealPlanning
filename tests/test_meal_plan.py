def test_meal_plan_page(authed_client):
    resp = authed_client.get("/meal-plan")
    assert resp.status_code == 200
    assert "meal" in resp.text.lower()


def test_meal_plan_grid_partial(authed_client):
    resp = authed_client.get("/meal-plan/grid?week=2026-02-23")
    assert resp.status_code == 200
    assert "Breakfast" in resp.text
    assert "Dinner" in resp.text


def test_meal_plan_with_week_param(authed_client):
    resp = authed_client.get("/meal-plan?week=2026-02-23")
    assert resp.status_code == 200


def test_meal_picker(authed_client):
    resp = authed_client.get("/meal-plan/pick/2026-02-23/Dinner")
    assert resp.status_code == 200
    assert "dialog" in resp.text.lower()


def test_meal_set_and_clear(authed_client):
    # Set a meal (no recipe, just notes)
    set_resp = authed_client.post("/meal-plan/set", data={
        "date": "2026-03-10",
        "slot": "Lunch",
        "recipe_id": "",
        "servings": "1",
        "notes": "Leftovers",
        "week": "2026-03-09",
    })
    assert set_resp.status_code == 200

    # Grid should show the entry
    grid_resp = authed_client.get("/meal-plan/grid?week=2026-03-09")
    assert grid_resp.status_code == 200
    assert "Leftovers" in grid_resp.text

    # Clear it
    clear_resp = authed_client.post("/meal-plan/clear", data={
        "date": "2026-03-10",
        "slot": "Lunch",
        "week": "2026-03-09",
    })
    assert clear_resp.status_code == 200


def test_meal_set_with_recipe(authed_client):
    # First add a recipe to use
    add_resp = authed_client.post("/recipes/add", data={
        "name": "Meal Plan Test Recipe",
        "servings": "2",
        "ingredient_name_0": "Pasta",
    }, follow_redirects=False)
    recipe_id = int(add_resp.headers["location"].split("/")[-1])

    # Set that recipe in the meal plan
    set_resp = authed_client.post("/meal-plan/set", data={
        "date": "2026-03-11",
        "slot": "Dinner",
        "recipe_id": str(recipe_id),
        "servings": "2",
        "notes": "",
        "week": "2026-03-09",
    })
    assert set_resp.status_code == 200
    assert "Meal Plan Test Recipe" in set_resp.text
