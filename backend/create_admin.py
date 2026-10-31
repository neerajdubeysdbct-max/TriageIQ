"""
Create the first admin account (signup itself is admin-only).

    ADMIN_USERNAME=admin ADMIN_PASSWORD=... [ADMIN_TEAM=ops] python create_admin.py

Does nothing if the user already exists, so it is safe to run on every start.
"""

import os
import sys

from auth import get_password_hash
from models import SessionLocal, User


def main():
    username, password = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        sys.exit("Set ADMIN_USERNAME and ADMIN_PASSWORD")
    if len(password) < 8:
        sys.exit("ADMIN_PASSWORD must be at least 8 characters")
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print(f"admin '{username}' already exists")
            return
        db.add(User(username=username, email=f"{username}@localhost", role="admin",
                    team_id=os.environ.get("ADMIN_TEAM", username), hashed_password=get_password_hash(password)))
        db.commit()
        print(f"created admin '{username}'")
    finally:
        db.close()


if __name__ == "__main__":
    main()
