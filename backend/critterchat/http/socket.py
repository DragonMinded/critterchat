import logging
import traceback
from importlib.metadata import PackageNotFoundError, version
from threading import Lock
from typing import Any, Final, Literal, cast

from .app import app, socketio, config, request
from ..common import AESCipher, Time, represents_real_text
from ..service import (
    AttachmentService,
    EmoteService,
    UserService,
    MessageService,
    UserServiceException,
    MessageServiceException,
)
from ..data import (
    Data,
    Action,
    ActionType,
    Attachment,
    Room,
    User,
    UserPermission,
    UserSettings,
    Occupant,
    NewActionID,
    ActionID,
    AttachmentID,
    FaviconID,
    RoomID,
    UserID,
)


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


MESSAGE_PUMP_TICK_SECONDS: Final[float] = 0.05
EMOJI_REFRESH_TICK_SECONDS: Final[int] = 5


MAX_ICON_WIDTH: Final[int] = 256
MAX_ICON_HEIGHT: Final[int] = 256


socket_lock: Lock = Lock()
socket_to_info: dict[Any, SocketInfo] = {}
background_thread: object | None = None
logger = logging.getLogger(__name__)


def background_thread_proc() -> None:
    while True:
        try:
            background_thread_proc_impl()
            return
        except Exception:
            logger.error(traceback.format_exc())
            logger.info("Background polling thread died with an exception, restarting!")


def background_thread_proc_impl() -> None:
    """
    The background polling thread that manages asynchronous messages from the database.
    """

    data = Data(config)
    messageservice = MessageService(config, data)
    userservice = UserService(config, data)
    emoteservice = EmoteService(config, data)

    # Make sure we can send emote additions and subtractions to the connected clients.
    emotes = {k for k in emoteservice.get_all_emotes()}
    last_emote_update = Time.now()
    last_user_update: int | None = None
    last_action: ActionID | None = None

    while True:
        # Just yield to the async system.
        socketio.sleep(MESSAGE_PUMP_TICK_SECONDS)

        # See if we need to update emotes on clients.
        if (Time.now() - last_emote_update) >= EMOJI_REFRESH_TICK_SECONDS:
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
            last_emote_update = Time.now()

        # Look for any new actions that should be relayed.
        current_action = messageservice.get_last_action()
        current_update = userservice.get_last_user_update()

        # Shut down early if we have nothing to poll.
        global background_thread
        with socket_lock:
            if not socket_to_info:
                logger.info("Shutting down message pump thread due to no more client sockets.")
                background_thread = None

                return

        if current_action == last_action and current_update == last_user_update:
            # Nothing to do, skip the expensive part below.
            continue

        last_action = current_action
        last_user_update = current_update

        # If we have actual actions, grab who we need to act on and then individually lock.
        # This prevents a misbehaving client from locking the whole network.
        with socket_lock:
            if not socket_to_info:
                logger.info("Shutting down message pump thread due to no more client sockets.")
                background_thread = None

                return

            sockets: list[SocketInfo] = list(socket_to_info.values())

        # Keep a lookup of room occupants so we don't look this up repeatedly during CHANGE_USERS events.
        occupantcache: dict[RoomID, list[Occupant]] = {}

        # Keep a lookup of actions so we don't look this up repeatedly during CHANGE_MESSAGE events.
        actioncache: dict[ActionID, Action | None] = {}

        for info in sockets:
            # Lock this so other communication with this client doesn't get out of order.
            locked = info.lock.acquire(blocking=False)
            if locked:
                try:
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
                                filtered: list[Action] = []
                                seen: set[ActionID] = set()

                                for action in actions:
                                    fetchlimit = action.id if fetchlimit is None else max(fetchlimit, action.id)

                                    if action.action == ActionType.CHANGE_USERS:
                                        if roomid not in occupantcache:
                                            room = messageservice.lookup_room(roomid, user.id)
                                            if room:
                                                occupantcache[roomid] = room.occupants

                                        if roomid in occupantcache:
                                            action.details = {
                                                "occupants": [o.to_dict() for o in occupantcache[roomid]],
                                            }

                                    elif action.action == ActionType.CHANGE_MESSAGE:
                                        original = cast(ActionID, action.details["actionid"])
                                        if original not in seen:
                                            seen.add(original)
                                            if original not in actioncache:
                                                actioncache[original] = messageservice.lookup_action(original)

                                            # Swap out the change message for the original updated message.
                                            grabbed = actioncache[original]
                                            if grabbed:
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
                            admin = userprofile is not None and UserPermission.ADMINISTRATOR in userprofile.permissions
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

                finally:
                    info.lock.release()


