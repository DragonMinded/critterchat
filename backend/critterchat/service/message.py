import emoji
import io
from PIL import Image
from typing import List, Optional

from ..config import Config
from ..common import Time
from ..data import (
    Data,
    Action,
    ActionType,
    Occupant,
    Room,
    RoomType,
    RoomSearchResult,
    DefaultAvatarID,
    DefaultRoomID,
    NewOccupantID,
    NewActionID,
    NewRoomID,
    NewUserID,
    ActionID,
    RoomID,
    UserID,
)
from .attachment import AttachmentService


class MessageServiceException(Exception):
    pass


class MessageService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__attachments = AttachmentService(self.__config, self.__data)

    def get_last_action(self) -> Optional[ActionID]:
        return self.__data.room.get_last_action()

    def get_last_room_action(self, roomid: RoomID) -> Optional[Action]:
        history = self.__data.room.get_room_history(roomid, limit=1)
        return self.__attachments.resolve_action_icon(history[0]) if history else None

    def get_room_history(self, roomid: RoomID) -> List[Action]:
        history = self.__data.room.get_room_history(roomid)
        history = [
            self.__attachments.resolve_action_icon(e)
            for e in history
            if e.action in ActionType.unread_types()
        ]
        return history

    def get_room_updates(self, roomid: RoomID, after: ActionID) -> List[Action]:
        history = self.__data.room.get_room_history(roomid, after=after)
        history = [
            self.__attachments.resolve_action_icon(e)
            for e in history
            if e.action in ActionType.update_types()
        ]
        return history

    def add_message(self, roomid: RoomID, userid: UserID, message: str) -> Optional[Action]:
        message = emoji.emojize(emoji.emojize(message, language="alias"), language="en")
        if len(message) > 64000:
            # TODO: Make this configurable on the instance.
            raise MessageServiceException("You're trying to send a message that is too long!")

        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=userid,
        )

        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.MESSAGE,
            details=message,
        )

        self.__data.room.insert_action(roomid, action)
        if action.id is not NewActionID:
            return self.__attachments.resolve_action_icon(action)
        return None

    def __infer_room_info(self, userid: UserID, room: Room) -> None:
        if room.public:
            room_name = "Unnamed Public Chat"
            room_type = RoomType.ROOM
        else:
            # Figure out how many people are in the chat, name it after them.
            occupants = self.__data.room.get_room_occupants(room.id, include_left=True)
            if not occupants:
                # This shouldn't happen, since we would have to be the sole occupant,
                # but I guess there could be a race between grabbing the rooms and occupants,
                # so let's just throw in a funny easter egg.
                room_name = "An Empty Cavern"
                room_type = RoomType.UNKNOWN
            elif len(occupants) == 1:
                room_name = "Chat with Myself"
                room_type = RoomType.CHAT
                if room.iconid is None or room.iconid in {DefaultAvatarID, DefaultRoomID}:
                    room.iconid = occupants[0].iconid
            elif len(occupants) == 2:
                not_me = [o for o in occupants if o.userid != userid]
                if len(not_me) == 1:
                    room_name = f"Chat with {not_me[0].nickname}"
                    room_type = RoomType.CHAT
                    if room.iconid is None or room.iconid in {DefaultAvatarID, DefaultRoomID}:
                        room.iconid = not_me[0].iconid
                else:
                    room_name = "Unnamed Private Chat"
                    room_type = RoomType.ROOM
            else:
                room_name = "Unnamed Private Chat"
                room_type = RoomType.ROOM

        room.type = room_type
        if not room.name:
            room.name = room_name

        if room_type == RoomType.CHAT:
            self.__attachments.resolve_chat_icon(room)
        if room_type == RoomType.ROOM:
            self.__attachments.resolve_room_icon(room)

    def create_chat(self, userid: UserID, otherid: UserID) -> Room:
        # First, find all rooms that the first user is in or was ever in.
        rooms = self.__data.room.get_joined_rooms(userid, include_left=True)

        # Now, for each of these, see if the only ones in the room are the two IDs.
        for room in rooms:
            if room.public:
                # Private chats never can go to a public room even if that only has the two of you chatting.
                continue

            occupants = self.__data.room.get_room_occupants(room.id, include_left=True)
            desired = {userid, otherid}
            if len(desired) == len(occupants):
                for occupant in occupants:
                    if occupant.userid not in desired:
                        break
                else:
                    # Found the room, just return this room after making both parties join it.
                    self.join_room(room.id, userid)
                    self.join_room(room.id, otherid)
                    self.__infer_room_info(userid, room)
                    return room

        # Now, create a new room since we don't have an existing one.
        room = Room(NewRoomID, "", "", False, None)
        self.__data.room.create_room(room)
        self.join_room(room.id, userid)
        self.join_room(room.id, otherid)
        self.__infer_room_info(userid, room)
        return room

    def join_room(self, roomid: RoomID, userid: UserID) -> None:
        self.__data.room.join_room(roomid, userid)

    def leave_room(self, roomid: RoomID, userid: UserID) -> None:
        self.__data.room.leave_room(roomid, userid)

    def update_room(
        self,
        roomid: RoomID,
        userid: UserID,
        name: Optional[str] = None,
        topic: Optional[str] = None,
        icon: Optional[bytes] = None,
    ) -> None:
        room = self.__data.room.get_room(roomid)
        if room:
            changed = False
            if name is not None:
                changed = changed or (room.name != name)
                room.name = name
            if topic is not None:
                changed = changed or (room.topic != topic)
                room.topic = topic
            if icon is not None:
                # Need to store this as a new attachment, and then get back the ID.
                img = Image.open(io.BytesIO(icon))
                width, height = img.size

                if width > AttachmentService.MAX_ICON_WIDTH or height > AttachmentService.MAX_ICON_HEIGHT:
                    raise MessageServiceException("Invalid image size for room icon")
                if width != height:
                    raise MessageServiceException("Room icon image is not square")

                content_type = img.get_format_mimetype()
                if not content_type:
                    raise MessageServiceException("Room icon image has no valid content type")

                attachmentid = self.__attachments.create_attachment(content_type)
                if attachmentid is None:
                    raise MessageServiceException("Could not insert new room icon!")
                self.__attachments.put_attachment_data(attachmentid, icon)

                changed = True
                room.iconid = attachmentid

            if room.iconid == DefaultAvatarID or room.iconid == DefaultRoomID:
                room.iconid = None

            if changed:
                self.__data.room.update_room(room, userid)

    def get_joined_rooms(self, userid: UserID) -> List[Room]:
        rooms = self.__data.room.get_joined_rooms(userid)

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            self.__infer_room_info(userid, room)

        return sorted(rooms, key=lambda r: r.last_action, reverse=True)

    def get_room_occupants(self, roomid: RoomID) -> List[Occupant]:
        occupants = [self.__attachments.resolve_occupant_icon(o) for o in self.__data.room.get_room_occupants(roomid)]
        return sorted(occupants, key=lambda o: o.nickname)

    def get_autojoin_rooms(self, userid: UserID) -> List[Room]:
        rooms = self.__data.room.get_autojoin_rooms()

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            self.__infer_room_info(userid, room)

        return sorted(rooms, key=lambda r: r.name)

    def join_autojoin_rooms(self, userid: UserID) -> None:
        rooms = self.__data.room.get_autojoin_rooms()
        for room in rooms:
            self.__data.room.join_room(room.id, userid)

    def get_public_rooms(self) -> List[Room]:
        rooms = self.__data.room.get_public_rooms()
        for room in rooms:
            self.__infer_room_info(NewUserID, room)
        return rooms

    def get_matching_rooms(self, userid: UserID, *, name: Optional[str] = None) -> List[RoomSearchResult]:
        # First get the list of rooms that we can see based on our user ID (joined rooms).
        inrooms = self.__data.room.get_matching_rooms(userid, name=name)
        memberof = {r.id for r in inrooms}

        # Now look up all the rooms we COULD join based on our permissions.
        potentialrooms = self.__data.room.get_visible_rooms(userid, name=name)

        # Merge them down to one, prioritizing joined over potential.
        rooms_by_id = {r.id: r for r in potentialrooms}
        for room in inrooms:
            rooms_by_id[room.id] = room
        rooms = [val for _, val in rooms_by_id.items()]

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            self.__infer_room_info(userid, room)

        # Now, filter out any rooms that still don't meet our criteria.
        if name:
            lowername = name.lower()
            rooms = [r for r in rooms if lowername in r.name.lower()]
        rooms = sorted(rooms, key=lambda r: r.name)

        # Now, look up all users we could chat with, given our criteria.
        potentialusers = sorted(
            self.__data.user.get_visible_users(userid, name=name),
            key=lambda u: u.nickname,
        )

        for user in potentialusers:
            self.__attachments.resolve_user_icon(user)

        # Now, combined the two.
        results: List[RoomSearchResult] = []
        for room in rooms:
            icon = room.icon
            if not icon:
                raise Exception("Logic error, should have been inferred above!")
            if room.id in memberof:
                results.append(RoomSearchResult(room.name, True, room.public, room.id, None, icon))
            else:
                results.append(RoomSearchResult(room.name, False, room.public, room.id, None, icon))
        for user in potentialusers:
            icon = user.icon
            if not icon:
                raise Exception("Logic error, should have been inferred above!")
            results.append(RoomSearchResult(user.nickname, False, False, None, user.id, icon))

        return results
