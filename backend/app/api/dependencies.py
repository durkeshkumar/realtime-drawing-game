
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.game_room import GameRoom
from app.models.player import Player


bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_player(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Player:
    if credentials is None:
        raise unauthorized_error()

    payload = decode_access_token(credentials.credentials)

    if not isinstance(payload, dict):
        raise unauthorized_error()

    # Accept only tokens issued for player access.
    if payload.get("token_type") != "player_access":
        raise unauthorized_error()

    player_id_claim = payload.get("sub")
    room_code_claim = payload.get("room_code")

    if not player_id_claim or not isinstance(room_code_claim, str):
        raise unauthorized_error()

    try:
        player_id = int(player_id_claim)
    except (TypeError, ValueError):
        raise unauthorized_error()

    if player_id <= 0:
        raise unauthorized_error()

    normalized_room_code = room_code_claim.strip().upper()

    if not normalized_room_code:
        raise unauthorized_error()

    player = (
        db.query(Player)
        .filter(
            Player.id == player_id,
            Player.left_at.is_(None),
        )
        .first()
    )

    if player is None:
        raise unauthorized_error()

    room = (
        db.query(GameRoom)
        .filter(GameRoom.id == player.room_id)
        .first()
    )

    if room is None or room.room_code != normalized_room_code:
        raise unauthorized_error()

    return player


def get_current_player_in_room(
    room_code: str,
    current_player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> Player:
    normalized_room_code = room_code.strip().upper()

    room = (
        db.query(GameRoom)
        .filter(GameRoom.room_code == normalized_room_code)
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    if current_player.room_id != room.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this room.",
        )

    if current_player.left_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are no longer an active player in this room.",
        )

    return current_player
