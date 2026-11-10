import argparse
import getpass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from shopos.audit import record_event
from shopos.db import make_engine
from shopos.models import User
from shopos.security import hash_password, normalize_username


def create_first_owner(db: Session, *, username: str, display_name: str, password: str) -> User:
    # The transaction lock prevents two concurrent bootstrap commands creating separate owners.
    db.execute(text("SELECT pg_advisory_xact_lock(8146149001)"))
    if db.scalar(select(User.id).limit(1)) is not None:
        raise ValueError("Bootstrap is only allowed before the first user exists")
    user = User(username=normalize_username(username), display_name=display_name.strip(), password_hash=hash_password(password), role="owner")
    if not user.display_name or len(user.display_name) > 100:
        raise ValueError("Display name must be 1–100 characters")
    db.add(user)
    db.flush()
    record_event(db, actor_id=user.id, action="owner.bootstrap", target_type="user", target_id=user.id)
    db.commit()
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first ShopOS owner after migrations")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Owner password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match")
    engine = make_engine()
    try:
        with Session(engine) as db:
            try:
                user = create_first_owner(db, username=args.username, display_name=args.display_name, password=password)
            except ValueError as exc:
                db.rollback()
                parser.error(str(exc))
            created_username = user.username
        print(f"Owner {created_username} created")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
