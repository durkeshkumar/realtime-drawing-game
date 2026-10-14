import json
import time
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sqlalchemy.orm import Session

from app.core.security import decode_access_token

from app.db.session import SessionLocal

from app.game.websocket_manager import manager

from app.models.game_room import GameRoom

from app.models.game_round import GameRound

from app.models.guess import Guess

from app.models.player import Player

router = APIRouter(tags=["WebSockets"])

MAX_STROKE_POINTS = 500

MAX_MESSAGE_LENGTH = 64_000

MAX_GUESS_LENGTH = 100

POINTS_PER_CORRECT_GUESS = 10

# Per-WebSocket-connection flood protection.
MAX_MESSAGES_PER_WINDOW = 60
MESSAGE_WINDOW_SECONDS = 10

class WebSocketRateLimiter:
    """Limit incoming messages using a rolling time window."""

    def __init__(
        self,
        max_messages: int = MAX_MESSAGES_PER_WINDOW,
        window_seconds: int = MESSAGE_WINDOW_SECONDS,
    ) -> None:
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.timestamps = deque()

    def allow_message(self) -> bool:
        now = time.monotonic()

        while (
            self.timestamps
            and now - self.timestamps[0] >= self.window_seconds
        ):
            self.timestamps.popleft()

        if len(self.timestamps) >= self.max_messages:
            return False

        self.timestamps.append(now)
        return True

ALLOWED_DRAWING_EVENTS = {

    "draw_start",

    "draw_move",

    "draw_end",

    "clear_canvas",

}

class DrawingPoint(BaseModel):

    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1, allow_inf_nan=False)

    y: float = Field(ge=0, le=1, allow_inf_nan=False)

class DrawingEvent(BaseModel):

    model_config = ConfigDict(extra="forbid")

    type: str

    round_number: int = Field(ge=1)

    color: str = Field(default="#000000", min_length=4, max_length=7)

    line_width: float = Field(

        default=4.0,

        gt=0,

        le=50,

        allow_inf_nan=False,

    )

    points: list[DrawingPoint] = Field(default_factory=list)

class GuessEvent(BaseModel):

    model_config = ConfigDict(extra="forbid")

    type: str

    round_number: int = Field(ge=1)

    guess: str = Field(min_length=1, max_length=MAX_GUESS_LENGTH)

def get_active_round(

    db: Session,

    room_id: int,

    round_number: int,

) -> GameRound | None:

    return (

        db.query(GameRound)

        .filter(

            GameRound.room_id == room_id,

            GameRound.round_number == round_number,

            GameRound.ended_at.is_(None),

        )

        .first()

    )

def build_scoreboard(db: Session, room_id: int) -> list[dict]:

    players = (

        db.query(Player)

        .filter(

            Player.room_id == room_id,

            Player.left_at.is_(None),

        )

        .order_by(Player.score.desc(), Player.joined_at.asc())

        .all()

    )

    return [

        {

            "player_id": player.id,

            "display_name": player.display_name,

            "score": player.score,

            "is_ready": player.is_ready,

        }

        for player in players

    ]

def build_restored_state(

    db: Session,

    room: GameRoom,

    player: Player,

) -> dict:

    game_round = None

    if room.status == "playing" and room.current_round > 0:

        game_round = (

            db.query(GameRound)

            .filter(

                GameRound.room_id == room.id,

                GameRound.round_number == room.current_round,

            )

            .first()

        )

    state = {

        "type": "state_restored",

        "room": {

            "room_code": room.room_code,

            "status": room.status,

            "current_round": room.current_round,

            "total_rounds": room.total_rounds,

        },

        "player": {

            "player_id": player.id,

            "display_name": player.display_name,

            "score": player.score,

            "is_ready": player.is_ready,

        },

        "players": build_scoreboard(db, room.id),

        "connected_player_ids": [],

        "current_round": None,

    }

    if game_round is not None:

        round_state = {

            "round_number": game_round.round_number,

            "drawer_player_id": game_round.drawer_player_id,

            "started_at": (

                game_round.started_at.isoformat()

                if game_round.started_at

                else None

            ),

            "ended_at": (

                game_round.ended_at.isoformat()

                if game_round.ended_at

                else None

            ),

        }

        # Only the assigned drawer receives the secret word.

        if game_round.drawer_player_id == player.id:

            round_state["word"] = game_round.word

        state["current_round"] = round_state

    return state