def register_sid(data: Data, sid: Any, sessionid: str | None) -> None:
    with socket_lock:
        global background_thread
        if background_thread is None:
            logger.info("Starting message pump thread due to first client socket connection.")
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


def recover_sessionid(data: Data, sid: Any) -> str | None:
    info = recover_info(sid)
    if info.sessionid is None:
        # Session was de-authed, tell the client to refresh.
        socketio.emit('reload', {}, room=sid)
        return None

    return info.sessionid


def recover_user(data: Data, sid: Any) -> User | None:
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

    return user


def hydrate_tag(request: dict[str, object], response: dict[str, object]) -> dict[str, object]:
    if 'tag' not in request:
        return response

    return {**response, 'tag': request['tag']}


def flash(severity: Literal["success", "info", "warning", "error"], message: str, *, room: Any) -> None:
    socketio.emit('flash', {'severity': severity, 'message': message}, room=room)


def error(message: str, *, room: Any) -> None:
    socketio.emit('error', {'error': message}, room=room)


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
    user = recover_user(data, request.sid)
    username = user.username if user else "(anonymous)"

    logger.info(f"Client {username} connected from {request.remote_addr} with session {request.sid}")


@socketio.on('disconnect')  # type: ignore
def disconnect() -> None:
    # Grab the person's information for logging purposes.
    data = Data(config)
    user = recover_user(data, request.sid)
    username = user.username if user else "(anonymous)"

    # Explicitly kill the presence since we know they're gone.
    unregister_sid(request.sid)
    logger.info(f"Client {username} disconnected from {request.remote_addr} with session {request.sid}")


@socketio.on('info')  # type: ignore
def serverinfo(json: dict[str, object]) -> None:
    data = Data(config)
    attachmentservice = AttachmentService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Figure out if we're running in development mode or production mode.
    try:
        ver = version('critterchat')
        ver = f"v{ver}" if ver else "development"
    except PackageNotFoundError:
        ver = "development"

    if app.config.get("DEBUG"):
        ver += "+debug"

    # Look up any server info to display to the user here.
    socketio.emit('info', hydrate_tag(json, {
        "name": config.name,
        "icon": attachmentservice.get_attachment_url(FaviconID),
        "administrator": config.administrator,
        "source": config.source,
        "version": "CritterChat " + ver,
        "info": config.info,
    }), room=request.sid)


@socketio.on('motd')  # type: ignore
def motd(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)
    attachmentservice = AttachmentService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    if UserPermission.WELCOMED not in user.permissions:
        # Look up any server info to display to the user here.
        extra = config.info
        rooms = messageservice.get_autojoin_rooms(user.id)
        if rooms:
            extra += "<p>You will be automatically added to the following rooms.</p>"

        socketio.emit('welcome', {
            "name": config.name,
            "icon": attachmentservice.get_attachment_url(FaviconID),
            "administrator": config.administrator,
            "source": config.source,
            "message": extra,
            "rooms": [room.to_dict() for room in rooms],
        }, room=request.sid)


