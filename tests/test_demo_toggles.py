from app.services import geo as geo_service
from app.services import notify


def test_toggle_provider_a_down_and_up(client):
    resp = client.post("/demo/geo-provider-a/down")
    assert resp.status_code == 200
    assert resp.json()["forced_down"] is True
    assert geo_service.FORCE_DOWN_A is True

    resp = client.post("/demo/geo-provider-a/up")
    assert resp.json()["forced_down"] is False
    assert geo_service.FORCE_DOWN_A is False


def test_toggle_email_side_effect_and_submission_still_succeeds(client, widget):
    client.post("/demo/email-side-effect/failing")
    assert notify.FORCE_FAIL is True

    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "a@example.com"}},
    )
    assert resp.status_code == 201  # side effect fails, submission still succeeds

    client.post("/demo/email-side-effect/ok")
    assert notify.FORCE_FAIL is False


def test_reset_clears_all_toggles(client):
    client.post("/demo/geo-provider-a/down")
    client.post("/demo/geo-provider-b/down")
    client.post("/demo/email-side-effect/failing")

    client.post("/demo/reset")

    status = client.get("/demo/status").json()
    assert status == {
        "geo_provider_a_down": False,
        "geo_provider_b_down": False,
        "email_side_effect_failing": False,
    }
