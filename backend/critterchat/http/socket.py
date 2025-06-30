from typing import Any, Dict, Optional

from .app import socketio, config, request
from ..common import AESCipher, Time
from ..data import Data, Action, Occupant, Room, ActionID, OccupantID, RoomID, UserID


class SocketInfo:
    def __init__(self, sid: Any, sessionid: Optional[str]) -> None:
        self.sid = sid
        self.sessionid = sessionid


socket_to_info: Dict[Any, SocketInfo] = {}


def register_sid(sid: Any, sessionid: Optional[str]) -> None:
    socket_to_info[sid] = SocketInfo(sid, sessionid)


def unregister_sid(sid: Any) -> None:
    if sid in socket_to_info:
        del socket_to_info[sid]


def recover_info(sid: Any) -> SocketInfo:
    if sid not in socket_to_info:
        return SocketInfo(sid, None)

    return socket_to_info[sid]


def recover_userid(data: Data, sid: Any) -> Optional[UserID]:
    info = recover_info(sid)
    if info.sessionid is None:
        # Session was de-authed, tell the client to refresh.
        socketio.emit('reload', {})
        return None

    userid = data.user.from_session(info.sessionid)
    if userid is None:
        # Session was de-authed, tell the client to refresh.
        socketio.emit('reload', {})
        return None

    return userid


@socketio.on('connect')  # type: ignore
def connect() -> None:
    unregister_sid(request.sid)

    ciphered_session = request.cookies.get("SessionID")
    if ciphered_session:
        try:
            aes = AESCipher(config.cookie_key)
            sessionID = aes.decrypt(ciphered_session)
        except Exception:
            sessionID = None
    else:
        sessionID = None

    # Make sure we track this client so we don't get a premature hang-up.
    register_sid(request.sid, sessionID)


@socketio.on('disconnect')  # type: ignore
def disconnect() -> None:
    if request.sid in socket_to_info:
        info = socket_to_info[request.sid]
        del socket_to_info[request.sid]

    # Explicitly kill the presence since we know they're gone.
    unregister_sid(request.sid)


@socketio.on('roomlist')  # type: ignore
def roomlist(json: Dict[str, object]) -> None:
    data = Data(config)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Grab all rooms that the user is in, based on their user ID.
    rooms = data.room.get_joined_rooms(userid)
    rooms.append(Room(RoomID(12345), "This is a test"))
    rooms.append(Room(RoomID(23456), "This is another test"))
    rooms.append(Room(RoomID(12345), "This should rename"))
    socketio.emit('roomlist', {
        'rooms': [room.to_dict() for room in rooms],
    })


@socketio.on('lastsettings')  # type: ignore
def lastsettings(json: Dict[str, object]) -> None:
    data = Data(config)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # TODO: Look up last settings for this user.
    socketio.emit('lastsettings', {
        'roomid': Room.from_id(RoomID(12345)),
    })


@socketio.on('updatesettings')  # type: ignore
def updatesettings(json: Dict[str, object]) -> None:
    data = Data(config)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # TODO: Save settings for this user.
    print(json)


@socketio.on('chathistory')  # type: ignore
def chathistory(json: Dict[str, object]) -> None:
    data = Data(config)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    roomid = Room.to_id(str(json.get('roomid')))
    if roomid:
        # TODO: Need to look up nicknames in profiles for anyone who hasn't set their name custom.
        history = data.room.get_room_history(roomid)
        history.append(Action(ActionID(2222), Time.now(), Occupant(OccupantID(100), UserID(userid), "kirakira"), "message", "this is a test message for room " + str(roomid)))
        history.append(Action(ActionID(2223), Time.now(), Occupant(OccupantID(100), UserID(userid), "kirakira"), "message", "this is a test message again"))
        history.append(Action(ActionID(2224), Time.now(), Occupant(OccupantID(100), UserID(userid), "kirakira"), "message", "this is a test message a third time"))
        history.append(Action(ActionID(2225), Time.now(), Occupant(OccupantID(100), UserID(userid), "kirakira"), "message", "this is a test message a fourth time with an edit"))
        socketio.emit('chathistory', {
            'roomid': Room.from_id(roomid),
            'history': [action.to_dict() for action in history],
        })
