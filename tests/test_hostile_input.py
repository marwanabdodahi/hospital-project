"""Inputs that a careless or hostile caller can send. None may return 5xx."""
import pytest


def test_an_oversized_id_is_rejected_not_crashed(client, make_user):
    """SQLite binds a 64-bit integer; anything larger raised OverflowError."""
    admin, _ = make_user("boss", role="admin")
    r = client.get("/patients/99999999999999999999", headers=admin)
    assert r.status_code == 422


def test_a_negative_id_is_rejected(client, make_user):
    admin, _ = make_user("boss", role="admin")
    assert client.get("/patients/-1", headers=admin).status_code == 422


def test_a_non_numeric_id_is_rejected(client, make_user):
    admin, _ = make_user("boss", role="admin")
    assert client.get("/patients/abc", headers=admin).status_code == 422


def test_admin_cannot_delete_their_own_account(client, make_user):
    admin, admin_id = make_user("boss", role="admin")
    r = client.delete(f"/admin/users/{admin_id}", headers=admin)
    assert r.status_code == 400
    assert "your own account" in r.json()["detail"]


def test_the_last_administrator_cannot_be_deleted(client, make_user):
    first, first_id = make_user("boss", role="admin")
    second, _ = make_user("boss2", role="admin")

    r = client.delete(f"/admin/users/{first_id}", headers=second)
    assert r.status_code == 200  # two admins exist, so one may go

    r = client.delete(f"/admin/users/{first_id}", headers=second)
    assert r.status_code == 404


def test_unknown_fields_are_rejected(client, make_user, slot):
    """Sending patient_id used to be silently ignored; it now fails loudly."""
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    r = client.post("/appointments", headers=patient,
                    json={"doctor_id": doctor_id, **slot(), "patient_id": 99, "status": "Completed"})
    assert r.status_code == 422


def test_booking_too_far_ahead_is_rejected(client, make_user):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    r = client.post("/appointments", headers=patient, json={
        "doctor_id": doctor_id,
        "start_time": "9999-12-31T23:00:00",
        "end_time": "9999-12-31T23:30:00",
    })
    assert r.status_code == 422
    assert "days ahead" in str(r.json()["detail"])


@pytest.mark.parametrize("payload", [
    {"username": "' OR '1'='1", "password": "x"},
    {"username": "a'; DROP TABLE users;--", "password": "x"},
])
def test_sql_injection_in_login_is_just_a_failed_login(client, payload, db_session):
    from app.models import User
    assert client.post("/login", json=payload).status_code == 401
    assert db_session.query(User).count() == 0  # the table is still there


def test_malformed_json_is_rejected(client, make_user):
    patient, _ = make_user("p1")
    r = client.post(
        "/appointments",
        headers={**patient, "Content-Type": "application/json"},
        content=b'{"doctor_id":',
    )
    assert r.status_code == 422
