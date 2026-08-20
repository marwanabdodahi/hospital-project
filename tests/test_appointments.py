"""Booking rules, double-booking prevention and role separation."""

SLOT = {"start_time": "2026-09-01T10:00:00", "end_time": "2026-09-01T11:00:00"}


def book(client, headers, doctor_id, **overrides):
    return client.post(
        "/appointments", headers=headers, json={"doctor_id": doctor_id, **SLOT, **overrides}
    )


def test_patient_can_book(client, make_user):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    assert book(client, patient, doctor_id).status_code == 201


def test_double_booking_is_rejected(client, make_user):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    assert book(client, p1, doctor_id).status_code == 201
    r = book(client, p2, doctor_id)
    assert r.status_code == 400
    assert "already booked" in r.json()["detail"]


def test_overlapping_booking_is_rejected(client, make_user):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    book(client, p1, doctor_id)
    r = book(client, p2, doctor_id,
             start_time="2026-09-01T10:30:00", end_time="2026-09-01T11:30:00")
    assert r.status_code == 400


def test_adjacent_booking_is_allowed(client, make_user):
    """10:00-11:00 and 11:00-12:00 do not overlap."""
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    book(client, p1, doctor_id)
    r = book(client, p2, doctor_id,
             start_time="2026-09-01T11:00:00", end_time="2026-09-01T12:00:00")
    assert r.status_code == 201


def test_cancelled_slot_can_be_rebooked(client, make_user):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, p1, doctor_id).json()["id"]
    assert client.delete(f"/appointments/{appt_id}", headers=p1).status_code == 200
    assert book(client, p2, doctor_id).status_code == 201


def test_end_time_must_be_after_start_time(client, make_user):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    r = book(client, patient, doctor_id,
             start_time="2026-09-01T11:00:00", end_time="2026-09-01T10:00:00")
    assert r.status_code == 422


def test_booking_an_unknown_doctor_fails(client, make_user):
    patient, _ = make_user("p1")
    assert book(client, patient, 999).status_code == 404


def test_doctor_cannot_book(client, make_user):
    doctor, _ = make_user("d1", role="doctor")
    _, other_doctor = make_user("d2", role="doctor")
    assert book(client, doctor, other_doctor).status_code == 403


def test_patient_cannot_cancel_someone_elses_appointment(client, make_user):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, p1, doctor_id).json()["id"]
    assert client.delete(f"/appointments/{appt_id}", headers=p2).status_code == 403


def test_doctor_updates_status(client, make_user):
    patient, _ = make_user("p1")
    doctor, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, patient, doctor_id).json()["id"]
    r = client.put(f"/appointments/{appt_id}/status", headers=doctor,
                   json={"status": "Completed"})
    assert r.status_code == 200


def test_invalid_status_is_rejected(client, make_user):
    patient, _ = make_user("p1")
    doctor, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, patient, doctor_id).json()["id"]
    r = client.put(f"/appointments/{appt_id}/status", headers=doctor,
                   json={"status": "Whatever"})
    assert r.status_code == 422


def test_doctor_cannot_touch_another_doctors_appointment(client, make_user):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")
    other, _ = make_user("d2", role="doctor")

    appt_id = book(client, patient, doctor_id).json()["id"]
    r = client.put(f"/appointments/{appt_id}/status", headers=other,
                   json={"status": "Completed"})
    assert r.status_code == 403
