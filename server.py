from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import ensure_auth_tables
from api.student_api import router as student_router
from api.user_create_api import router as user_create_router
from api.auth_api import router as auth_router
from api.roles_api import router as roles_router
app = FastAPI(
    title="Student ERP API"
)


@app.on_event("startup")
def initialize_database():
    ensure_auth_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "API is running"
    }


app.include_router(student_router)
app.include_router(user_create_router)
app.include_router(auth_router)
app.include_router(roles_router)