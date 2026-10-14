
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlayerJoin(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)


class PlayerReady(BaseModel):
    is_ready: bool


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    display_name: str
    score: int
    joined_at: datetime
    left_at: datetime | None = None
    is_ready: bool = False


class PlayerJoinResponse(PlayerResponse):
    access_token: str
    token_type: str = "bearer"


class LobbyResponse(BaseModel):
    room_code: str
    status: str
    player_count: int
    max_players: int
    players: list[PlayerResponse]
