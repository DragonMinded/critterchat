import logging
from typing import Any, Protocol

from ..config import Config
from ..data import Data
from ..service import EmoteService

logger = logging.getLogger(__name__)


class SupportsSocketIO(Protocol):
    def emit(self, event: str, details: dict[str, object], *, room: Any = None) -> None: ...


def send_emote_deltas(config: Config, data: Data, socketio: SupportsSocketIO, emotes: set[str]) -> set[str]:
    emoteservice = EmoteService(config, data)
    newemotes = emoteservice.get_all_emotes()
    additions: set[str] = set()
    deletions: set[str] = set()

    for emote in newemotes:
        if emote not in emotes:
            # This was an addition.
            additions.add(emote)

    for emote in emotes:
        if emote not in newemotes:
            # This was a deletion.
            deletions.add(emote)

    # Send the delta to the clients, intentionally not choosing a room here.
    if additions or deletions:
        if additions:
            logger.info("Detected the following added emotes: " + ", ".join(additions))
        if deletions:
            logger.info("Detected the following removed emotes: " + ", ".join(deletions))
        socketio.emit('emotechanges', {
            'additions': {f":{alias}:": newemotes[alias].to_dict() for alias in additions},
            'deletions': [f":{d}:" for d in deletions],
        })
        emotes = {k for k in newemotes}

    return emotes
