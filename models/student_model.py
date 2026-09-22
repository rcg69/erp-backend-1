class Student:
    def __init__(
        self,
        name: str,
        roll_number: str,
        admission_date: str,
        parent_name: str | None = None,
        mobile_number: str | None = None,
        status: str = "active"
    ):
        self.name = name
        self.roll_number = roll_number
        self.admission_date = admission_date
        self.parent_name = parent_name
        self.mobile_number = mobile_number
        self.status = status