@socketio.on('welcomeaccept')  # type: ignore
def welcomeaccept(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    messageservice.join_autojoin_rooms(user.id)
    userservice.add_permission(user.id, UserPermission.WELCOMED)
    rooms = messageservice.get_joined_rooms(user.id)
    if rooms:
        socketio.emit('roomlist', {
            'rooms': [room.to_dict() for room in rooms],
            'selected': Room.from_id(rooms[-1].id),
        }, room=request.sid)


@socketio.on('roomlist')  # type: ignore
def roomlist(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    info = recover_info(request.sid)
    if user is None or info is None:
        return

    with info.lock:
        # Grab all rooms that the user is in, based on their user ID.
        rooms = messageservice.get_joined_rooms(user.id)
        lastseen = userservice.get_last_seen_counts(user.id)

        # Pre-charge the delta fetches for all rooms this user is in.
        for room in rooms:
            info.fetchlimit[room.id] = room.newest_action if room.newest_action is not None else NewActionID
            info.lastseen[room.id] = lastseen.get(room.id, 0)

    socketio.emit('roomlist', hydrate_tag(json, {
        'rooms': [room.to_dict() for room in rooms],
        'counts': [{'roomid': Room.from_id(k), 'count': v} for k, v in lastseen.items()],
    }), room=request.sid)


@socketio.on('lastsettings')  # type: ignore
def lastsettings(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user and login session if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return
    sessionid = recover_sessionid(data, request.sid)
    if sessionid is None:
        return

    # Look up last settings for this user.
    socketio.emit('lastsettings', hydrate_tag(json, userservice.get_settings(sessionid, user.id).to_dict()), room=request.sid)


@socketio.on('profile')  # type: ignore
def profile(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    info = recover_info(request.sid)
    if user is None or info is None:
        return

    admin = user is not None and UserPermission.ADMINISTRATOR in user.permissions

    otheruserid = User.to_id(str(json.get('userid')))
    if otheruserid:
        # Generic profile lookup request.
        userprofile = userservice.lookup_user(otheruserid)
        if userprofile:
            socketio.emit('profile', hydrate_tag(json, userprofile.to_dict(config=config, admin=admin)), room=request.sid)
            return

    occupantid = Occupant.to_id(str(json.get('userid')))
    if occupantid:
        # Per-room profile lookup request.
        userprofile = messageservice.lookup_occupant(occupantid)
        if userprofile:
            socketio.emit('profile', hydrate_tag(json, userprofile.to_dict(config=config, admin=admin)), room=request.sid)
            return

    # Locking our socket info so we can keep track of profiles sent to all sessions.
    # That way we can notify other sessions if the current one changes their profile.
    with info.lock:
        # Look up last settings for this user.
        ts = Time.now()
        userprofile = userservice.lookup_user(user.id)
        if userprofile:
            info.profilets = ts
            socketio.emit('profile', hydrate_tag(json, userprofile.to_dict(config=config, admin=admin)), room=request.sid)


@socketio.on('preferences')  # type: ignore
def preferences(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    info = recover_info(request.sid)
    if user is None or info is None:
        return

    # Locking our socket info so we can keep track of profiles sent to all sessions.
    # That way we can notify other sessions if the current one changes their profile.
    with info.lock:
        # Look up last settings for this user.
        ts = Time.now()
        userpreferences = userservice.get_preferences(user.id)
        if userpreferences:
            info.prefsts = ts
            socketio.emit('preferences', hydrate_tag(json, userpreferences.to_dict()), room=request.sid)


@socketio.on('updatesettings')  # type: ignore
def updatesettings(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user and login session if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return
    sessionid = recover_sessionid(data, request.sid)
    if sessionid is None:
        return

    # Save last settings for this user.
    userservice.update_settings(sessionid, UserSettings.from_dict(user.id, json))


@socketio.on('updateprofile')  # type: ignore
def updateprofile(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Save last settings for this user.
    newname = str(json.get('name', '')).strip()
    newicon = str(json.get('icon', '')).strip()
    newabout = str(json.get('about', '')).strip()
    icondelete = bool(json.get('icon_delete', ''))

    # We allow spaces inside names, but not space-only names.
    if not represents_real_text(newname):
        newname = ""

    if newname and len(newname) > 255:
        flash('warning', 'Your nickname is too long!', room=request.sid)
        return
    if len(newabout) > config.limits.about_length:
        flash('warning', 'Your about section is too long!', room=request.sid)
        return

    icon: AttachmentID | None = None
    if newicon:
        icon = Attachment.to_id(newicon)

    try:
        userservice.update_user(user.id, name=newname, about=newabout, icon=icon, icon_delete=icondelete)
        userprofile = userservice.lookup_user(user.id)
        admin = userprofile is not None and UserPermission.ADMINISTRATOR in userprofile.permissions

        if userprofile:
            socketio.emit('profile', hydrate_tag(json, userprofile.to_dict(config=config, admin=admin)), room=request.sid)
            flash('success', 'Your profile has been updated!', room=request.sid)
    except UserServiceException as e:
        error(str(e), room=request.sid)


@socketio.on('updatepreferences')  # type: ignore
def updatepreferences(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user and login session if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Save preferences for this user.
    new_rooms_on_top = json.get('rooms_on_top', None)
    if new_rooms_on_top is not None:
        new_rooms_on_top = bool(new_rooms_on_top)
    new_combined_messages = json.get('combined_messages', None)
    if new_combined_messages is not None:
        new_combined_messages = bool(new_combined_messages)
    new_color_scheme = json.get('color_scheme', None)
    if new_color_scheme is not None:
        new_color_scheme = {
            "system": "system",
            "light": "light",
            "dark": "dark",
        }.get(str(new_color_scheme))
    new_desktop_size = json.get('desktop_size', None)
    if new_desktop_size is not None:
        new_desktop_size = {
            "smallest": "smallest",
            "smaller": "smaller",
            "normal": "normal",
            "larger": "larger",
            "largest": "largest",
        }.get(str(new_desktop_size))
    new_mobile_size = json.get('mobile_size', None)
    if new_mobile_size is not None:
        new_mobile_size = {
            "smallest": "smallest",
            "smaller": "smaller",
            "normal": "normal",
            "larger": "larger",
            "largest": "largest",
        }.get(str(new_mobile_size))
    new_admin_controls = json.get('admin_controls', None)
    if new_admin_controls is not None:
        new_admin_controls = {
            "hidden": "hidden",
            "visible": "visible",
        }.get(str(new_admin_controls))
    new_title_notifs = json.get('title_notifs', None)
    if new_title_notifs is not None:
        new_title_notifs = bool(new_title_notifs)
    new_mobile_audio_notifs = json.get('mobile_audio_notifs', None)
    if new_mobile_audio_notifs is not None:
        new_mobile_audio_notifs = bool(new_mobile_audio_notifs)
    new_audio_notifs = json.get('audio_notifs', None)
    if new_audio_notifs is not None:
        if isinstance(new_audio_notifs, list):
            new_audio_notifs = {str(x) for x in new_audio_notifs}
        else:
            new_audio_notifs = None
    notif_delete = json.get('notif_sounds_delete', None)
    if notif_delete is not None:
        if isinstance(notif_delete, list):
            notif_delete = {str(x) for x in notif_delete}
        else:
            notif_delete = None

    new_notif_sounds: dict[str, AttachmentID] = {}
    notif_dict = json.get('notif_sounds', {}) or {}
    if isinstance(notif_dict, dict):
        for name, data in notif_dict.items():
            if not isinstance(name, str) or not isinstance(data, str):
                continue

            aid = Attachment.to_id(data)
            if aid:
                new_notif_sounds[name] = aid

    try:
        userservice.update_preferences(
            user.id,
            rooms_on_top=new_rooms_on_top,
            combined_messages=new_combined_messages,
            color_scheme=new_color_scheme,
            desktop_size=new_desktop_size,
            mobile_size=new_mobile_size,
            admin_controls=new_admin_controls,
            title_notifs=new_title_notifs,
            mobile_audio_notifs=new_mobile_audio_notifs,
            audio_notifs=new_audio_notifs,
            notif_sounds=new_notif_sounds,
            notif_sounds_delete=notif_delete,
        )
        flash('success', 'Your preferences have been updated!', room=request.sid)
    except UserServiceException as e:
        error(str(e), room=request.sid)


@socketio.on('chatactions')  # type: ignore
def chatactions(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    info = recover_info(request.sid)
    if user is None or info is None:
        return

    # Locking our socket info so we can keep track of what history we've seen,
    # so that we can send deltas afterwards to the client when new chats happen.
    with info.lock:
        roomid = Room.to_id(str(json.get('roomid')))
        if roomid:
            # Grab the current room in our joined rooms list. There's a way more performant
            # way to do this but we can fix that later.
            rooms = messageservice.get_joined_rooms(user.id)
            rooms = [r for r in rooms if r.id == roomid]
            room = rooms[0] if rooms else None

            if not room:
                # Trying to grab chat for a room we're not in!
                return

            if (after := json.get('after', None)) and (afterid := Action.to_id(str(after))):
                actions = messageservice.get_room_updates(roomid, after=afterid)
                seen: set[ActionID] = set()

                # Starting from the known last seen action ID here, since this is a client
                # catch-up message after reconnecting. With this pre-charged, we won't end
                # up re-sending the messages again in the message pump thread above.
                fetchlimit = afterid
                filtered: list[Action] = []

                for action in actions:
                    fetchlimit = max(fetchlimit, action.id)

                    if action.action == ActionType.CHANGE_USERS:
                        action.details = {
                            "occupants": [o.to_dict() for o in room.occupants],
                        }

                    elif action.action == ActionType.CHANGE_MESSAGE:
                        original = cast(ActionID, action.details["actionid"])
                        if original not in seen:
                            # Swap out the change message for the original updated message.
                            seen.add(original)
                            grabbed = messageservice.lookup_action(original)
                            if grabbed:
                                grabbed.details['modified'] = True
                                filtered.append(grabbed)

                    # This should go to the client as-is.
                    filtered.append(action)

                info.fetchlimit[roomid] = fetchlimit

                socketio.emit('chatactions', hydrate_tag(json, {
                    'roomid': Room.from_id(roomid),
                    'actions': [action.to_dict() for action in filtered],
                }), room=request.sid)


@socketio.on('chathistory')  # type: ignore
def chathistory(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    info = recover_info(request.sid)
    if user is None or info is None:
        return

    # Locking our socket info so we can keep track of what history we've seen,
    # so that we can send deltas afterwards to the client when new chats happen.
    with info.lock:
        roomid = Room.to_id(str(json.get('roomid')))
        if roomid:
            rooms = messageservice.get_joined_rooms(user.id)
            joinedrooms = {room.id: room for room in rooms}
            if roomid not in joinedrooms:
                # Trying to grab chat for a room we're not in!
                return

            before = json.get('before', None)
            if before:
                beforeid = Action.to_id(str(before))
                actions = messageservice.get_room_history(roomid, before=beforeid)

                socketio.emit('chathistory', hydrate_tag(json, {
                    'roomid': Room.from_id(roomid),
                    'history': [action.to_dict() for action in actions],
                }), room=request.sid)

            else:
                lastseen = userservice.get_last_seen_actions(user.id)
                actions = messageservice.get_room_history(roomid)
                occupants = messageservice.get_room_occupants(roomid)

                # Starting from the point where we read here, and only updating if new events
                # somehow came in after we read the list of joined rooms. This stops us from
                # accidentally re-sending events that aren't looked up in get_room_history such
                # as CHANGE_MESSAGE actions.
                fetchlimit = joinedrooms[roomid].newest_action
                for action in actions:
                    fetchlimit = action.id if fetchlimit is None else max(fetchlimit, action.id)
                info.fetchlimit[roomid] = fetchlimit or NewActionID

                # Also report the last seen message, so that a "new" indicator can be displayed.
                lastaction = lastseen.get(roomid, None)

                socketio.emit('chathistory', hydrate_tag(json, {
                    'roomid': Room.from_id(roomid),
                    'history': [action.to_dict() for action in actions],
                    'occupants': [occupant.to_dict() for occupant in occupants],
                    'lastseen': Action.from_id(lastaction) if lastaction else None,
                }), room=request.sid)


@socketio.on('invite')  # type: ignore
def invite(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Only allow generating invites if the server allows it or the user is
    # an administrator.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Ensure that the user is actually an admin.
    is_admin = UserPermission.ADMINISTRATOR in user.permissions
    if is_admin or config.account_registration.invites:
        url = userservice.create_user_invite(user.id)
        socketio.emit('invite', hydrate_tag(json, {'invite': url}), room=request.sid)
    else:
        error(f'Invites are disabled on {config.name}!', room=request.sid)


@socketio.on('message')  # type: ignore
def message(json: dict[str, object]) -> dict[str, object]:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return {'status': 'failed'}

    roomid = Room.to_id(str(json.get('roomid')))

    # While we allow funny formatting and spaces, we don't allow space-only messages.
    message = str(json.get('message')).strip()
    if roomid:
        rooms = messageservice.get_joined_rooms(user.id)
        joinedrooms = {room.id for room in rooms}
        if roomid not in joinedrooms:
            # Trying to insert a chat for a room we're not in!
            return {'status': 'failed'}

        # Add any attachments that came along with the data.
        attachments: list[AttachmentID] = []
        atchlist = json.get('attachments', [])
        if isinstance(atchlist, list):
            for atch in atchlist:
                aid = Attachment.to_id(str(atch))
                if not aid:
                    continue

                attachments.append(aid)

        if len(attachments) > config.limits.attachment_max:
            if config.limits.attachment_max:
                flash('warning', 'Too many attachments!', room=request.sid)
            else:
                flash('warning', 'Attachments are disabled!', room=request.sid)
            return {'status': 'failed'}

        # Add any sensitivity tag.
        sensitive = bool(json.get('sensitive'))

        if represents_real_text(message) or attachments:
            try:
                # Now, send the message itself.
                messageservice.add_message(roomid, user.id, message, sensitive, attachments)
                return {'status': 'success'}
            except MessageServiceException as e:
                error(str(e), room=request.sid)

    # Failed somehow, either got an exception or invalid room ID.
    return {'status': 'failed'}


@socketio.on('leaveroom')  # type: ignore
def leaveroom(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    info = recover_info(request.sid)
    if user is None or info is None:
        return

    # Locking our socket info so we can remove this chat from our monitoring.
    with info.lock:
        roomid = Room.to_id(str(json.get('roomid')))
        if roomid:
            if roomid in info.fetchlimit:
                del info.fetchlimit[roomid]

            messageservice.leave_room(roomid, user.id)


@socketio.on('searchrooms')  # type: ignore
def searchrooms(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Grab all rooms that match this search result
    rooms = messageservice.get_matching_rooms(user.id, name=str(json.get('name')))
    socketio.emit('searchrooms', hydrate_tag(json, {
        'rooms': [room.to_dict() for room in rooms],
    }), room=request.sid)


@socketio.on('joinroom')  # type: ignore
def joinroom(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    info = recover_info(request.sid)
    if user is None or info is None:
        return

    # Locking our socket info so we can add this chat to our monitoring.
    actual_id: RoomID | None = None
    with info.lock:
        roomid = Room.to_id(str(json.get('roomid')))
        if roomid:
            try:
                messageservice.join_room(roomid, user.id)
                actual_id = roomid
            except MessageServiceException as e:
                error(str(e), room=request.sid)
                return

        otherid = User.to_id(str(json.get('roomid')))
        if otherid:
            try:
                room = messageservice.create_direct_message(user.id, otherid)
                actual_id = room.id
            except MessageServiceException as e:
                error(str(e), room=request.sid)
                return

        if actual_id:
            # Grab all rooms that the user is in, based on their user ID.
            rooms = messageservice.get_joined_rooms(user.id)

            # Pre-charge the delta fetches for all rooms this user is in that
            # they weren't in beforehand.
            for room in rooms:
                if room.id not in info.fetchlimit:
                    info.fetchlimit[room.id] = room.newest_action if room.newest_action is not None else NewActionID

    if actual_id:
        socketio.emit('roomlist', {
            'rooms': [room.to_dict() for room in rooms],
            'selected': Room.from_id(actual_id),
        }, room=request.sid)


@socketio.on('lastaction')  # type: ignore
def lastaction(json: dict[str, object]) -> None:
    data = Data(config)
    userservice = UserService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Grab all rooms that match this search result
    roomid = Room.to_id(str(json.get('roomid')))
    actionid = Action.to_id(str(json.get('actionid')))
    if roomid is not None and actionid is not None:
        userservice.mark_last_seen(user.id, roomid, actionid)


@socketio.on('updateroom')  # type: ignore
def updateroom(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Grab all rooms that match this search result
    roomid = Room.to_id(str(json.get('roomid')))
    if roomid is not None:
        room = messageservice.lookup_room(roomid, user.id)
        if room is None:
            # Trying to update a non-existent room?
            return

        occupants = [o for o in room.occupants if o.userid == user.id]
        if len(occupants) != 1:
            # Trying to update a room we're not in or more than one match?
            return
        myself = occupants[0]

        # Now, if it's a moderated room, make sure we're a moderator.
        if room.moderated and not myself.moderator:
            # Nice try buck-o.
            return

        details = cast(dict[str, object], json.get('details', {}))
        newname = str(details.get('name', '')).strip()
        newtopic = str(details.get('topic', '')).strip()
        newicon = str(details.get('icon', '')).strip()
        icondelete = bool(details.get('icon_delete', ''))

        newmoderated: bool | None = None
        if UserPermission.ADMINISTRATOR in user.permissions:
            newmoderated = bool(details.get('moderated', ''))

        if not represents_real_text(newname):
            newname = ""
        if not represents_real_text(newtopic):
            newtopic = ""

        icon: AttachmentID | None = None
        if newicon:
            icon = Attachment.to_id(newicon)

        try:
            messageservice.update_room(
                roomid,
                user.id,
                name=newname,
                topic=newtopic,
                moderated=newmoderated,
                icon=icon,
                icon_delete=icondelete,
            )
        except MessageServiceException as e:
            error(str(e), room=request.sid)


@socketio.on('admin')  # type: ignore
def adminaction(json: dict[str, object]) -> dict[str, object]:
    data = Data(config)
    userservice = UserService(config, data)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return {'status': 'failed'}

    # Ensure that the user is actually an admin.
    if UserPermission.ADMINISTRATOR not in user.permissions:
        return {'status': 'failed'}

    # Grab the action and delegate.
    action = str(json.get('action', ''))

    try:
        if action == "activate":
            # Activate user.
            otheruserid = User.to_id(str(json.get('userid')))
            if otheruserid:
                userservice.add_permission(otheruserid, UserPermission.ACTIVATED)
                flash('success', 'User activated!', room=request.sid)
                return {'status': 'success'}
            else:
                flash('error', 'User does not exist!', room=request.sid)
                return {'status': 'failed'}

        elif action == "deactivate":
            # Deactivate user.
            otheruserid = User.to_id(str(json.get('userid')))
            if otheruserid:
                userservice.remove_permission(otheruserid, UserPermission.ACTIVATED)
                flash('success', 'User deactivated!', room=request.sid)
                return {'status': 'success'}
            else:
                flash('error', 'User does not exist!', room=request.sid)
                return {'status': 'failed'}

        elif action == "mod":
            # Set an occupant as a moderator.
            occupantid = Occupant.to_id(str(json.get('occupantid')))
            if occupantid:
                messageservice.grant_occupant_moderator(occupantid)
                flash('success', 'User moderator role granted for room!', room=request.sid)
                return {'status': 'success'}
            else:
                flash('error', 'User does not exist!', room=request.sid)
                return {'status': 'failed'}

        elif action == "demod":
            # Set an occupant as a regular user.
            occupantid = Occupant.to_id(str(json.get('occupantid')))
            if occupantid:
                messageservice.revoke_occupant_moderator(occupantid)
                flash('success', 'User moderator role revoked for room!', room=request.sid)
                return {'status': 'success'}
            else:
                flash('error', 'User does not exist!', room=request.sid)
                return {'status': 'failed'}

        else:
            error('Unrecognized action requested!', room=request.sid)
            return {'status': 'failed'}
    except MessageServiceException as e:
        flash('error', str(e), room=request.sid)
        return {'status': 'failed'}
    except UserServiceException as e:
        flash('error', str(e), room=request.sid)
        return {'status': 'failed'}


@socketio.on('mod')  # type: ignore
def modaction(json: dict[str, object]) -> dict[str, object]:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return {'status': 'failed'}

    # Figure out if the user is actually an admin, because there's some mod actions that
    # an admin can take (such as muting/unmuting in free-for-all public rooms).
    is_admin = UserPermission.ADMINISTRATOR in user.permissions

    # Grab the action and delegate.
    action = str(json.get('action', ''))

    try:
        if action in {"mute", "unmute"}:
            # Mute user in channel.
            otheruserid = Occupant.to_id(str(json.get('occupantid')))
            if not otheruserid:
                flash('error', 'User does not exist!', room=request.sid)
                return {'status': 'failed'}

            room = messageservice.get_occupant_room(otheruserid)
            if not room:
                flash('error', 'User does not exist!', room=request.sid)
                return {'status': 'failed'}

            is_moderator = False
            if room.moderated:
                # Moderated room needs this user to be a mod or an admin to act.
                myself = [o for o in room.occupants if o.userid == user.id]
                if len(myself) != 1:
                    flash('error', 'You cannot mute or unmute somebody in a room you are not in!', room=request.sid)
                    return {'status': 'failed'}

                is_moderator = myself[0].moderator
                if myself[0].id == otheruserid:
                    flash('error', 'You cannot mute or unmute yourself!', room=request.sid)
                    return {'status': 'failed'}

                if is_moderator or is_admin:
                    if action == "mute":
                        messageservice.mute_occupant(otheruserid)
                        flash('success', 'User muted!', room=request.sid)
                    else:
                        messageservice.unmute_occupant(otheruserid)
                        flash('success', 'User unmuted!', room=request.sid)
                    return {'status': 'success'}

            else:
                # Free-for-all room needs this user to simply be an admin.
                if is_admin:
                    if action == "mute":
                        messageservice.mute_occupant(otheruserid)
                        flash('success', 'User muted!', room=request.sid)
                    else:
                        messageservice.unmute_occupant(otheruserid)
                        flash('success', 'User unmuted!', room=request.sid)
                    return {'status': 'success'}

            # Silently refuse to modify, due to user not having the correct role.
            return {'status': 'failed'}

        else:
            error('Unrecognized action requested!', room=request.sid)
            return {'status': 'failed'}
    except MessageServiceException as e:
        flash('error', str(e), room=request.sid)
        return {'status': 'failed'}
    except UserServiceException as e:
        flash('error', str(e), room=request.sid)
        return {'status': 'failed'}


@socketio.on('reaction')  # type: ignore
def reaction(json: dict[str, object]) -> None:
    data = Data(config)
    messageservice = MessageService(config, data)

    # Try to associate with a user if there is one.
    user = recover_user(data, request.sid)
    if user is None:
        return

    # Grab the action ID of the action being reacted to, the reaction emoji and
    # the type of reaction (add or remove).
    actionid = Action.to_id(str(json.get('actionid')))
    if not actionid:
        return

    reaction = str(json.get('reaction'))
    reactiontype = str(json.get('type'))

    try:
        if reactiontype == "add":
            messageservice.add_reaction(user.id, actionid, reaction)
        elif reactiontype == "remove":
            messageservice.remove_reaction(user.id, actionid, reaction)
    except MessageServiceException as e:
        error(str(e), room=request.sid)
