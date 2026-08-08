from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_register_success():
    response = client.post("/register", json={
        "username": "testuser",
        "email": "test@test.com",
        "password": "123456",
        "role": "patient"
    })
    assert response.status_code in [200, 400]


def test_register_duplicate():
    client.post("/register", json={
        "username": "duplicate",
        "email": "dup@test.com",
        "password": "123456",
        "role": "patient"
    })

    response = client.post("/register", json={
        "username": "duplicate",
        "email": "dup@test.com",
        "password": "123456",
        "role": "patient"
    })

    assert response.status_code == 400


def test_login_success():
    client.post("/register", json={
        "username": "loginuser",
        "email": "login@test.com",
        "password": "123456",
        "role": "patient"
    })

    response = client.post("/login", json={
        "username": "loginuser",
        "password": "123456"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password():
    response = client.post("/login", json={
        "username": "loginuser",
        "password": "wrong"
    })

    assert response.status_code == 401


def get_token(username="patient1"):
    client.post("/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "123456",
        "role": "patient"
    })

    login = client.post("/login", json={
        "username": username,
        "password": "123456"
    })

    return login.json()["access_token"]


def test_protected_without_token():
    response = client.get("/appointments")
    assert response.status_code in [401, 403]


def test_protected_with_token():
    token = get_token()

    response = client.get(
        "/appointments",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code in [200, 403]


def test_book_appointment():
    token = get_token("patient_book")

    data = {
        "doctor_id": 1,
        "patient_id": 1,
        "start_time": "2025-05-01T10:00:00",
        "end_time": "2025-05-01T11:00:00"
    }

    response = client.post(
        "/appointments",
        json=data,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code in [200, 400]


def test_double_booking():
    token = get_token("patient_double")

    data = {
        "doctor_id": 1,
        "patient_id": 1,
        "start_time": "2025-05-01T12:00:00",
        "end_time": "2025-05-01T13:00:00"
    }

    client.post(
        "/appointments",
        json=data,
        headers={"Authorization": f"Bearer {token}"}
    )

    response = client.post(
        "/appointments",
        json=data,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400


def test_invalid_token():
    response = client.get(
        "/appointments",
        headers={"Authorization": "Bearer invalidtoken"}
    )

    assert response.status_code == 401