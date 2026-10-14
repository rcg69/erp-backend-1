import unittest

from schemas.user_details_schema import UserDetailsUpdate
from services.user_details_service import PRESENT_ADDRESS_FIELDS, update_user_details


class _Result:
    def __init__(self, row=None):
        self.row = row

    def first(self):
        return self.row

    def mappings(self):
        return self


class _ProfileSession:
    def __init__(self):
        self.profile = {
            "same_as_present_address": False,
            **{f"present_{field}": None for field in PRESENT_ADDRESS_FIELDS},
            **{f"permanent_{field}": None for field in PRESENT_ADDRESS_FIELDS},
        }
        self.update_parameters = None

    def execute(self, statement, parameters=None):
        query = str(statement)
        if "SELECT id FROM users" in query:
            return _Result((1,))
        if "INSERT INTO user_details" in query:
            return _Result()
        if "SELECT" in query and "FROM user_details" in query:
            return _Result(dict(self.profile))
        if "UPDATE user_details" in query:
            self.update_parameters = parameters
            self.profile.update(
                {
                    key: value
                    for key, value in parameters.items()
                    if key != "user_id"
                }
            )
            return _Result()
        raise AssertionError(f"Unexpected query: {query}")

    def commit(self):
        pass

    def rollback(self):
        pass


class UserDetailsTests(unittest.TestCase):
    def test_profile_update_accepts_personal_contact_family_and_address_fields(self):
        details = UserDetailsUpdate.model_validate(
            {
                "full_name": "Rahul Kumar",
                "gender": "Male",
                "date_of_birth": "2008-03-12",
                "nationality": "Indian",
                "mobile_number": "9876543210",
                "father_name": "Father Kumar",
                "annual_family_income": "120000.00",
                "present_country": "India",
                "permanent_country": "India",
            }
        )

        self.assertEqual(details.full_name, "Rahul Kumar")
        self.assertEqual(details.mobile_number, "9876543210")
        self.assertEqual(details.father_name, "Father Kumar")
        self.assertEqual(details.model_dump(exclude_unset=True)["present_country"], "India")

    def test_same_present_address_copies_and_tracks_address_fields(self):
        db = _ProfileSession()
        details = UserDetailsUpdate(
            present_street_locality="Main Road",
            present_village_town_city="Hyderabad",
            same_as_present_address=True,
        )

        result = update_user_details(1, details, db)

        self.assertEqual(
            db.update_parameters["permanent_street_locality"],
            "Main Road",
        )
        self.assertEqual(
            db.update_parameters["permanent_village_town_city"],
            "Hyderabad",
        )
        self.assertTrue(result["same_as_present_address"])


if __name__ == "__main__":
    unittest.main()
