
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoomCreate(BaseModel):
    total_rounds: int = Field(default=3, ge=1, le=10)


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_code: str
    status: str
    current_round: int
    total_rounds: int
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
