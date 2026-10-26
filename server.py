from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from exceptions.handlers import register_exception_handlers
from middleware.request_id import RequestIDMiddleware
from api.scheduling_api import router as scheduling_router
from api.attendance_api import router as attendance_router
from api.auth_api import router as auth_router
from api.class_roster_api import router as class_roster_router
from api.grade_api import router as grade_router
from api.roles_api import router as roles_router
from api.sections_api import router as sections_router
from api.staff_api import router as staff_router
from api.student_api import router as student_router
from api.user_api import router as user_create_router
from api.user_details_api import router as user_details_router
from api.user_image_api import router as user_image_router
from database import ensure_database_schema
from api.subject_api import router as subject_router
from api.exam_api import router as exam_router
app = FastAPI(
    title="Student ERP API"
)
register_exception_handlers(app)
app.add_middleware(RequestIDMiddleware)


@app.on_event("startup")
def initialize_database():
    ensure_database_schema()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://erp-frontend-mark-1.vercel.app",
    ],
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
app.include_router(class_roster_router)
app.include_router(grade_router)
app.include_router(sections_router)
app.include_router(student_router)
app.include_router(staff_router)
app.include_router(user_create_router)
app.include_router(user_details_router)
app.include_router(user_image_router)
app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(subject_router)
app.include_router(exam_router)
