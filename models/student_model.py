class Student:
    def __init__(
        self,
        name: str,
        roll_number: str,
        admission_date: str,
        status: str = "active"
    ):
        self.name = name
        self.roll_number = roll_number
        self.admission_date = admission_date
        self.status = status