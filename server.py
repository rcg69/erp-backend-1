from fastapi import FastAPI


from api.student_api import router as student_router
from api.user_create_api import router as user_create_router
from api.auth_api import router as auth_router
app = FastAPI(
    title="Student ERP API"
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