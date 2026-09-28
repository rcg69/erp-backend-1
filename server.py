from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.scheduling_api import router as scheduling_router
from api.attendance_api import router as attendance_router
from api.auth_api import router as auth_router
from api.grade_api import router as grade_router
from api.roles_api import router as roles_router
from api.sections_api import router as sections_router
from api.staff_api import router as staff_router
from api.student_api import router as student_router
from api.user_create_api import router as user_create_router
from database import ensure_database_schema
from api.subject_api import router as subject_router
app = FastAPI(
    title="Student ERP API"
)


@app.on_event("startup")
def initialize_database():
    ensure_database_schema()

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
app.include_router(scheduling_router)
app.include_router(attendance_router)
app.include_router(grade_router)
app.include_router(sections_router)
app.include_router(student_router)
app.include_router(staff_router)
app.include_router(user_create_router)
app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(subject_router)