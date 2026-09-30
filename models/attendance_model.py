from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    CheckConstraint,
    UniqueConstraint,
)

from database import Base


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Actual class session
    session_id = Column(
        Integer,
        ForeignKey("class_sessions.id"),
        nullable=False,
        index=True,
    )

    # Existing student
    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )

    status = Column(
        String(10),
        nullable=False,
    )

    remarks = Column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PRESENT', 'ABSENT', 'LATE', 'EXCUSED')",
            name="ck_attendance_status",
        ),
        UniqueConstraint(
            "session_id",
            "student_id",
            name="uq_session_student_attendance",
        ),
    )