from conftest import solve_pow_challenge


def test_widget_creation_returns_embed_snippet(client, tenant_and_key):
    resp = client.post(
        "/api/widgets",
        headers={"X-API-Key": tenant_and_key["api_key"]},
        json={
            "type": "cta_popover",
            "title": "Get a discount",
            "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["embed_snippet"].startswith("<script src=")
    assert body["id"] in body["embed_snippet"]
    assert "/widget/v1.js" in body["embed_snippet"]


def test_versioned_bundle_is_immutable_cached(client):
    resp = client.get("/widget/v1.js")
    assert resp.status_code == 200
    assert "immutable" in resp.headers["cache-control"]
    assert "application/javascript" in resp.headers["content-type"]


def test_unversioned_bundle_alias_is_short_cached(client):
    resp = client.get("/widget.js")
    assert resp.status_code == 200
    assert "immutable" not in resp.headers["cache-control"]
    assert "max-age=300" in resp.headers["cache-control"]


def test_config_endpoint_public_cors_and_short_cache(client, widget):
    resp = client.get(f"/widgets/{widget['id']}/config")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=60"
    assert resp.headers["access-control-allow-origin"] == "*"
    body = resp.json()
    # Public config never leaks tenant-internal fields.
    assert "tenant_id" not in body


def test_config_404_for_unknown_widget(client):
    resp = client.get("/widgets/does-not-exist/config")
    assert resp.status_code == 404


def test_full_second_origin_flow_config_then_submit(client, widget):
    """Simulates exactly what test-site/index.html's widget.js does: fetch
    config from one origin, then POST a submission from a different one."""
    customer_origin = "http://localhost:5500"

    config_resp = client.get(
        f"/widgets/{widget['id']}/config", headers={"Origin": customer_origin}
    )
    assert config_resp.status_code == 200
    config = config_resp.json()
    assert config["fields"][0]["name"] == "email"

    submit_resp = client.post(
        "/submissions",
        headers={"Origin": customer_origin},
        json={
            "widget_id": widget["id"],
            "data": {"email": "visitor@example.com"},
            "website": "",  # honeypot left empty by a real visitor
            **solve_pow_challenge(client, widget["id"]),
        },
    )
    assert submit_resp.status_code == 201
    assert submit_resp.headers["access-control-allow-origin"] == customer_origin
