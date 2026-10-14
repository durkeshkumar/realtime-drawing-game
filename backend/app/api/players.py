
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_player
from app.core.limiter import limiter
from app.core.security import create_access_token
from app.db.session import get_db
from app.game.websocket_manager import manager
from app.models.game_room import GameRoom
from app.models.player import Player
from app.schemas.player import (
    LobbyResponse,
    PlayerJoin,
    PlayerJoinResponse,
    PlayerReady,
    PlayerResponse,
)

router = APIRouter(tags=["Players"])

MAX_PLAYERS = 8


def utc_now() -> datetime:
    return datetime.utcnow()


def get_room(db: Session, room_code: str) -> GameRoom:
    room = (
        db.query(GameRoom)
        .filter(GameRoom.room_code == room_code.strip().upper())
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    return room


def get_waiting_room(db: Session, room_code: str) -> GameRoom:
    room = get_room(db, room_code)

    if room.status != "waiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This room is no longer accepting lobby changes.",
        )

    return room


def get_active_player(
    db: Session,
    room: GameRoom,
    player_id: int,
) -> Player:
    player = (
        db.query(Player)
        .filter(
            Player.id == player_id,
            Player.room_id == room.id,
            Player.left_at.is_(None),
        )
        .first()
    )

    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active player not found in this room.",
        )

    return player


def ensure_player_ownership(
    room: GameRoom,
    current_player: Player,
) -> None:
    if current_player.room_id != room.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify another player's room.",
        )


def player_event(player: Player, event_type: str) -> dict:
    return {
        "type": event_type,
        "player_id": player.id,
        "display_name": player.display_name,
        "score": player.score,
        "is_ready": player.is_ready,
    }


@router.post(
    "/rooms/{room_code}/players",
    response_model=PlayerJoinResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def join_room(
    request: Request,
    room_code: str,
    payload: PlayerJoin,
    db: Session = Depends(get_db),
):
    room = get_waiting_room(db, room_code)
    display_name = payload.display_name.strip()

    if not display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Display name cannot be empty.",
        )

    normalized_name = display_name.casefold()

    duplicate = (
        db.query(Player)
        .filter(
            Player.room_id == room.id,
            func.lower(Player.display_name) == normalized_name,
            Player.left_at.is_(None),
        )
        .first()
    )

    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That display name is already in use in this room.",
        )

    previous_player = (
        db.query(Player)
        .filter(
            Player.room_id == room.id,
            func.lower(Player.display_name) == normalized_name,
        )
        .first()
    )

    if previous_player is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This display name was previously used in this room. "
                "Choose another name."
            ),
        )

    active_count = (
        db.query(Player)
        .filter(
            Player.room_id == room.id,
            Player.left_at.is_(None),
        )
        .count()
    )

    if active_count >= MAX_PLAYERS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This room is full.",
        )

    player = Player(
        room_id=room.id,
        display_name=display_name,
        score=0,
        is_ready=False,
    )

    try:
        db.add(player)
        db.commit()
        db.refresh(player)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This display name is unavailable. Choose another name.",
        )

    access_token = create_access_token(
        subject=str(player.id),
        additional_claims={
            "room_code": room.room_code,
            "token_type": "player_access",
        },
    )

    await manager.broadcast(
        room.room_code,
        player_event(player, "player_joined"),
        exclude_player_id=player.id,
    )

    return PlayerJoinResponse(
        id=player.id,
        room_id=player.room_id,
        display_name=player.display_name,
        score=player.score,
        joined_at=player.joined_at,
        left_at=player.left_at,
        is_ready=player.is_ready,
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/rooms/{room_code}/lobby",
    response_model=LobbyResponse,
)
@limiter.limit("60/minute")
def get_lobby(
    request: Request,
    room_code: str,
    db: Session = Depends(get_db),
):
    room = get_room(db, room_code)

    players = (
        db.query(Player)
        .filter(
            Player.room_id == room.id,
            Player.left_at.is_(None),
        )
        .order_by(Player.joined_at.asc(), Player.id.asc())
        .all()
    )

    return LobbyResponse(
        room_code=room.room_code,
        status=room.status,
        player_count=len(players),
        max_players=MAX_PLAYERS,
        players=players,
    )


@router.patch(
    "/rooms/{room_code}/players/{player_id}/ready",
    response_model=PlayerResponse,
)
@limiter.limit("10/minute")
async def update_player_ready(
    request: Request,
    room_code: str,
    player_id: int,
    payload: PlayerReady,
    current_player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
):
    room = get_waiting_room(db, room_code)
    ensure_player_ownership(room, current_player)

    if current_player.id != player_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change your own readiness.",
        )

    player = get_active_player(db, room, player_id)
    player.is_ready = payload.is_ready

    db.commit()
    db.refresh(player)

    await manager.broadcast(
        room.room_code,
        player_event(player, "player_ready_changed"),
        exclude_player_id=player.id,
    )

    return player


@router.delete(
    "/rooms/{room_code}/players/{player_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("5/minute")
async def leave_room(
    request: Request,
    room_code: str,
    player_id: int,
    current_player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
):
    room = get_room(db, room_code)
    ensure_player_ownership(room, current_player)

    if current_player.id != player_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only leave as your own player.",
        )

    player = get_active_player(db, room, player_id)
    player.left_at = utc_now()
    player.is_ready = False

    db.commit()

    await manager.broadcast(
        room.room_code,
        {
            "type": "player_left",
            "player_id": player.id,
            "display_name": player.display_name,
        },
        exclude_player_id=player.id,
    )

    await manager.disconnect(room.room_code, player.id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
