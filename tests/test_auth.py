"""Registration, login and token handling."""


def test_register_creates_a_patient(client):
    r = client.post("/register", json={
        "username": "newpatient", "email": "new@test.com",
        "password": "secret123", "role": "patient",
    })
    assert r.status_code == 201


def test_register_rejects_duplicate_username(client):
    body = {"username": "taken", "email": "a@test.com", "password": "secret123"}
    assert client.post("/register", json=body).status_code == 201

    r = client.post("/register", json=body)
    assert r.status_code == 400
    assert "already taken" in r.json()["detail"]


def test_register_rejects_bad_email(client):
    r = client.post("/register", json={
        "username": "bademail", "email": "not-an-email", "password": "secret123",
    })
    assert r.status_code == 422


def test_register_rejects_short_password(client):
    r = client.post("/register", json={
        "username": "shortpw", "email": "s@test.com", "password": "123",
    })
    assert r.status_code == 422


def test_register_cannot_grant_admin(client, make_user):
    """A public sign-up asking for admin must still come out as a patient."""
    client.post("/register", json={
        "username": "sneaky", "email": "s@test.com",
        "password": "secret123", "role": "admin",
    })
    token = client.post("/login", json={
        "username": "sneaky", "password": "secret123",
    }).json()["access_token"]

    r = client.get("/patients", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_password_is_not_stored_in_plain_text(client, db_session):
    from app.models import User
    client.post("/register", json={
        "username": "hashed", "email": "h@test.com", "password": "secret123",
    })
    stored = db_session.query(User).filter(User.username == "hashed").first().password
    assert stored != "secret123"
    assert stored.startswith("$2b$")


def test_login_returns_a_token(client, make_user):
    headers, _ = make_user("loginuser")
    assert headers["Authorization"].startswith("Bearer ey")


def test_login_rejects_wrong_password(client, make_user):
    make_user("realuser", password="secret123")
    r = client.post("/login", json={"username": "realuser", "password": "wrong"})
    assert r.status_code == 401


def test_login_rejects_empty_password(client, make_user):
    make_user("realuser2", password="secret123")
    r = client.post("/login", json={"username": "realuser2", "password": ""})
    assert r.status_code == 401


def test_login_rejects_unknown_user(client):
    r = client.post("/login", json={"username": "ghost", "password": "secret123"})
    assert r.status_code == 401


def test_protected_route_needs_a_token(client):
    assert client.get("/appointments").status_code in (401, 403)


def test_invalid_token_is_rejected(client):
    r = client.get("/appointments", headers={"Authorization": "Bearer notatoken"})
    assert r.status_code == 401
