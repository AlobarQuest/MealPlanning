from meal_planner.core import staples as staples_core
from meal_planner.db.models import Staple


def test_staples_list_returns_200(authed_client):
    resp = authed_client.get("/pantry/staples")
    assert resp.status_code == 200
    assert "staple" in resp.text.lower() or "on hand" in resp.text.lower()


def test_staples_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/pantry/staples/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_staples_add_saves_staple(authed_client):
    resp = authed_client.post("/pantry/staples/add", data={"name": "Olive Oil"})
    assert resp.status_code == 200
    assert "Olive Oil" in resp.text


def test_staples_edit_form_returns_dialog(authed_client):
    staples_core.add(Staple(id=None, name="Salt"))
    staple = next(s for s in staples_core.get_all() if s.name == "Salt")
    resp = authed_client.get(f"/pantry/staples/{staple.id}/edit")
    assert resp.status_code == 200
    assert "Salt" in resp.text


def test_staples_edit_saves_changes(authed_client):
    staples_core.add(Staple(id=None, name="Pepper"))
    staple = staples_core.get_all()[-1]
    resp = authed_client.post(f"/pantry/staples/{staple.id}/edit", data={"name": "Black Pepper"})
    assert resp.status_code == 200
    assert "Black Pepper" in resp.text


def test_staples_delete_removes_staple(authed_client):
    staples_core.add(Staple(id=None, name="DeleteMe"))
    staple = next(s for s in staples_core.get_all() if s.name == "DeleteMe")
    resp = authed_client.delete(f"/pantry/staples/{staple.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""
    assert staples_core.get(staple.id) is None
