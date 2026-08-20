"""One-time migration for a database created by an earlier version.

Run it once, from the project folder:

    python migrate_db.py

It is safe to run again - anything already migrated is skipped.
"""
import shutil
import sqlite3
from datetime import datetime

from app.auth import hash_password
from app.db import DB_PATH

VALID_ROLES = {"patient", "doctor", "admin"}


def main():
    db_file = str(DB_PATH)
    backup = f"{db_file}.backup-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy(db_file, backup)
    print(f"Backup saved to {backup}\n")

    db = sqlite3.connect(db_file)
    rows = db.execute("SELECT id, username, password, role, email FROM users").fetchall()

    hashed = skipped = fixed_roles = fixed_names = 0

    for user_id, username, password, role, email in rows:
        if password.startswith("$2b$"):
            skipped += 1
        else:
            print(f"  {username:12} old password was: {password}")
            db.execute("UPDATE users SET password = ? WHERE id = ?",
                       (hash_password(password), user_id))
            hashed += 1

        clean_role = (role or "patient").strip().lower()
        if clean_role not in VALID_ROLES:
            clean_role = "patient"
        if clean_role != role:
            print(f"  {username:12} role {role!r} -> {clean_role!r}")
            db.execute("UPDATE users SET role = ? WHERE id = ?", (clean_role, user_id))
            fixed_roles += 1

        clean_name = (username or "").strip().lower()
        clean_email = (email or "").strip().lower()
        if clean_name != username or clean_email != email:
            print(f"  {username:12} username -> {clean_name!r}")
            db.execute("UPDATE users SET username = ?, email = ? WHERE id = ?",
                       (clean_name, clean_email, user_id))
            fixed_names += 1

    # Appointments whose doctor or patient no longer exists cannot be honoured.
    orphans = db.execute("""
        DELETE FROM appointments
        WHERE doctor_id NOT IN (SELECT id FROM users)
           OR patient_id NOT IN (SELECT id FROM users)
    """).rowcount

    # These two tables were never written to - both roles live in users.
    db.execute("DROP TABLE IF EXISTS doctors")
    db.execute("DROP TABLE IF EXISTS patients")

    # create_all() skips tables that already exist, so indexes and the unique
    # email constraint added in later versions have to be created by hand.
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_appointments_doctor_window "
               "ON appointments (doctor_id, start_time, end_time)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_appointments_patient "
               "ON appointments (patient_id)")

    db.commit()
    db.close()

    print(f"\nHashed {hashed} password(s), skipped {skipped} already hashed.")
    print(f"Fixed {fixed_roles} role(s) and {fixed_names} username(s).")
    print(f"Removed {orphans} appointment(s) pointing at a deleted user.")
    if hashed:
        print("Write the old passwords down - they cannot be read back out.")


if __name__ == "__main__":
    main()
