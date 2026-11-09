CREATE TABLE IF NOT EXISTS api_users (
    username text PRIMARY KEY CHECK (btrim(username) <> ''),
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
