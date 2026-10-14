
import asyncio
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.game.result_service import save_game_result
from app.game.round_service import finish_round, start_round
from app.game.websocket_manager import manager
from app.models.game_round import GameRound
from app.models.game_room import GameRoom
from app.models.player import Player

_round_tasks: dict[int, tuple[int, asyncio.Task]] = {}


def _elapsed_seconds(started_at: datetime) -> float:
    now = datetime.utcnow()

    if started_at.tzinfo is not None:
        now = now.replace(tzinfo=started_at.tzinfo)

    return max(0.0, (now - started_at).total_seconds())


def get_remaining_seconds(started_at: datetime) -> int:
    remaining = (
        settings.ROUND_DURATION_SECONDS - _elapsed_seconds(started_at)
    )
    return max(0, int(remaining + 0.999))


def start_round_timer(room_id: int, round_number: int) -> None:
    existing = _round_tasks.get(room_id)

    if existing is not None:
        existing_round, existing_task = existing

        if existing_round == round_number and not existing_task.done():
            return

        existing_task.cancel()

    task = asyncio.create_task(_run_round_timer(room_id, round_number))
    _round_tasks[room_id] = (round_number, task)


async def _run_round_timer(room_id: int, round_number: int) -> None:
    current_task = asyncio.current_task()

    try:
        while True:
            db = SessionLocal()

            try:
                room = (
                    db.query(GameRoom)
                    .filter(GameRoom.id == room_id)
                    .first()
                )

                if (
                    room is None
                    or room.status != "playing"
                    or room.current_round != round_number
                ):
                    return

                game_round = (
                    db.query(GameRound)
                    .filter(
                        GameRound.room_id == room_id,
                        GameRound.round_number == round_number,
                    )
                    .first()
                )

                if game_round is None or game_round.ended_at is not None:
                    return

                remaining = get_remaining_seconds(game_round.started_at)
                room_code = room.room_code
                started_at = game_round.started_at.isoformat()

            finally:
                db.close()

            await manager.broadcast(
                room_code,
                {
                    "type": "timer_sync",
                    "round_number": round_number,
                    "started_at": started_at,
                    "duration_seconds": settings.ROUND_DURATION_SECONDS,
                    "remaining_seconds": remaining,
                },
            )

            if remaining <= 0:
                break

            await asyncio.sleep(min(5, remaining))

        db = SessionLocal()

        try:
            room = (
                db.query(GameRoom)
                .filter(GameRoom.id == room_id)
                .with_for_update()
                .first()
            )

            if (
                room is None
                or room.status != "playing"
                or room.current_round != round_number
            ):
                return

            game_round = (
                db.query(GameRound)
                .filter(
                    GameRound.room_id == room_id,
                    GameRound.round_number == round_number,
                )
                .with_for_update()
                .first()
            )

            if game_round is None or game_round.ended_at is not None:
                return

            room_code = room.room_code
            secret_word = game_round.word
            drawer_player_id = game_round.drawer_player_id

            finish_round(db, room, game_round)
            db.refresh(room)

            players = (
                db.query(Player)
                .filter(Player.room_id == room.id)
                .order_by(Player.score.desc(), Player.joined_at.asc())
                .all()
            )

            scoreboard = [
                {
                    "player_id": player.id,
                    "display_name": player.display_name,
                    "score": player.score,
                }
                for player in players
            ]

            await manager.broadcast(
                room_code,
                {
                    "type": "round_ended",
                    "round_number": round_number,
                    "drawer_player_id": drawer_player_id,
                    "word": secret_word,
                    "reason": "time_up",
                    "scoreboard": scoreboard,
                },
            )

            if room.status == "completed":
                result = save_game_result(db, room)

                await manager.broadcast(
                    room_code,
                    {
                        "type": "game_completed",
                        "room_code": room_code,
                        "total_rounds": room.total_rounds,
                        "scoreboard": scoreboard,
                        "winner": (
                            {
                                "player_id": result.winner_player_id,
                                "display_name": next(
                                    (
                                        item["display_name"]
                                        for item in scoreboard
                                        if item["player_id"]
                                        == result.winner_player_id
                                    ),
                                    None,
                                ),
                            }
                            if result and result.winner_player_id is not None
                            else None
                        ),
                    },
                )
                return

            next_round = (
                db.query(GameRound)
                .filter(
                    GameRound.room_id == room.id,
                    GameRound.round_number == room.current_round,
                )
                .first()
            )

            if next_round is None:
                next_round = start_round(db, room)

            drawer = (
                db.query(Player)
                .filter(Player.id == next_round.drawer_player_id)
                .first()
            )

            await manager.broadcast(
                room_code,
                {
                    "type": "round_started",
                    "round_number": next_round.round_number,
                    "drawer_player_id": next_round.drawer_player_id,
                    "drawer_display_name": (
                        drawer.display_name if drawer else None
                    ),
                    "started_at": next_round.started_at.isoformat(),
                    "duration_seconds": settings.ROUND_DURATION_SECONDS,
                },
            )

            start_round_timer(room.id, next_round.round_number)

        finally:
            db.close()

    except asyncio.CancelledError:
        raise

    finally:
        current = _round_tasks.get(room_id)

        if current is not None and current[1] is current_task:
            _round_tasks.pop(room_id, None)


def cancel_round_timer(room_id: int) -> None:
    current = _round_tasks.pop(room_id, None)

    if current is not None:
        current[1].cancel()
