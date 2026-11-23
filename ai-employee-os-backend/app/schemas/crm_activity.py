import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActivityType = Literal["call", "email", "meeting", "note", "follow_up"]


class ActivityCreate(BaseModel):
    activity_type: ActivityType
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    activity_type: ActivityType
    title: str
    description: str | None
    created_at: datetime