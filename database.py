import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
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


def ensure_database_schema() -> None:
    """Create any missing database tables and essential default seed data."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    legacy_section_columns = set()

    if "sections" in existing_tables:
        legacy_section_columns = {
            column["name"]
            for column in inspector.get_columns("sections")
        }

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    role_id SERIAL PRIMARY KEY,
                    role_name VARCHAR(50) NOT NULL UNIQUE
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    roll_number VARCHAR(50) NOT NULL UNIQUE,
                    admission_date DATE NOT NULL,
                    parent_name VARCHAR(150),
                    mobile_number VARCHAR(30),
                    grade VARCHAR(20),
                    section VARCHAR(20),
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    person_id INTEGER,
                    role_id INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE RESTRICT,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS grades (
                    id SERIAL PRIMARY KEY,
                    academic_year VARCHAR(20) NOT NULL,
                    grade VARCHAR(20) NOT NULL,
                    section_id INTEGER NULL,
                    staff_id INTEGER NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    CONSTRAINT uq_academic_year_grade UNIQUE (academic_year, grade)
                )
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE grades
                ADD COLUMN IF NOT EXISTS section_id INTEGER
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE grades
                ADD COLUMN IF NOT EXISTS staff_id INTEGER
                """
            )
        )

        if "sections" in existing_tables:
            connection.execute(
                text(
                    """
                    ALTER TABLE sections
                    DROP COLUMN IF EXISTS staff_id
                    """
                )
            )

        if "sections" in existing_tables and {"grade", "academic_year"}.issubset(legacy_section_columns):
            connection.execute(
                text(
                    """
                    INSERT INTO grades (academic_year, grade, section_id, staff_id, status)
                    SELECT DISTINCT s.academic_year, s.grade, NULL, CAST(NULL AS INTEGER), 'active'
                    FROM sections s
                    ON CONFLICT (academic_year, grade) DO NOTHING
                    """
                )
            )

            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sections_new (
                        id SERIAL PRIMARY KEY,
                        section VARCHAR(10) NOT NULL UNIQUE
                    )
                    """
                )
            )

            connection.execute(
                text(
                    """
                    INSERT INTO sections_new (section)
                    SELECT DISTINCT section
                    FROM sections
                    ON CONFLICT (section) DO NOTHING
                    """
                )
            )

            connection.execute(text("DROP TABLE sections"))
            connection.execute(text("ALTER TABLE sections_new RENAME TO sections"))
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sections (
                        id SERIAL PRIMARY KEY,
                        section VARCHAR(10) NOT NULL UNIQUE
                    )
                    """
                )
            )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS staff (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    number VARCHAR(30) NOT NULL UNIQUE,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

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

        connection.execute(
            text(
                "ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_name VARCHAR(150)"
            )
        )

        connection.execute(
            text(
                "ALTER TABLE students ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(30)"
            )
        )

        connection.execute(
            text(
                "ALTER TABLE students ADD COLUMN IF NOT EXISTS grade VARCHAR(20)"
            )
        )

        connection.execute(
            text(
                "ALTER TABLE students ADD COLUMN IF NOT EXISTS section VARCHAR(20)"
            )
        )

        connection.execute(
            text("ALTER TABLE students DROP COLUMN IF EXISTS user_id")
        )

        connection.execute(
            text(
                """
                INSERT INTO roles (role_name)
                VALUES ('admin'), ('staff'), ('student'), ('parent')
                ON CONFLICT (role_name) DO NOTHING
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS access_logs (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER,
                    action VARCHAR(100) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def ensure_auth_tables() -> None:
    ensure_database_schema()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()