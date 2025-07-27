import urllib.request
from threading import Lock
from typing import Any, Dict, Optional, Set, cast
from typing_extensions import Final

from .app import socketio, config, request
from ..common import AESCipher, Time
from ..service import EmoteService, UserService, MessageService, UserServiceException, MessageServiceException
from ..data import Data, Action, Room, User, UserPermission, UserSettings, NewActionID, ActionID, RoomID, UserID


class SocketInfo:
    def __init__(self, sid: Any, sessionid: Optional[str], userid: Optional[UserID]) -> None:
        self.sid = sid
        self.sessionid = sessionid
        self.userid = userid
        self.fetchlimit: Dict[RoomID, Optional[ActionID]] = {}
        self.lastseen: Dict[RoomID, int] = {}


MESSAGE_PUMP_TICK_SECONDS: Final[float] = 0.25
EMOJI_REFRESH_TICK_SECONDS: Final[int] = 5


MAX_ICON_WIDTH: Final[int] = 256
MAX_ICON_HEIGHT: Final[int] = 256


socket_lock: Lock = Lock()
socket_to_info: Dict[Any, SocketInfo] = {}
background_thread: Optional[object] = None


def background_thread_proc() -> None:
    """
    The background polling thread that manages asynchronous messages from the database.
    """

    data = Data(config)
    messageservice = MessageService(config, data)
    userservice = UserService(config, data)
    emoteservice = EmoteService(config, data)

    # Make sure we can send emote additions and subtractions to the connected clients.
    emotes = {k for k in emoteservice.get_all_emotes()}
    last_update = Time.now()

    while True:
        # Just yield to the async system.
        socketio.sleep(MESSAGE_PUMP_TICK_SECONDS)

        # See if we need to update emotes on clients.
        if Time.now() - last_update >= EMOJI_REFRESH_TICK_SECONDS:
            newemotes = emoteservice.get_all_emotes()
            additions: Set[str] = set()
            deletions: Set[str] = set()

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
                socketio.emit('emotechanges', {
                    'additions': {f":{alias}:": newemotes[alias] for alias in additions},
                    'deletions': [f":{d}:" for d in deletions],
                })
                emotes = {k for k in newemotes}
            last_update = Time.now()

        # Look for any new actions that should be relayed.
        with socket_lock:
            if not socket_to_info:
                print("Shutting down message pump thread due to no more client sockets.")

                global background_thread
                background_thread = None

                return

            for _, info in socket_to_info.items():
                # First, if they were deactivated, inform them now.
                user = userservice.lookup_user(info.userid) if info.userid is not None else None
                if user is None or UserPermission.ACTIVATED not in user.permissions:
                    socketio.emit('reload', {}, room=info.sid)
                    continue

                updated = False
                for roomid, fetchlimit in info.fetchlimit.items():
                    # Only fetch deltas for clients that have gotten an initial fetch for a room.
                    if fetchlimit is not None:
                        actions = messageservice.get_room_updates(roomid, after=fetchlimit)

                        if actions:
                            for action in actions:
                                fetchlimit = action.id if fetchlimit is None else max(fetchlimit, action.id)
                            info.fetchlimit[roomid] = fetchlimit or NewActionID

                            socketio.emit('chatactions', {
                                'roomid': Room.from_id(roomid),
                                'actions': [action.to_dict() for action in actions],
                            }, room=info.sid)
                            updated = True

                # Figure out if this user has been joined to a new chat.
                if info.userid is not None:
                    # Figure out if rooms have changed, so we can start monitoring.
                    rooms = messageservice.get_joined_rooms(info.userid)

                    for room in rooms:
                        if room.id not in info.fetchlimit:
                            updated = True
                            lastaction = messageservice.get_last_room_action(room.id)
                            if lastaction:
                                info.fetchlimit[room.id] = lastaction.id
                            else:
                                info.fetchlimit[room.id] = NewActionID

                    # Calculate any badge updates that the client needs to know about.
                    lastseen = userservice.get_last_seen_counts(info.userid)
                    counts: Dict[RoomID, int] = {}
                    for roomid, count in lastseen.items():
                        if count < info.lastseen.get(roomid, 0):
                            counts[roomid] = count
                            updated = True
                        info.lastseen[roomid] = count

                    if updated:
                        # Notify the client of any room rearranges, or any new rooms.
                        socketio.emit('roomlist', {
                            'rooms': [room.to_dict() for room in rooms],
                            'counts': [{'roomid': Room.from_id(k), 'count': v} for k, v in counts.items()],
                        }, room=info.sid)


