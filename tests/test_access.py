"""Role-based access control and schedule ownership."""


def test_patient_cannot_list_all_appointments(client, make_user):
    patient, _ = make_user("p1")
    assert client.get("/appointments", headers=patient).status_code == 403


def test_admin_can_list_all_appointments(client, make_user):
    admin, _ = make_user("boss", role="admin")
    r = client.get("/appointments", headers=admin)
    assert r.status_code == 200
    assert r.json() == []


def test_patient_cannot_list_patients(client, make_user):
    patient, _ = make_user("p1")
    assert client.get("/patients", headers=patient).status_code == 403


def test_admin_sees_patients_and_doctors(client, make_user):
    admin, _ = make_user("boss", role="admin")
    make_user("p1")
    make_user("d1", role="doctor")

    assert len(client.get("/patients", headers=admin).json()) == 1
    assert len(client.get("/doctors", headers=admin).json()) == 1


def test_directory_never_exposes_passwords(client, make_user):
    admin, _ = make_user("boss", role="admin")
    make_user("p1")

    body = client.get("/patients", headers=admin).json()
    assert "password" not in body[0]


def test_doctor_sees_only_their_own_schedule(client, make_user):
    doctor, doctor_id = make_user("d1", role="doctor")
    _, other_id = make_user("d2", role="doctor")

    assert client.get(f"/doctors/{doctor_id}/appointments", headers=doctor).status_code == 200
    assert client.get(f"/doctors/{other_id}/appointments", headers=doctor).status_code == 403


def test_patient_sees_only_their_own_schedule(client, make_user):
    patient, patient_id = make_user("p1")
    _, other_id = make_user("p2")

    assert client.get(f"/patients/{patient_id}/appointments", headers=patient).status_code == 200
    assert client.get(f"/patients/{other_id}/appointments", headers=patient).status_code == 403


def test_admin_can_create_a_doctor(client, make_user):
    admin, _ = make_user("boss", role="admin")
    r = client.post("/admin/create-user", headers=admin, json={
        "username": "newdoc", "email": "nd@test.com",
        "password": "secret123", "role": "doctor",
    })
    assert r.status_code == 201
    assert len(client.get("/doctors", headers=admin).json()) == 1


def test_patient_cannot_create_users(client, make_user):
    patient, _ = make_user("p1")
    r = client.post("/admin/create-user", headers=patient, json={
        "username": "nope", "email": "n@test.com", "password": "secret123", "role": "admin",
    })
    assert r.status_code == 403


def test_admin_can_delete_a_user(client, make_user):
    admin, _ = make_user("boss", role="admin")
    _, patient_id = make_user("p1")

    assert client.delete(f"/admin/users/{patient_id}", headers=admin).status_code == 200
    assert client.delete(f"/admin/users/{patient_id}", headers=admin).status_code == 404


def test_dashboard_requires_admin(client, make_user):
    patient, _ = make_user("p1")
    admin, _ = make_user("boss", role="admin")

    assert client.get("/dashboard", headers=patient).status_code == 403

    body = client.get("/dashboard", headers=admin).json()
    assert body["total_requests"] > 0
    assert body["error_count"] >= 1  # the 403 above was counted
