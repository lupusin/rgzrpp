import pytest
from app import create_app

@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()

def test_shorten_and_follow_and_stats(client):
    r = client.post("/shorten", json={"url": "https://example.com", "user_id": "u1"})
    assert r.status_code == 201
    code = r.get_json()["short_code"]

    r2 = client.get("/", query_string={"short": code})

    assert r2.status_code in (301, 302)

    r3 = client.get("/stats/", query_string={"short": code})
    assert r3.status_code == 200
    data = r3.get_json()
    assert data["clicks"] >= 1