def register_sid(data: Data, sid: Any, sessionid: Optional[str]) -> None:
    with socket_lock:
        global background_thread
        if background_thread is None:
            print("Starting message pump thread due to first client socket connection.")
            background_thread = socketio.start_background_task(background_thread_proc)

        user = None if sessionid is None else data.user.from_session(sessionid)
        socket_to_info[sid] = SocketInfo(sid, sessionid, user.id if user is not None else None)


def unregister_sid(sid: Any) -> None:
    with socket_lock:
        if sid in socket_to_info:
            del socket_to_info[sid]


def recover_info(sid: Any) -> SocketInfo:
    with socket_lock:
        if sid not in socket_to_info:
            return SocketInfo(sid, None, None)

        return socket_to_info[sid]


def recover_userid(data: Data, sid: Any) -> Optional[UserID]:
    info = recover_info(sid)
    if info.sessionid is None:
        # Session was de-authed, tell the client to refresh.
        socketio.emit('reload', {}, room=sid)
        return None

    user = data.user.from_session(info.sessionid)
    if user is None:
        # Session was de-authed, tell the client to refresh.
        socketio.emit('reload', {}, room=sid)
        return None

    if info.userid != user.id:
        # Session is invalid, tell the client to refresh.
        socketio.emit('reload', {}, room=sid)
        return None

    if UserPermission.ACTIVATED not in user.permissions:
        # User is not activated, they might have been deactivated.
        socketio.emit('reload', {}, room=sid)
        return None

    return user.id


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
    data = Data(config)
    register_sid(data, request.sid, sessionID)


@socketio.on('disconnect')  # type: ignore
def disconnect() -> None:
    # Explicitly kill the presence since we know they're gone.
    unregister_sid(request.sid)


