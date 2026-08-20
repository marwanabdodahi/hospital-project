"""One-time migration for a database created before passwords were hashed.

Run it once, from the project folder:

    python migrate_db.py

It is safe to run again - accounts that are already hashed are skipped.
"""
import shutil
import sqlite3
from datetime import datetime

from app.auth import hash_password

DB = "hospital.db"
VALID_ROLES = {"patient", "doctor", "admin"}


def main():
    backup = f"hospital.db.backup-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy(DB, backup)
    print(f"Backup saved to {backup}\n")

    db = sqlite3.connect(DB)
    rows = db.execute("SELECT id, username, password, role FROM users").fetchall()

    hashed = skipped = fixed_roles = 0

    for user_id, username, password, role in rows:
        if password.startswith("$2b$"):
            skipped += 1
        else:
            print(f"  {username:12} old password was: {password}")
            db.execute("UPDATE users SET password = ? WHERE id = ?",
                       (hash_password(password), user_id))
            hashed += 1

        clean = (role or "patient").strip().lower()
        if clean not in VALID_ROLES:
            clean = "patient"
        if clean != role:
            print(f"  {username:12} role {role!r} -> {clean!r}")
            db.execute("UPDATE users SET role = ? WHERE id = ?", (clean, user_id))
            fixed_roles += 1

    # The doctors and patients tables were never used - appointments reference users.id.
    db.execute("DROP TABLE IF EXISTS doctors")
    db.execute("DROP TABLE IF EXISTS patients")

    db.commit()
    db.close()

    print(f"\nHashed {hashed} password(s), skipped {skipped} already hashed, "
          f"fixed {fixed_roles} role(s).")
    print("Write the old passwords down - they cannot be read back out.")


if __name__ == "__main__":
    main()
