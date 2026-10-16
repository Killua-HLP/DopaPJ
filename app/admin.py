import argparse
import sys

from sqlalchemy import func

from app.database import SessionLocal
from app.models import admin_audit, anime, comment, watch_progress
from app.models.user import User


def promote_user(email: str) -> bool:
    with SessionLocal() as db:
        user = db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
        if user is None:
            print("No account exists for that email. Register it first, then retry.", file=sys.stderr)
            return False
        if user.is_admin:
            print(f"{user.email} already has administrator access.")
            return True
        user.is_admin = True
        db.commit()
        print(f"Granted administrator access to {user.email}.")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Anime Hub administrator account management.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    promote = subparsers.add_parser("promote", help="grant administrator access to an existing account")
    promote.add_argument("email", help="email address of the already-registered account")
    args = parser.parse_args()
    return 0 if promote_user(args.email) else 1


if __name__ == "__main__":
    raise SystemExit(main())
