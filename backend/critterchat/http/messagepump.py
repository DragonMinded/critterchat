import logging
from threading import Lock
from typing import Any, Protocol, cast

from ..config import Config
from ..common import Time
from ..data import (
    Data,
    NewActionID,
    ActionID,
    UserID,
    RoomID,
    Action,
    ActionType,
    Room,
    User,
    UserPermission,
)
from ..service import EmoteService, MessageService, UserService

logger = logging.getLogger(__name__)


class SupportsSocketIO(Protocol):
    def emit(self, event: str, details: dict[str, object], *, room: Any = None) -> None: ...


class SocketInfo:
    def __init__(self, sid: Any, sessionid: str | None, userid: UserID | None) -> None:
        self.sid = sid
        self.sessionid = sessionid
        self.userid = userid
        self.fetchlimit: dict[RoomID, ActionID | None] = {}
        self.lastseen: dict[RoomID, int] = {}
        self.profilets: int | None = None
        self.prefsts: int | None = None
        self.lock: Lock = Lock()


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


def send_chat_deltas(
    config: Config,
    data: Data,
    socketio: SupportsSocketIO,
    info: SocketInfo,
    user: User,
) -> None:
    messageservice = MessageService(config, data)
    userservice = UserService(config, data)

    updated = False
    for roomid, fetchlimit in info.fetchlimit.items():
        # Only fetch deltas for clients that have gotten an initial fetch for a room.
        if fetchlimit is not None:
            actions = messageservice.get_room_updates(roomid, after=fetchlimit)

            if actions:
                filtered: list[Action] = []
                seen: set[ActionID] = set()

                for action in actions:
                    fetchlimit = action.id if fetchlimit is None else max(fetchlimit, action.id)

                    if action.action == ActionType.CHANGE_USERS:
                        occupants = messageservice.lookup_room_occupants(roomid, user.id)
                        if occupants is not None:
                            action.details = {
                                "occupants": [o.to_dict() for o in occupants],
                            }

                    elif action.action == ActionType.CHANGE_MESSAGE:
                        original = cast(ActionID, action.details["actionid"])
                        if original not in seen:
                            seen.add(original)

                            # Swap out the change message for the original updated message.
                            grabbed = messageservice.lookup_action(original)
                            if grabbed:
                                grabbed = grabbed.clone()
                                grabbed.details['modified'] = True

                                filtered.append(grabbed)

                    # This should go to the client.
                    filtered.append(action)

                info.fetchlimit[roomid] = fetchlimit or NewActionID

                socketio.emit('chatactions', {
                    'roomid': Room.from_id(roomid),
                    'actions': [action.to_dict() for action in filtered],
                }, room=info.sid)
                updated = True

    # Figure out if this user has been joined to a new chat.
    # Figure out if rooms have changed, so we can start monitoring.
    rooms = messageservice.get_joined_rooms(user.id)

    includes: set[RoomID] = set()
    for room in rooms:
        if room.id not in info.fetchlimit:
            includes.add(room.id)
            info.fetchlimit[room.id] = room.newest_action if room.newest_action is not None else NewActionID
            updated = True

    # Calculate any badge updates that the client needs to know about, including
    # badges on newly-joined rooms.
    lastseen = userservice.get_last_seen_counts(user.id)
    counts: dict[RoomID, int] = {}
    for roomid, count in lastseen.items():
        if roomid in includes or count < info.lastseen.get(roomid, 0):
            counts[roomid] = count
        info.lastseen[roomid] = count

    if updated or counts:
        clientdata: dict[str, object] = {}
        if updated:
            clientdata['rooms'] = [room.to_dict() for room in rooms]
        if counts:
            clientdata['counts'] = [{'roomid': Room.from_id(k), 'count': v} for k, v in counts.items()]

        # Notify the client of any room rearranges, or any new rooms.
        socketio.emit('roomlist', clientdata, room=info.sid)

    # Figure out if preferences or profile changed since our last poll,
    # and send an updated "preferences" or "profile" response to said
    # client if it has. This should keep prefs and profiles in sync
    # across multiple sessions at once.
    profilets = info.profilets
    prefsts = info.prefsts

    if profilets is not None:
        ts = Time.now()
        if userservice.has_updated_user(user.id, profilets):
            userprofile = userservice.lookup_user(user.id)
            admin = UserPermission.ADMINISTRATOR in user.permissions
            if userprofile:
                info.profilets = ts
                socketio.emit('profile', userprofile.to_dict(config=config, admin=admin), room=info.sid)

    if prefsts is not None:
        ts = Time.now()
        if userservice.has_updated_preferences(user.id, prefsts):
            userpreferences = userservice.get_preferences(user.id)
            if userpreferences:
                info.prefsts = ts
                socketio.emit('preferences', userpreferences.to_dict(), room=info.sid)
