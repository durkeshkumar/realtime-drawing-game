
from threading import Lock

_ready_players: set[int] = set()
_lock = Lock()


def set_player_ready(player_id: int, is_ready: bool) -> None:
    with _lock:
        if is_ready:
            _ready_players.add(player_id)
        else:
            _ready_players.discard(player_id)


def is_player_ready(player_id: int) -> bool:
    with _lock:
        return player_id in _ready_players


def remove_player_readiness(player_id: int) -> None:
    with _lock:
        _ready_players.discard(player_id)
