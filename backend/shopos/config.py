import os


def database_url() -> str:
    """Read at use time so local and hosted processes share one configuration path."""
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required for database operations")
    # Render supplies a plain PostgreSQL URL; psycopg is the selected driver.
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value
