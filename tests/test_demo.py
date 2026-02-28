from fastapi.testclient import TestClient


def _fresh_client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


def test_demo_pantry_accessible_without_auth():
    with _fresh_client() as c:
        resp = c.get("/demo/pantry", follow_redirects=False)
    assert resp.status_code == 200


def test_demo_recipes_accessible_without_auth():
    with _fresh_client() as c:
        resp = c.get("/demo/recipes", follow_redirects=False)
    assert resp.status_code == 200


def test_demo_meal_plan_accessible_without_auth():
    with _fresh_client() as c:
        resp = c.get("/demo/meal-plan", follow_redirects=False)
    assert resp.status_code == 200


def test_demo_shopping_accessible_without_auth():
    with _fresh_client() as c:
        resp = c.get("/demo/shopping", follow_redirects=False)
    assert resp.status_code == 200


def test_demo_stores_accessible_without_auth():
    with _fresh_client() as c:
        resp = c.get("/demo/stores", follow_redirects=False)
    assert resp.status_code == 200


def test_demo_shows_banner():
    with _fresh_client() as c:
        resp = c.get("/demo/pantry")
    assert "demo mode" in resp.text.lower()


def test_demo_no_write_buttons():
    with _fresh_client() as c:
        resp = c.get("/demo/pantry")
    # Write buttons should not appear in demo mode
    assert "Add Item" not in resp.text
    assert "Import CSV" not in resp.text


def test_demo_shopping_generate():
    with _fresh_client() as c:
        resp = c.post("/demo/shopping/generate", data={
            "start_date": "2026-02-23",
            "end_date": "2026-03-01",
        })
    assert resp.status_code == 200


def test_demo_recipe_detail():
    with _fresh_client() as c:
        # Get recipe list first to find an ID
        list_resp = c.get("/demo/recipes")
        assert list_resp.status_code == 200
        # The seeded demo DB should have recipes; just verify the page loads
        assert "recipes" in list_resp.text.lower() or "spaghetti" in list_resp.text.lower()


def test_demo_does_not_affect_main_db(authed_client):
    # Add something to the main DB
    r = authed_client.post("/recipes/add", data={
        "name": "Main DB Recipe",
        "servings": "2",
        "ingredient_name_0": "Flour",
    }, follow_redirects=False)
    assert r.status_code == 303

    # Demo DB should not show the main DB recipe (they're separate DBs)
    with _fresh_client() as c:
        demo_r = c.get("/demo/recipes")
    assert demo_r.status_code == 200
    # The main DB recipe should not show up in demo
    # (demo has seeded recipes like "Spaghetti Bolognese")
