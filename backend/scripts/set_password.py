"""Set (or change) a staff member's password. Run it from the backend folder:

    python -m scripts.set_password ama@station.com

It asks for the new password twice (nothing is shown while you type) and stores only a secure hash.
Use it to replace the demo passwords (demo123 / staff123) before real people use the system.
"""
import getpass
import sys

import psycopg

from app import config
from app.security import hash_password
from app.services import audit


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.set_password <staff email>")
        return 1
    email = sys.argv[1].strip().lower()
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat the new password: "):
        print("The two passwords are not the same. Nothing was changed.")
        return 1
    if not 8 <= len(password) <= 72:
        print("The password must be 8 to 72 characters long. Nothing was changed.")
        return 1
    with psycopg.connect(config.DATABASE_URL) as conn:
        row = conn.execute(
            "UPDATE staff SET password_hash = %s WHERE lower(email) = %s RETURNING staff_id",
            (hash_password(password), email),
        ).fetchone()
        if not row:
            print(f"No staff account has the email {email}. Nothing was changed.")
            return 1
        audit(conn, row[0], "PASSWORD_CHANGED", "staff", row[0])
    print(f"Password changed for {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