def validate_websocket_token(

    token: str | None,

    room_code: str,

    player_id: int,

) -> bool:

    if not token:

        return False

    payload = decode_access_token(token)

    if not isinstance(payload, dict):

        return False

    if payload.get("token_type") != "player_access":

        return False

    try:

        token_player_id = int(payload.get("sub", ""))

    except (TypeError, ValueError):

        return False

    token_room_code = str(

        payload.get("room_code", "")

    ).strip().upper()

    return (

        token_player_id == player_id

        and token_room_code == room_code

        and player_id > 0

    )

async def send_error(

    room_code: str,

    player_id: int,

    message: str,

) -> None:

    await manager.send_personal_message(

        {

            "type": "error",

            "message": message,

        },

        room_code,

        player_id,

    )

def valid_color(color: str) -> bool:

    return (

        len(color) in {4, 7}

        and color.startswith("#")

        and all(

            character in "0123456789abcdefABCDEF"

            for character in color[1:]

        )

    )

@router.websocket("/ws/rooms/{room_code}")

async def room_websocket(

    websocket: WebSocket,

    room_code: str,

    player_id: int,

    token: str | None = None,

):

    normalized_room_code = room_code.strip().upper()

    # Authenticate before registering the WebSocket connection.

    if not validate_websocket_token(

        token,

        normalized_room_code,

        player_id,

    ):

        await websocket.close(

            code=1008,

            reason="Invalid or missing authentication token",

        )

        return

    db = SessionLocal()

    try:

        room = (

            db.query(GameRoom)

            .filter(GameRoom.room_code == normalized_room_code)

            .first()

        )

        if room is None:

            await websocket.close(

                code=1008,

                reason="Room not found",

            )

            return

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

            await websocket.close(

                code=1008,

                reason="Invalid or inactive player",

            )

            return

        room_id = room.id

        restored_state = build_restored_state(db, room, player)

    finally:

        db.close()

    await manager.connect(

        normalized_room_code,

        player_id,

        websocket,

    )

    try:

        connected_ids = await manager.get_connected_player_ids(

            normalized_room_code

        )

        restored_state["connected_player_ids"] = connected_ids

        await manager.send_personal_message(

            {

                "type": "connected",

                "room_code": normalized_room_code,

                "player_id": player_id,

            },

            normalized_room_code,

            player_id,

        )

        await manager.send_personal_message(

            restored_state,

            normalized_room_code,

            player_id,

        )

        await manager.broadcast(

            normalized_room_code,

            {

                "type": "player_presence",

                "player_id": player_id,

                "online": True,

                "connected_player_ids": connected_ids,

            },

            exclude_player_id=player_id,

        )

        message_limiter = WebSocketRateLimiter()

        while True:

            # Read raw text first so the size can be checked before JSON parsing.

            raw_message = await websocket.receive_text()

            if not message_limiter.allow_message():
                await send_error(
                    normalized_room_code,
                    player_id,
                    "Too many messages. Please slow down and try again.",
                )
                await websocket.close(
                    code=1008,
                    reason="WebSocket message rate limit exceeded",
                )
                break

            if len(raw_message.encode("utf-8")) > MAX_MESSAGE_LENGTH:

                await send_error(

                    normalized_room_code,

                    player_id,

                    "Message is too large.",

                )

                continue

            try:

                message = json.loads(raw_message)

            except (json.JSONDecodeError, ValueError):

                await send_error(

                    normalized_room_code,

                    player_id,

                    "Invalid JSON message.",

                )

                continue

            if not isinstance(message, dict):

                await send_error(

                    normalized_room_code,

                    player_id,

                    "Expected a JSON object.",

                )

                continue

            event_type = message.get("type")

            if event_type == "ping":

                await manager.send_personal_message(

                    {"type": "pong"},

                    normalized_room_code,

                    player_id,

                )

                continue

            if event_type not in ALLOWED_DRAWING_EVENTS | {"guess"}:

                await send_error(

                    normalized_room_code,

                    player_id,

                    "Unsupported event type.",

                )

                continue

            db = SessionLocal()

            try:

                room = (

                    db.query(GameRoom)

                    .filter(GameRoom.id == room_id)

                    .first()

                )

                if room is None or room.status != "playing":

                    await send_error(

                        normalized_room_code,

                        player_id,

                        "The game is not playing.",

                    )

                    continue

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

                    await websocket.close(

                        code=1008,

                        reason="Player is no longer active",

                    )

                    return

                active_round = get_active_round(

                    db,

                    room.id,

                    room.current_round,

                )

                if (

                    active_round is None

                    or message.get("round_number") != room.current_round

                ):

                    await send_error(

                        normalized_room_code,

                        player_id,

                        "No active round or invalid round number.",

                    )

                    continue

                if event_type == "guess":

                    try:

                        guess_event = GuessEvent.model_validate(message)

                    except ValidationError:

                        await send_error(

                            normalized_room_code,

                            player_id,

                            "Invalid guess event.",

                        )

                        continue

                    if guess_event.type != "guess":

                        await send_error(

                            normalized_room_code,

                            player_id,

                            "Invalid guess event type.",

                        )

                        continue

                    if active_round.drawer_player_id == player_id:

                        await send_error(

                            normalized_room_code,

                            player_id,

                            "The drawer cannot guess.",

                        )

                        continue

                    guess_text = guess_event.guess.strip()

                    if not guess_text:

                        await send_error(

                            normalized_room_code,

                            player_id,

                            "Guess cannot be empty.",

                        )

                        continue

                    previous_correct = (

                        db.query(Guess)

                        .filter(

                            Guess.round_id == active_round.id,

                            Guess.player_id == player_id,

                            Guess.is_correct.is_(True),

                        )

                        .first()

                    )

                    if previous_correct is not None:

                        await manager.send_personal_message(

                            {

                                "type": "already_guessed",

                                "message": (

                                    "You already guessed correctly "

                                    "this round."

                                ),

                            },

                            normalized_room_code,

                            player_id,

                        )

                        continue

                    is_correct = (

                        guess_text.casefold()

                        == active_round.word.strip().casefold()

                    )

                    guesser = (

                        db.query(Player)

                        .filter(

                            Player.id == player_id,

                            Player.room_id == room.id,

                            Player.left_at.is_(None),

                        )

                        .with_for_update()

                        .first()

                    )

                    if guesser is None:

                        continue

                    db.add(

                        Guess(

                            round_id=active_round.id,

                            player_id=player_id,

                            guess_text=guess_text,

                            is_correct=is_correct,

                        )

                    )

                    if is_correct:

                        guesser.score += POINTS_PER_CORRECT_GUESS

                    db.commit()

                    db.refresh(guesser)

                    if is_correct:

                        await manager.broadcast(

                            normalized_room_code,

                            {

                                "type": "correct_guess",

                                "player_id": player_id,

                                "display_name": guesser.display_name,

                                "points_awarded": POINTS_PER_CORRECT_GUESS,

                                "score": guesser.score,

                                "round_number": active_round.round_number,

                                "scoreboard": build_scoreboard(

                                    db,

                                    room.id,

                                ),

                            },

                        )

                    else:

                        await manager.broadcast(

                            normalized_room_code,

                            {

                                "type": "guess",

                                "player_id": player_id,

                                "guess": guess_text,

                                "is_correct": False,

                            },

                            exclude_player_id=player_id,

                        )

                    continue

                try:

                    drawing_event = DrawingEvent.model_validate(message)

                except ValidationError:

                    await send_error(

                        normalized_room_code,

                        player_id,

                        "Invalid drawing event.",

                    )

                    continue

                if drawing_event.type != event_type:

                    await send_error(

                        normalized_room_code,

                        player_id,

                        "Drawing event type does not match.",

                    )

                    continue

                if event_type not in ALLOWED_DRAWING_EVENTS:

                    continue

                if len(drawing_event.points) > MAX_STROKE_POINTS:

                    await send_error(

                        normalized_room_code,

                        player_id,

                        "Too many points in drawing event.",

                    )

                    continue

                if not valid_color(drawing_event.color):

                    await send_error(

                        normalized_room_code,

                        player_id,

                        "Invalid drawing color.",

                    )

                    continue

                if active_round.drawer_player_id != player_id:

                    await send_error(

                        normalized_room_code,

                        player_id,

                        "Only the drawer can draw.",

                    )

                    continue

                await manager.broadcast(

                    normalized_room_code,

                    {

                        **drawing_event.model_dump(),

                        "player_id": player_id,

                    },

                    exclude_player_id=player_id,

                )

            except Exception:

                db.rollback()

                await send_error(

                    normalized_room_code,

                    player_id,

                    "Unable to process the message.",

                )

            finally:

                db.close()

    except WebSocketDisconnect:

        pass

    finally:

        await manager.disconnect(

            normalized_room_code,

            player_id,

            websocket,

        )

        connected_ids = await manager.get_connected_player_ids(

            normalized_room_code

        )

        await manager.broadcast(

            normalized_room_code,

            {

                "type": "player_presence",

                "player_id": player_id,

                "online": player_id in connected_ids,

                "connected_player_ids": connected_ids,

            },

        )
