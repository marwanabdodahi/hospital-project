"""Input normalisation and the limits that used to crash or confuse the API."""


def test_username_is_case_insensitive(client):
    """'Ahmed' and 'ahmed' must be the same account, not two."""
    assert client.post("/register", json={
        "username": "Ahmed", "email": "a@test.com", "password": "secret123",
    }).status_code == 201

    r = client.post("/register", json={
        "username": "ahmed", "email": "b@test.com", "password": "secret123",
    })
    assert r.status_code == 400
    assert "already taken" in r.json()["detail"]


def test_login_works_in_any_case(client):
    client.post("/register", json={
        "username": "Ahmed", "email": "a@test.com", "password": "secret123",
    })
    for attempt in ("ahmed", "Ahmed", "AHMED", "  ahmed  "):
        r = client.post("/login", json={"username": attempt, "password": "secret123"})
        assert r.status_code == 200, f"login failed for {attempt!r}"


def test_surrounding_spaces_are_trimmed(client, db_session):
    from app.models import User
    client.post("/register", json={
        "username": "  spaced  ", "email": "s@test.com", "password": "secret123",
    })
    assert db_session.query(User).filter(User.username == "spaced").first() is not None


def test_username_rejects_odd_characters(client):
    r = client.post("/register", json={
        "username": "bad name!", "email": "b@test.com", "password": "secret123",
    })
    assert r.status_code == 422


def test_email_must_be_unique(client):
    client.post("/register", json={
        "username": "first", "email": "same@test.com", "password": "secret123",
    })
    r = client.post("/register", json={
        "username": "second", "email": "same@test.com", "password": "secret123",
    })
    assert r.status_code == 400
    assert "Email already registered" in r.json()["detail"]


def test_email_is_lowercased(client, db_session):
    from app.models import User
    client.post("/register", json={
        "username": "caps", "email": "CAPS@Test.COM", "password": "secret123",
    })
    assert db_session.query(User).filter(User.username == "caps").first().email == "caps@test.com"


def test_long_arabic_password_is_rejected_not_crashed(client):
    """40 Arabic characters are 80 bytes, past bcrypt's 72-byte limit.
    That used to raise ValueError and return 500."""
    r = client.post("/register", json={
        "username": "arabicpw", "email": "ar@test.com", "password": "كلمة" * 10,
    })
    assert r.status_code == 422
    assert "too long" in str(r.json()["detail"])


def test_a_password_at_the_byte_limit_works(client):
    r = client.post("/register", json={
        "username": "limitpw", "email": "lim@test.com", "password": "a" * 72,
    })
    assert r.status_code == 201
    assert client.post("/login", json={
        "username": "limitpw", "password": "a" * 72,
    }).status_code == 200


def test_swagger_default_timestamps_do_not_crash(client, make_user):
    """The example Swagger generates ends in Z, which Pydantic parses as a
    timezone-aware value. Comparing that to datetime.now() used to raise
    TypeError and return 500."""
    from datetime import datetime, timedelta

    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")
    start = (datetime.now() + timedelta(days=2)).replace(microsecond=0)

    r = client.post("/appointments", headers=patient, json={
        "doctor_id": doctor_id,
        "start_time": start.isoformat() + "Z",
        "end_time": (start + timedelta(hours=1)).isoformat() + "Z",
    })
    assert r.status_code in (201, 422), r.text
    assert r.status_code != 500


def test_a_timezone_offset_is_accepted(client, make_user):
    from datetime import datetime, timedelta

    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")
    start = (datetime.now() + timedelta(days=3)).replace(microsecond=0)

    r = client.post("/appointments", headers=patient, json={
        "doctor_id": doctor_id,
        "start_time": start.isoformat() + "+02:00",
        "end_time": (start + timedelta(hours=1)).isoformat() + "+02:00",
    })
    assert r.status_code != 500
