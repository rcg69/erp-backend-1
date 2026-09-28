from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Date,
    Boolean,
    Text,
    UniqueConstraint,
)

from database import Base


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Recurring timetable entry
    timetable_id = Column(
        Integer,
        ForeignKey("timetables.id"),
        nullable=False,
        index=True,
    )

    # Actual date on which this class was scheduled
    session_date = Column(
        Date,
        nullable=False,
    )

    # Whether the class actually took place
    is_conducted = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    remarks = Column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "timetable_id",
            "session_date",
            name="uq_timetable_session_date",
        ),
    )