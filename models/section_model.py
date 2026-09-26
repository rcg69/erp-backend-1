from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from database import Base


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    academic_year = Column(String(20), nullable=False)
    grade = Column(String(20), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    staff_id = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="active")

    __table_args__ = (
        UniqueConstraint("academic_year", "grade", name="uq_academic_year_grade"),
    )


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    section = Column(String(10), nullable=False, unique=True)
