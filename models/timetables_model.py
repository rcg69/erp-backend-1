from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    SmallInteger,
    Time,
    CheckConstraint,
)

from database import Base


class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, index=True)

    # Existing academic section
    section_id = Column(
        Integer,
        ForeignKey("sections.id"),
        nullable=False,
        index=True,
    )

    # Existing subject
    subject_id = Column(
        Integer,
        ForeignKey("subjects.id"),
        nullable=False,
        index=True,
    )

    # Existing staff/teacher
    staff_id = Column(
        Integer,
        ForeignKey("staff.id"),
        nullable=False,
        index=True,
    )

    # 1 = Monday ... 7 = Sunday
    day_of_week = Column(
        SmallInteger,
        nullable=False,
    )

    start_time = Column(
        Time,
        nullable=False,
    )

    end_time = Column(
        Time,
        nullable=False,
    )

    room = Column(
        String(50),
        nullable=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="active",
    )

    __table_args__ = (
        CheckConstraint(
            "day_of_week BETWEEN 1 AND 7",
            name="ck_timetable_day_of_week",
        ),
        CheckConstraint(
            "start_time < end_time",
            name="ck_timetable_time_range",
        ),
    )