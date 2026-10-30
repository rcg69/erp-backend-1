# Student ERP API

A backend API for an educational management application. The service exposes endpoints for authentication, user and role management, students, staff, class rosters, attendance, examinations, grades, subjects, sections, and timetable/class-session scheduling.

**Frontend:** https://erp-frontend-mark-1.vercel.app/login

## Features

- FastAPI application with modular routers
- PostgreSQL persistence through SQLAlchemy
- JWT access-token authentication
- Refresh-token flow using an HTTP-only cookie
- Role-aware authorization for administrator, staff/teacher, and student operations
- Student and staff records, user details, and profile-image APIs
- Class roster and section management
- Attendance records and attendance reports
- Examination and grade management
- Timetable and class-session scheduling
- Request ID middleware and centralized exception handlers
- Automated tests covering API security, attendance, roster, examinations, database bootstrap, and user details/images

## Technology

- Python
- FastAPI and Pydantic
- SQLAlchemy
- PostgreSQL and psycopg2
- PyJWT
- Uvicorn
- unittest-based test suite

## Architecture

```text
.
├── api/          # FastAPI routers and HTTP endpoints
├── exceptions/   # Centralized exception handlers
├── middleware/   # Request middleware
├── models/       # Database models and persistence operations
├── schemas/      # Request and response schemas
├── security/     # Authentication and role-based access checks
├── services/     # Business logic
├── tests/        # Automated tests
├── utils/        # Shared utilities, including JWT helpers
├── database.py   # Database configuration and schema bootstrap
└── server.py     # FastAPI application entry point
```

## Run locally

### Prerequisites

- Python 3.10 or newer
- PostgreSQL
- pip

Create a PostgreSQL database, then clone and install the project:

```bash
git clone https://github.com/rcg69/erp-backend-1.git
cd erp-backend-1

python -m venv .venv
```

Activate the virtual environment:

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

Install dependencies and configure environment variables:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set values for your local PostgreSQL database and a unique JWT secret. Do not commit `.env` or production credentials.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL |
| `JWT_SECRET_KEY` | Unique JWT signing secret |
| `JWT_ALGORITHM` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime |
| `ENVIRONMENT` | Runtime environment |
| `JWT_COOKIE_SECURE` | Secure-cookie setting |
| `JWT_COOKIE_SAMESITE` | SameSite cookie policy |

Start the development server:

```bash
uvicorn server:app --reload
```

The API is available at http://127.0.0.1:8000. Interactive API documentation is available at http://127.0.0.1:8000/docs.

## Run tests

```bash
python -m unittest discover -s tests
```

## Authentication

The authentication router provides:

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`

Protected endpoints use bearer access tokens. The refresh endpoint reads the refresh token from the configured cookie.

## Notes

- Configure CORS origins for the frontend environment you intend to use.
- Use a strong, unique JWT secret and secure cookie settings in production.
- Review role guards before exposing new endpoints.
- This README describes the checked-in implementation; deployment status and production readiness should be verified separately.
