"""Booking rules, double-booking prevention and the appointment lifecycle."""


def book(client, headers, doctor_id, when, **overrides):
    return client.post(
        "/appointments", headers=headers, json={"doctor_id": doctor_id, **when, **overrides}
    )


def test_patient_can_book(client, make_user, slot):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    assert book(client, patient, doctor_id, slot()).status_code == 201


def test_double_booking_is_rejected(client, make_user, slot):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    assert book(client, p1, doctor_id, slot()).status_code == 201
    r = book(client, p2, doctor_id, slot())
    assert r.status_code == 400
    assert "already booked" in r.json()["detail"]


def test_overlapping_booking_is_rejected(client, make_user, slot):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    book(client, p1, doctor_id, slot(hours=2))
    assert book(client, p2, doctor_id, slot(hour_offset=1)).status_code == 400


def test_adjacent_booking_is_allowed(client, make_user, slot):
    """09:00-10:00 and 10:00-11:00 do not overlap."""
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    book(client, p1, doctor_id, slot())
    assert book(client, p2, doctor_id, slot(hour_offset=1)).status_code == 201


def test_two_doctors_can_share_a_slot(client, make_user, slot):
    p1, _ = make_user("p1")
    _, d1 = make_user("d1", role="doctor")
    _, d2 = make_user("d2", role="doctor")

    assert book(client, p1, d1, slot()).status_code == 201
    assert book(client, p1, d2, slot()).status_code == 201


def test_cancelled_slot_can_be_rebooked(client, make_user, slot):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, p1, doctor_id, slot()).json()["id"]
    assert client.delete(f"/appointments/{appt_id}", headers=p1).status_code == 200
    assert book(client, p2, doctor_id, slot()).status_code == 201


def test_restoring_a_cancelled_appointment_cannot_double_book(client, make_user, slot):
    """Reviving a cancelled appointment must not put two patients in one slot."""
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    doctor, doctor_id = make_user("d1", role="doctor")

    first = book(client, p1, doctor_id, slot()).json()["id"]
    client.delete(f"/appointments/{first}", headers=p1)
    assert book(client, p2, doctor_id, slot()).status_code == 201

    r = client.put(f"/appointments/{first}/status", headers=doctor,
                   json={"status": "Scheduled"})
    assert r.status_code == 400
    assert "since been booked" in r.json()["detail"]


def test_restoring_is_allowed_when_the_slot_is_still_free(client, make_user, slot):
    p1, _ = make_user("p1")
    doctor, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, p1, doctor_id, slot()).json()["id"]
    client.delete(f"/appointments/{appt_id}", headers=p1)

    r = client.put(f"/appointments/{appt_id}/status", headers=doctor,
                   json={"status": "Scheduled"})
    assert r.status_code == 200


def test_end_time_must_be_after_start_time(client, make_user, slot):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    s = slot()
    r = book(client, patient, doctor_id,
             {"start_time": s["end_time"], "end_time": s["start_time"]})
    assert r.status_code == 422


def test_booking_in_the_past_is_rejected(client, make_user):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    r = book(client, patient, doctor_id,
             {"start_time": "2020-01-01T10:00:00", "end_time": "2020-01-01T11:00:00"})
    assert r.status_code == 422
    assert "past" in str(r.json()["detail"])


def test_an_overlong_appointment_is_rejected(client, make_user, slot):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    r = book(client, patient, doctor_id, slot(hours=30 * 24))
    assert r.status_code == 422
    assert "longer than" in str(r.json()["detail"])


def test_booking_an_unknown_doctor_fails(client, make_user, slot):
    patient, _ = make_user("p1")
    assert book(client, patient, 999, slot()).status_code == 404


def test_cannot_book_a_patient_as_the_doctor(client, make_user, slot):
    patient, patient_id = make_user("p1")
    make_user("d1", role="doctor")
    assert book(client, patient, patient_id, slot()).status_code == 404


def test_doctor_cannot_book(client, make_user, slot):
    doctor, _ = make_user("d1", role="doctor")
    _, other_doctor = make_user("d2", role="doctor")
    assert book(client, doctor, other_doctor, slot()).status_code == 403


def test_patient_cannot_cancel_someone_elses_appointment(client, make_user, slot):
    p1, _ = make_user("p1")
    p2, _ = make_user("p2")
    _, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, p1, doctor_id, slot()).json()["id"]
    assert client.delete(f"/appointments/{appt_id}", headers=p2).status_code == 403


def test_doctor_and_admin_can_cancel(client, make_user, slot):
    p1, _ = make_user("p1")
    doctor, doctor_id = make_user("d1", role="doctor")
    admin, _ = make_user("boss", role="admin")

    a = book(client, p1, doctor_id, slot()).json()["id"]
    assert client.delete(f"/appointments/{a}", headers=doctor).status_code == 200

    b = book(client, p1, doctor_id, slot(hour_offset=2)).json()["id"]
    assert client.delete(f"/appointments/{b}", headers=admin).status_code == 200


def test_cancelling_twice_is_rejected(client, make_user, slot):
    p1, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, p1, doctor_id, slot()).json()["id"]
    assert client.delete(f"/appointments/{appt_id}", headers=p1).status_code == 200

    r = client.delete(f"/appointments/{appt_id}", headers=p1)
    assert r.status_code == 400
    assert "already cancelled" in r.json()["detail"]


def test_doctor_updates_status(client, make_user, slot):
    patient, _ = make_user("p1")
    doctor, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, patient, doctor_id, slot()).json()["id"]
    r = client.put(f"/appointments/{appt_id}/status", headers=doctor,
                   json={"status": "Completed"})
    assert r.status_code == 200


def test_a_completed_appointment_cannot_be_cancelled(client, make_user, slot):
    patient, _ = make_user("p1")
    doctor, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, patient, doctor_id, slot()).json()["id"]
    client.put(f"/appointments/{appt_id}/status", headers=doctor,
               json={"status": "Completed"})

    r = client.delete(f"/appointments/{appt_id}", headers=patient)
    assert r.status_code == 400


def test_invalid_status_is_rejected(client, make_user, slot):
    patient, _ = make_user("p1")
    doctor, doctor_id = make_user("d1", role="doctor")

    appt_id = book(client, patient, doctor_id, slot()).json()["id"]
    r = client.put(f"/appointments/{appt_id}/status", headers=doctor,
                   json={"status": "Whatever"})
    assert r.status_code == 422


def test_doctor_cannot_touch_another_doctors_appointment(client, make_user, slot):
    patient, _ = make_user("p1")
    _, doctor_id = make_user("d1", role="doctor")
    other, _ = make_user("d2", role="doctor")

    appt_id = book(client, patient, doctor_id, slot()).json()["id"]
    r = client.put(f"/appointments/{appt_id}/status", headers=other,
                   json={"status": "Completed"})
    assert r.status_code == 403
