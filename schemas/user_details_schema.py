from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserDetailsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=150)
    gender: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    nationality: str | None = Field(default=None, max_length=100)
    mother_tongue: str | None = Field(default=None, max_length=100)
    religion: str | None = Field(default=None, max_length=100)
    caste_category: str | None = Field(default=None, max_length=100)
    aadhaar_number: str | None = Field(default=None, max_length=20)
    identification_mark_1: str | None = Field(default=None, max_length=255)
    identification_mark_2: str | None = Field(default=None, max_length=255)

    mobile_number: str | None = Field(default=None, max_length=30)
    alternate_mobile_number: str | None = Field(default=None, max_length=30)
    email_address: EmailStr | None = None

    father_name: str | None = Field(default=None, max_length=150)
    father_mobile_number: str | None = Field(default=None, max_length=30)
    father_occupation: str | None = Field(default=None, max_length=150)
    mother_name: str | None = Field(default=None, max_length=150)
    mother_mobile_number: str | None = Field(default=None, max_length=30)
    mother_occupation: str | None = Field(default=None, max_length=150)
    spouse_guardian_name: str | None = Field(default=None, max_length=150)
    spouse_guardian_mobile_number: str | None = Field(default=None, max_length=30)
    annual_family_income: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )

    present_house_flat_number: str | None = Field(default=None, max_length=100)
    present_street_locality: str | None = Field(default=None, max_length=255)
    present_village_town_city: str | None = Field(default=None, max_length=150)
    present_mandal_sub_district: str | None = Field(default=None, max_length=150)
    present_district: str | None = Field(default=None, max_length=150)
    present_state: str | None = Field(default=None, max_length=150)
    present_pin_code: str | None = Field(default=None, max_length=20)
    present_country: str | None = Field(default=None, max_length=100)

    same_as_present_address: bool = False
    permanent_house_flat_number: str | None = Field(default=None, max_length=100)
    permanent_street_locality: str | None = Field(default=None, max_length=255)
    permanent_village_town_city: str | None = Field(default=None, max_length=150)
    permanent_mandal_sub_district: str | None = Field(default=None, max_length=150)
    permanent_district: str | None = Field(default=None, max_length=150)
    permanent_state: str | None = Field(default=None, max_length=150)
    permanent_pin_code: str | None = Field(default=None, max_length=20)
    permanent_country: str | None = Field(default=None, max_length=100)


class UserDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = None
    mother_tongue: str | None = None
    religion: str | None = None
    caste_category: str | None = None
    aadhaar_number: str | None = None
    identification_mark_1: str | None = None
    identification_mark_2: str | None = None
    mobile_number: str | None = None
    alternate_mobile_number: str | None = None
    email_address: EmailStr | None = None
    father_name: str | None = None
    father_mobile_number: str | None = None
    father_occupation: str | None = None
    mother_name: str | None = None
    mother_mobile_number: str | None = None
    mother_occupation: str | None = None
    spouse_guardian_name: str | None = None
    spouse_guardian_mobile_number: str | None = None
    annual_family_income: Decimal | None = None
    present_house_flat_number: str | None = None
    present_street_locality: str | None = None
    present_village_town_city: str | None = None
    present_mandal_sub_district: str | None = None
    present_district: str | None = None
    present_state: str | None = None
    present_pin_code: str | None = None
    present_country: str | None = None
    same_as_present_address: bool
    permanent_house_flat_number: str | None = None
    permanent_street_locality: str | None = None
    permanent_village_town_city: str | None = None
    permanent_mandal_sub_district: str | None = None
    permanent_district: str | None = None
    permanent_state: str | None = None
    permanent_pin_code: str | None = None
    permanent_country: str | None = None
    updated_at: datetime