@socketio.on('motd')  # type: ignore
def motd(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    user = userservice.lookup_user(userid)
    if user:
        if UserPermission.WELCOMED not in user.permissions:
            # TODO: Look up any welcome message to display to the user here.
            extra = ""
            rooms = messageservice.get_autojoin_rooms(userid)
            if rooms:
                extra += "You will be automatically added to the following rooms."

            socketio.emit('welcome', {
                "message": f"Welcome to {config.name}! {extra}",
                "rooms": [room.to_dict() for room in rooms],
            }, room=request.sid)


@socketio.on('welcomeaccept')  # type: ignore
def welcomeaccept(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    messageservice.join_autojoin_rooms(userid)
    userservice.add_permission(userid, UserPermission.WELCOMED)
    rooms = messageservice.get_joined_rooms(userid)
    if rooms:
        socketio.emit('roomlist', {
            'rooms': [room.to_dict() for room in rooms],
            'selected': Room.from_id(rooms[-1].id),
        }, room=request.sid)


@socketio.on('roomlist')  # type: ignore
def roomlist(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    info = recover_info(request.sid)
    if userid is None or info is None:
        return

    with socket_lock:
        # Grab all rooms that the user is in, based on their user ID.
        rooms = messageservice.get_joined_rooms(userid)
        lastseen = userservice.get_last_seen_counts(userid)

        # Pre-charge the delta fetches for all rooms this user is in.
        for room in rooms:
            action = messageservice.get_last_room_action(room.id)
            if action:
                info.fetchlimit[room.id] = action.id
            else:
                info.fetchlimit[room.id] = NewActionID

            info.lastseen[room.id] = lastseen.get(room.id, 0)

    socketio.emit('roomlist', {
        'rooms': [room.to_dict() for room in rooms],
        'counts': [{'roomid': Room.from_id(k), 'count': v} for k, v in lastseen.items()],
    }, room=request.sid)


@socketio.on('lastsettings')  # type: ignore
def lastsettings(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Look up last settings for this user.
    socketio.emit('lastsettings', userservice.get_settings(userid).to_dict(), room=request.sid)


@socketio.on('profile')  # type: ignore
def profile(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Look up last settings for this user.
    userprofile = userservice.lookup_user(userid)
    if userprofile:
        socketio.emit('profile', userprofile.to_dict(), room=request.sid)


@socketio.on('updatesettings')  # type: ignore
def updatesettings(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Save last settings for this user.
    userservice.update_settings(userid, UserSettings.from_dict(userid, json))


@socketio.on('updateprofile')  # type: ignore
def updateprofile(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Save last settings for this user.
    details = cast(Dict[str, object], json.get('details', {}))
    newname = str(details.get('name', ''))
    newicon = str(details.get('icon', ''))

    if newname and len(newname) > 255:
        socketio.emit('error', {'error': 'Your nickname is too long!'}, room=request.sid)
        return

    # TODO: Configurable, maybe?
    if len(newicon) > 128000:
        socketio.emit('error', {'error': 'Chosen avatar file size is too large!'}, room=request.sid)
        return

    icon: Optional[bytes] = None
    if newicon:
        # Verify that it's a reasonable icon.
        header, _ = newicon.split(",", 1)
        if not header.startswith("data:") or not header.endswith("base64"):
            socketio.emit('error', {'error': 'Chosen avatar is not a valid image!'}, room=request.sid)
            return

        with urllib.request.urlopen(newicon) as fp:
            icon = fp.read()

    try:
        userservice.update_user(userid, name=newname, icon=icon)
        userprofile = userservice.lookup_user(userid)
        if userprofile:
            socketio.emit('profile', userprofile.to_dict(), room=request.sid)
    except UserServiceException as e:
        socketio.emit('error', {'error': str(e)}, room=request.sid)


@socketio.on('chathistory')  # type: ignore
def chathistory(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    info = recover_info(request.sid)
    if userid is None or info is None:
        return

    # Locking our socket info so we can keep track of what history we've seen,
    # so that we can send deltas afterwards to the client when new chats happen.
    with socket_lock:
        roomid = Room.to_id(str(json.get('roomid')))
        if roomid:
            rooms = messageservice.get_joined_rooms(userid)
            joinedrooms = {room.id for room in rooms}
            if roomid not in joinedrooms:
                # Trying to grab chat for a room we're not in!
                return

            lastseen = userservice.get_last_seen_actions(userid)
            actions = messageservice.get_room_history(roomid)
            occupants = messageservice.get_room_occupants(roomid)

            # Starting from scratch here since this messages clears the chat pane on the client.
            fetchlimit = None
            for action in actions:
                fetchlimit = action.id if fetchlimit is None else max(fetchlimit, action.id)
            info.fetchlimit[roomid] = fetchlimit or NewActionID

            # Also report the last seen message, so that a "new" indicator can be displayed.
            lastaction = lastseen.get(roomid, None)

            socketio.emit('chathistory', {
                'roomid': Room.from_id(roomid),
                'history': [action.to_dict() for action in actions],
                'occupants': [occupant.to_dict() for occupant in occupants],
                'lastseen': Action.from_id(lastaction) if lastaction else None,
            }, room=request.sid)


@socketio.on('message')  # type: ignore
def message(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    roomid = Room.to_id(str(json.get('roomid')))
    message = json.get('message')
    if roomid and message:
        rooms = messageservice.get_joined_rooms(userid)
        joinedrooms = {room.id for room in rooms}
        if roomid not in joinedrooms:
            # Trying to insert a chat for a room we're not in!
            return

        try:
            messageservice.add_message(roomid, userid, str(message))
        except MessageServiceException as e:
            socketio.emit('error', {'error': str(e)}, room=request.sid)


@socketio.on('leaveroom')  # type: ignore
def leaveroom(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    info = recover_info(request.sid)
    if userid is None or info is None:
        return

    # Locking our socket info so we can remove this chat from our monitoring.
    with socket_lock:
        roomid = Room.to_id(str(json.get('roomid')))
        if roomid:
            if roomid in info.fetchlimit:
                del info.fetchlimit[roomid]

            messageservice.leave_room(roomid, userid)


@socketio.on('searchrooms')  # type: ignore
def searchrooms(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Grab all rooms that match this search result
    rooms = messageservice.get_matching_rooms(userid, name=str(json.get('name')))
    socketio.emit('searchrooms', {
        'rooms': [room.to_dict() for room in rooms],
    }, room=request.sid)


@socketio.on('joinroom')  # type: ignore
def joinroom(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    info = recover_info(request.sid)
    if userid is None or info is None:
        return

    # Locking our socket info so we can add this chat to our monitoring.
    actual_id: Optional[RoomID] = None
    with socket_lock:
        roomid = Room.to_id(str(json.get('roomid')))
        if roomid:
            messageservice.join_room(roomid, userid)
            actual_id = roomid

        otherid = User.to_id(str(json.get('roomid')))
        if otherid:
            room = messageservice.create_chat(userid, otherid)
            if room:
                actual_id = room.id

        # Grab all rooms that the user is in, based on their user ID.
        rooms = messageservice.get_joined_rooms(userid)

        # Pre-charge the delta fetches for all rooms this user is in.
        for room in rooms:
            action = messageservice.get_last_room_action(room.id)
            if action:
                info.fetchlimit[room.id] = action.id
            else:
                info.fetchlimit[room.id] = NewActionID

    if actual_id:
        socketio.emit('roomlist', {
            'rooms': [room.to_dict() for room in rooms],
            'selected': Room.from_id(actual_id),
        }, room=request.sid)


@socketio.on('lastaction')  # type: ignore
def lastaction(json: Dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Grab all rooms that match this search result
    roomid = Room.to_id(str(json.get('roomid')))
    actionid = Action.to_id(str(json.get('actionid')))
    if roomid is not None and actionid is not None:
        userservice.mark_last_seen(userid, roomid, actionid)


@socketio.on('updateroom')  # type: ignore
def updateroom(json: Dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    userid = recover_userid(data, request.sid)
    if userid is None:
        return

    # Grab all rooms that match this search result
    roomid = Room.to_id(str(json.get('roomid')))
    if roomid is not None:
        details = cast(Dict[str, object], json.get('details', {}))
        newname = str(details.get('name', ''))
        newtopic = str(details.get('topic', ''))
        newicon = str(details.get('icon', ''))

        rooms = messageservice.get_joined_rooms(userid)
        joinedrooms = {room.id for room in rooms}
        if roomid not in joinedrooms:
            # Trying to grab chat for a room we're not in!
            return

        # TODO: Configurable, maybe?
        if len(newicon) > 128000:
            socketio.emit('error', {'error': 'Chosen icon file size is too large!'}, room=request.sid)
            return

        icon: Optional[bytes] = None
        if newicon:
            # Verify that it's a reasonable icon.
            header, _ = newicon.split(",", 1)
            if not header.startswith("data:") or not header.endswith("base64"):
                socketio.emit('error', {'error': 'Chosen icon is not a valid image!'}, room=request.sid)
                return

            with urllib.request.urlopen(newicon) as fp:
                icon = fp.read()

        try:
            messageservice.update_room(roomid, userid, name=newname, topic=newtopic, icon=icon)
        except MessageServiceException as e:
            socketio.emit('error', {'error': str(e)}, room=request.sid)
