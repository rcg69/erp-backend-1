import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def ensure_auth_tables() -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_name VARCHAR(150)"))
        connection.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(30)"))
        connection.execute(text("ALTER TABLE students DROP COLUMN IF EXISTS user_id"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    expires_at TIMESTAMPTZ NOT NULL,
                    revoked BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()