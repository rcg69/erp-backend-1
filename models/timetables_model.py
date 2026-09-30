from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Time,
    CheckConstraint,
    UniqueConstraint,
)

from database import Base


class Timetable(Base):
    """
    One recurring weekly slot (day + period) for a class + section.

    Opening a timetable creates a 6 x 6 grid of these rows
    (Monday-Saturday x Period 1-6). The weekly subject/staff
    assignment lives in default_subject_id / default_staff_id.
    Dated ClassSession rows are generated from those defaults.
    """

    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, index=True)

    # The academic section (A, B, ...).
    section_id = Column(
        Integer,
        ForeignKey("sections.id"),
        nullable=False,
        index=True,
    )

    # The class + academic year (a row of the grades table).
    # Nullable so legacy rows created before the grid still load.
    grade_id = Column(
        Integer,
        ForeignKey("grades.id"),
        nullable=True,
        index=True,
    )

    # 1 = Monday ... 7 = Sunday
    day_of_week = Column(
        SmallInteger,
        nullable=False,
    )

    # 1 ... 6 for the standard grid
    period_number = Column(
        SmallInteger,
        nullable=True,
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

    # Weekly assignment for this slot. Copied into class_sessions
    # when sessions are generated. NOT named subject_id / staff_id:
    # database.py drops those two column names from timetables.
    default_subject_id = Column(
        Integer,
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
    )

    default_staff_id = Column(
        Integer,
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Academic year date range this grid runs for.
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "day_of_week BETWEEN 1 AND 7",
            name="ck_timetable_day_of_week",
        ),
        CheckConstraint(
            "start_time < end_time",
            name="ck_timetable_time_range",
        ),
        CheckConstraint(
            "period_number IS NULL OR period_number BETWEEN 1 AND 12",
            name="ck_timetable_period_number",
        ),
        UniqueConstraint(
            "grade_id",
            "section_id",
            "day_of_week",
            "period_number",
            name="uq_timetable_grade_section_day_period",
        ),
    )