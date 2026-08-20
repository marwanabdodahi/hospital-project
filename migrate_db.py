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


def rebuild_tables(db):
    """Recreate users and appointments with the current constraints.

    SQLAlchemy's create_all() only creates tables that do not exist yet - it
    never alters one. A database from an earlier version therefore still has
    appointments pointing at the old doctors and patients tables, and inserting
    a row fails once foreign keys are enforced. SQLite cannot change a foreign
    key in place, so the table is rebuilt and the rows copied across.
    """
    current = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='appointments'"
    ).fetchone()
    if current and "REFERENCES users" in current[0]:
        print("  tables already rebuilt - skipping")
        return

    print("  rebuilding users and appointments with the current schema")
    db.execute("PRAGMA foreign_keys=OFF")

    db.execute("""
        CREATE TABLE users_new (
            id INTEGER NOT NULL PRIMARY KEY,
            username VARCHAR NOT NULL UNIQUE,
            email VARCHAR NOT NULL UNIQUE,
            password VARCHAR NOT NULL,
            role VARCHAR NOT NULL DEFAULT 'patient'
        )
    """)
    db.execute("INSERT INTO users_new SELECT id, username, email, password, role FROM users")
    db.execute("DROP TABLE users")
    db.execute("ALTER TABLE users_new RENAME TO users")

    db.execute("""
        CREATE TABLE appointments_new (
            id INTEGER NOT NULL PRIMARY KEY,
            doctor_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            patient_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'Scheduled'
        )
    """)
    # Only rows whose doctor and patient both still exist can satisfy the new keys.
    db.execute("""
        INSERT INTO appointments_new
        SELECT a.id, a.doctor_id, a.patient_id, a.start_time, a.end_time,
               COALESCE(a.status, 'Scheduled')
        FROM appointments a
        WHERE a.doctor_id IN (SELECT id FROM users)
          AND a.patient_id IN (SELECT id FROM users)
    """)
    dropped = db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] - \
              db.execute("SELECT COUNT(*) FROM appointments_new").fetchone()[0]
    db.execute("DROP TABLE appointments")
    db.execute("ALTER TABLE appointments_new RENAME TO appointments")
    if dropped:
        print(f"  dropped {dropped} appointment(s) referencing a missing user")

    db.execute("CREATE INDEX ix_users_username ON users (username)")
    db.execute("CREATE INDEX ix_appointments_doctor_window "
               "ON appointments (doctor_id, start_time, end_time)")
    db.execute("CREATE INDEX ix_appointments_patient ON appointments (patient_id)")

    db.execute("PRAGMA foreign_keys=ON")


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

    rebuild_tables(db)

    db.commit()
    db.close()

    print(f"\nHashed {hashed} password(s), skipped {skipped} already hashed.")
    print(f"Fixed {fixed_roles} role(s) and {fixed_names} username(s).")
    print(f"Removed {orphans} appointment(s) pointing at a deleted user.")
    if hashed:
        print("Write the old passwords down - they cannot be read back out.")


if __name__ == "__main__":
    main()
