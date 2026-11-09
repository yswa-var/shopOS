"""Create or disable API users without a public signup endpoint."""

import argparse
import getpass

import psycopg

from auth import password_hash
from database import DatabaseSettings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("add", "disable"))
    parser.add_argument("username")
    args = parser.parse_args()
    username = args.username.strip()
    if not username:
        parser.error("username must not be empty")
    settings = DatabaseSettings.from_env()
    if args.action == "add":
        password = getpass.getpass("Password: ")
        if len(password) < 12:
            parser.error("password must be at least 12 characters")
        hashed = password_hash.hash(password)
    with psycopg.connect(
        host=settings.host, port=settings.port, dbname=settings.name,
        user=settings.user, password=settings.password,
    ) as connection:
        with connection.cursor() as cursor:
            if args.action == "add":
                cursor.execute(
                    """INSERT INTO api_users (username, password_hash, is_active)
                       VALUES (%s, %s, true)
                       ON CONFLICT (username) DO UPDATE
                       SET password_hash = EXCLUDED.password_hash, is_active = true""",
                    (username, hashed),
                )
            else:
                cursor.execute(
                    "UPDATE api_users SET is_active = false WHERE username = %s",
                    (username,),
                )
                if cursor.rowcount == 0:
                    parser.error("user not found")
    print(f"User {username} {args.action} complete")


if __name__ == "__main__":
    main()
