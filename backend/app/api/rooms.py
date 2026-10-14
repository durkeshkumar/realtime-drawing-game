
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.game_room import GameRoom
from app.schemas.room import RoomCreate, RoomResponse

router = APIRouter(prefix="/rooms", tags=["Rooms"])

ROOM_CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_room_code(db: Session) -> str:
    """Generate a unique, eight-character room code."""
    for _ in range(10):
        code = "".join(
            secrets.choice(ROOM_CODE_ALPHABET) for _ in range(8)
        )

        existing_room = db.scalar(
            select(GameRoom.id).where(GameRoom.room_code == code)
        )

        if existing_room is None:
            return code

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not generate a unique room code. Please try again.",
    )


@router.post(
    "",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
def create_room(
    request: Request,
    payload: RoomCreate,
    db: Session = Depends(get_db),
) -> GameRoom:
    room = GameRoom(
        room_code=generate_room_code(db),
        total_rounds=payload.total_rounds,
        current_round=0,
        status="waiting",
    )

    db.add(room)
    db.commit()
    db.refresh(room)

    return room


@router.get(
    "/{room_code}",
    response_model=RoomResponse,
)
def get_room(
    room_code: str,
    db: Session = Depends(get_db),
) -> GameRoom:
    normalized_code = room_code.strip().upper()

    room = db.scalar(
        select(GameRoom).where(
            GameRoom.room_code == normalized_code
        )
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    return room
