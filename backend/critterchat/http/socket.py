from typing import Any, Dict, Optional

from .app import socketio, config, request
from ..common import AESCipher
from ..service import UserService, MessageService
from ..data import Data, Room, UserSettings, UserID


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
        socketio.emit('reload', {}, room=sid)
        return None

    userid = data.user.from_session(info.sessionid)
    if userid is None:
        # Session was de-authed, tell the client to refresh.
        socketio.emit('reload', {}, room=sid)
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
        del socket_to_info[request.sid]

    # Explicitly kill the presence since we know they're gone.
    unregister_sid(request.sid)


@socketio.on('roomlist')  # type: ignore
def roomlist(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Grab all rooms that the user is in, based on their user ID.
    rooms = userservice.get_joined_rooms(userid)
    socketio.emit('roomlist', {
        'rooms': [room.to_dict() for room in rooms],
    }, room=request.sid)


@socketio.on('lastsettings')  # type: ignore
def lastsettings(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Look up last settings for this user.
    socketio.emit('lastsettings', userservice.get_settings(userid).to_dict(), room=request.sid)


@socketio.on('updatesettings')  # type: ignore
def updatesettings(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Save last settings for this user.
    userservice.update_settings(userid, UserSettings.from_dict(userid, json))


@socketio.on('chathistory')  # type: ignore
def chathistory(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    roomid = Room.to_id(str(json.get('roomid')))
    if roomid:
        socketio.emit('chathistory', {
            'roomid': Room.from_id(roomid),
            'history': [action.to_dict() for action in messageservice.get_room_history(roomid)],
        }, room=request.sid)


@socketio.on('message')  # type: ignore
def message(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    roomid = Room.to_id(str(json.get('roomid')))
    message = json.get('message')
    if roomid and message:
        action = messageservice.add_message(roomid, userid, str(message))
        if action:
            # We don't update our last fetched action here because it could be newer than
            # some other messages, so we don't want to hide those until refresh.
            socketio.emit('chatactions', {
                'roomid': Room.from_id(roomid),
                'actions': [action.to_dict()],
            }, room=request.sid)
