from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Category(str, Enum):
    ACADEMIC = "学术科技"
    ARTS_SPORTS = "文艺体育"
    VOLUNTEER = "志愿公益"
    PRACTICE = "实践交流"
    OTHER = "其他"


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ActivityInput(InputModel):
    title: Annotated[str, Field(min_length=1, max_length=100)]
    club_name: Annotated[str, Field(min_length=1, max_length=100)]
    category: Category
    location: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(min_length=1, max_length=5000)]
    capacity: Annotated[int, Field(strict=True, ge=1, le=100000)]
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    registration_deadline: AwareDatetime

    @field_validator("starts_at", "ends_at", "registration_deadline", mode="before")
    @classmethod
    def require_datetime_string(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("时间必须是带时区的 ISO 8601 字符串。")
        return value

    @field_validator("starts_at", "ends_at", "registration_deadline")
    @classmethod
    def normalize_time(cls, value: datetime):
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("结束时间必须晚于开始时间。")
        if self.registration_deadline > self.starts_at:
            raise ValueError("报名截止时间不能晚于活动开始时间。")
        return self


class RegistrationInput(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=50)]
    student_id: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]
    contact: Annotated[str, Field(min_length=1, max_length=100)]

    @field_validator("student_id")
    @classmethod
    def normalize_student_id(cls, value: str):
        return value.upper()


class ActivityOut(ActivityInput):
    id: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    registration_count: int
    remaining_capacity: int
    registration_status: str


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    page: int
    page_size: int


class RegistrationOut(RegistrationInput):
    id: int
    activity_id: int
    created_at: AwareDatetime


class RegistrationPage(BaseModel):
    items: list[RegistrationOut]
    total: int
    page: int
    page_size: int


class ActivityStat(BaseModel):
    activity_id: int
    title: str
    capacity: int
    registration_count: int
    remaining_capacity: int


class StatsOut(BaseModel):
    activity_count: int
    registration_count: int
    unique_student_count: int
    activities: list[ActivityStat]
