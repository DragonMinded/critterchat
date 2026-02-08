import emoji
from typing import Dict, Final, List, Optional, Set

from ..config import Config
from ..common import Time
from ..data import (
    Data,
    Action,
    ActionType,
    Attachment,
    Occupant,
    Room,
    RoomPurpose,
    RoomSearchResult,
    User,
    UserPermission,
    DefaultAvatarID,
    DefaultRoomID,
    FaviconID,
    NewOccupantID,
    NewActionID,
    NewRoomID,
    NewUserID,
    ActionID,
    AttachmentID,
    OccupantID,
    RoomID,
    UserID,
)
from .attachment import AttachmentService


class MessageServiceException(Exception):
    pass


class MessageService:
    MAX_HISTORY: Final[int] = 100

    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__attachments = AttachmentService(self.__config, self.__data)

    def migrate_legacy_names(self) -> None:
        # TODO: Once the implementation for per-room nicknames is done, this will need to
        # sweep those and ensure they're not messed up. This mostly handles checking for
        # old exploits and deleting nicknames that are no longer allowed which reverts the
        # user back to their globally-set nickname or username if unset.

        # Don't check for whether this migration ran, we want it to run every restart.
        pass

    def _resolve_attachments(self, actions: List[Action]) -> List[Action]:
        ids = {a.id for a in actions}
        if not ids:
            return actions

        actionmap = self.__data.attachment.get_action_attachments(ids)
        for action in actions:
            actionattachments = actionmap[action.id]

            attachments: List[Attachment] = []
            for actionattachment in actionattachments:
                attachments.append(
                    Attachment(
                        actionattachment.attachmentid,
                        self.__attachments.get_attachment_url(actionattachment.attachmentid),
                        actionattachment.content_type,
                        actionattachment.metadata,
                    )
                )
            action.attachments = attachments
        return actions

    def get_last_action(self) -> Optional[ActionID]:
        return self.__data.room.get_last_action()

    def get_last_room_action(self, roomid: RoomID) -> Optional[Action]:
        history = self.__data.room.get_room_history(roomid, limit=1)
        history = self._resolve_attachments(history)
        return self.__attachments.resolve_action_icon(history[0]) if history else None

    def get_room_history(self, roomid: RoomID, before: Optional[ActionID] = None) -> List[Action]:
        room = self.__data.room.get_room(roomid)
        if not room:
            return []

        history = self.__data.room.get_room_history(room.id, before=before, limit=self.MAX_HISTORY)
        history = self._resolve_attachments(history)
        history = [
            self.__attachments.resolve_action_icon(e)
            for e in history
            # We intentionally over-fetch joins/leaves for DMs here, because the "load more history"
            # component needs to know if there's any more history, and it does that by comparing
            # its own list of events to the oldest event to see if there's anything more to load. If
            # we filter out the first events (a join in every case) for DMs, it never knows to stop
            # showing the load more indicator.
            if e.action in ActionType.unread_types()
        ]
        return history

    def get_room_updates(self, roomid: RoomID, after: ActionID) -> List[Action]:
        history = self.__data.room.get_room_history(roomid, after=after)
        history = self._resolve_attachments(history)
        history = [
            self.__attachments.resolve_action_icon(e)
            for e in history
            if e.action in ActionType.update_types()
        ]
        return history

    def add_message(
        self,
        roomid: RoomID,
        userid: UserID,
        message: str,
        sensitive: bool,
        attachments: List[AttachmentID],
    ) -> Optional[Action]:
        message = emoji.emojize(emoji.emojize(message, language="alias"), language="en")
        if len(message) > self.__config.limits.message_length:
            raise MessageServiceException("You're trying to send a message that is too long!")

        # First, ensure that DMs re-open when messaging the other user again.
        self.rejoin_direct_message(roomid)

        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=userid,
        )

        messagedata: Dict[str, object] = {"message": message}
        if sensitive:
            messagedata["sensitive"] = True

        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.MESSAGE,
            details=messagedata,
        )

        attachmentids: List[AttachmentID] = []
        response_attachments: List[Attachment] = []
        for attachment in attachments:
            adata = self.__data.attachment.lookup_attachment(attachment)
            if adata is None:
                # Skip adding this attachment.
                continue

            if adata.content_type not in AttachmentService.SUPPORTED_IMAGE_TYPES:
                # Trying to sneak a bad attachment in.
                continue

            attachmentids.append(adata.id)
            response_attachments.append(
                Attachment(
                    adata.id,
                    self.__attachments.get_attachment_url(adata.id),
                    adata.content_type,
                    adata.metadata,
                )
            )

        if len(attachmentids) != len(response_attachments):
            raise Exception("Logic error, mismatched message attachment structures!")

        # Locking a bunch of tables is expensive, so only do it when we really need to be atomic.
        if attachmentids:
            with self.__data.room.lock_actions():
                self.__data.room.insert_action(roomid, action)

                with self.__data.attachment.lock_action_attachments():
                    for attachmentid in attachmentids:
                        self.__data.attachment.link_action_attachment(action.id, attachmentid)
        else:
            self.__data.room.insert_action(roomid, action)

        action.attachments = response_attachments
        if action.id is not NewActionID:
            return self.__attachments.resolve_action_icon(action)
        return None

    def lookup_occupant(self, occupantid: OccupantID) -> Optional[User]:
        occupant = self.__data.room.get_room_occupant(occupantid)
        if not occupant:
            return None

        # Grab generic info for user based on occupant.
        user = self.__data.user.get_user(occupant.userid)
        if not user:
            return None

        # Copy the data over so the client can display it.
        user.iconid = occupant.iconid
        user.nickname = occupant.nickname
        user.occupantid = occupantid
        user.moderator = occupant.moderator
        self.__attachments.resolve_user_icon(user)
        return user

    def grant_room_moderator(self, roomid: RoomID, userid: UserID) -> None:
        user = self.__data.user.get_user(userid)
        if not user:
            raise MessageServiceException("User not found!")

        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("Room not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot grant moderator for user in non-public room!")

        self.__data.room.grant_room_moderator(room.id, user.id)

    def revoke_room_moderator(self, roomid: RoomID, userid: UserID) -> None:
        user = self.__data.user.get_user(userid)
        if not user:
            raise MessageServiceException("User not found!")

        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("Room not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot revoke moderator for occupant in non-public room!")

        self.__data.room.revoke_room_moderator(room.id, user.id)

    def grant_occupant_moderator(self, occupantid: OccupantID) -> None:
        occupant = self.__data.room.get_room_occupant(occupantid)
        if not occupant:
            raise MessageServiceException("Occupant not found!")

        room = self.__data.room.get_occupant_room(occupantid)
        if not room:
            raise MessageServiceException("Occupant not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot grant moderator for occupant in non-public room!")

        self.__data.room.grant_room_moderator(room.id, occupant.userid)

    def revoke_occupant_moderator(self, occupantid: OccupantID) -> None:
        occupant = self.__data.room.get_room_occupant(occupantid)
        if not occupant:
            raise MessageServiceException("Occupant not found!")

        room = self.__data.room.get_occupant_room(occupantid)
        if not room:
            raise MessageServiceException("Occupant not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot revoke moderator for occupant in non-public room!")

        self.__data.room.revoke_room_moderator(room.id, occupant.userid)

    def __infer_room_info(self, userid: UserID, room: Room) -> None:
        if room.purpose == RoomPurpose.ROOM:
            room_name = "Unnamed Public Chat"
            occupants = self.__data.room.get_room_occupants(room.id)
        elif room.purpose == RoomPurpose.CHAT:
            room_name = "Unnamed Private Chat"
            occupants = self.__data.room.get_room_occupants(room.id)
        else:
            # Figure out how many people are in the direct message, name it after them.
            occupants = self.__data.room.get_room_occupants(room.id, include_left=True)
            if not occupants:
                # This shouldn't happen, since we would have to be the sole occupant,
                # but I guess there could be a race between grabbing the rooms and occupants,
                # so let's just throw in a funny easter egg.
                room_name = "An Empty Cavern"
            elif len(occupants) == 1:
                room_name = "Chat with Myself"
                if room.iconid is None or room.iconid in {DefaultAvatarID, DefaultRoomID}:
                    room.iconid = occupants[0].iconid
                room.deficonid = occupants[0].iconid
            elif len(occupants) == 2:
                not_me = [o for o in occupants if o.userid != userid]
                if len(not_me) == 1:
                    room_name = f"Chat with {not_me[0].nickname}"
                    if room.iconid is None or room.iconid in {DefaultAvatarID, DefaultRoomID}:
                        room.iconid = not_me[0].iconid
                    room.deficonid = not_me[0].iconid
                else:
                    room_name = "Unnamed Private Chat"
            else:
                # This should never happen, but let's account for it anyway.
                room_name = "Unnamed Private Chat"

        room.occupants = occupants
        if not room.name:
            room.name = room_name

        if room.purpose in {RoomPurpose.CHAT, RoomPurpose.DIRECT_MESSAGE}:
            self.__attachments.resolve_chat_icon(room)
        elif room.purpose == RoomPurpose.ROOM:
            self.__attachments.resolve_room_icon(room)
        else:
            raise Exception("Logic error, unexpected room purpose!")

    def create_public_room(
        self,
        name: str,
        topic: str,
        icon: Optional[AttachmentID],
        autojoin: bool = False,
        moderated: bool = False,
    ) -> Room:
        # Create a new public room, possibly with auto-join enabled, and return it. If auto-join is
        # enabled then join all existing users to the room after creating.
        room = Room(NewRoomID, name, topic, RoomPurpose.ROOM, moderated, icon, None)
        self.__data.room.create_room(room)

        if autojoin:
            self.__data.room.set_room_autojoin(room.id, True)

            for user in self.__data.user.get_users():
                if UserPermission.ACTIVATED not in user.permissions:
                    continue

                self.__data.room.join_room(room.id, user.id)
        else:
            self.__data.room.set_room_autojoin(room.id, False)

        # Finally, return the room.
        return room

    def lookup_room(self, roomid: RoomID, userid: UserID) -> Optional[Room]:
        room = self.__data.room.get_room(roomid)
        if room:
            self.__infer_room_info(userid, room)
        return room

    def update_public_room_autojoin(self, roomid: RoomID, autojoin: bool) -> Room:
        # First, look up the room, making sure it exists.
        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("Room does not exist!")

        # Next, only allow changes to public rooms.
        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Room is not public!")

        # Grab info, update the autojoin property.
        self.__infer_room_info(NewUserID, room)
        self.__data.room.set_room_autojoin(room.id, autojoin)

        # Finally, return the room.
        return room

    def update_public_room_moderated(self, roomid: RoomID, userid: UserID, moderated: bool) -> Room:
        # First, look up the room, making sure it exists.
        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("Room does not exist!")

        # Next, only allow changes to public rooms.
        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Room is not public!")

        # Only change room's details if it's actually changing.
        if room.moderated == moderated:
            return room

        room.moderated = moderated
        self.__data.room.update_room(room, userid)

        # Finally, return the updated room.
        return room

    def create_direct_message(self, userid: UserID, otherid: UserID) -> Room:
        # First, find all rooms that the first user is in or was ever in.
        rooms = self.__data.room.get_joined_rooms(userid, include_left=True)

        # Now, for each of these, see if the only ones in the room are the two IDs.
        for room in rooms:
            if room.purpose != RoomPurpose.DIRECT_MESSAGE:
                # Private chats never can go to a public room or a group chat even
                # if that only has the two of you chatting.
                continue

            occupants = self.__data.room.get_room_occupants(room.id, include_left=True)
            desired = {userid, otherid}
            if len(desired) == len(occupants):
                for occupant in occupants:
                    if occupant.userid not in desired:
                        break
                else:
                    # Found the room, just return this room after making both parties join it.
                    self.__data.room.join_room(room.id, userid)
                    self.__data.room.shadow_join_room(room.id, otherid)
                    self.__infer_room_info(userid, room)
                    return room

        # Now, create a new room since we don't have an existing one.
        room = Room(NewRoomID, "", "", RoomPurpose.DIRECT_MESSAGE, False, None, None)
        self.__data.room.create_room(room)
        self.__data.room.join_room(room.id, userid)
        self.__data.room.shadow_join_room(room.id, otherid)
        self.__infer_room_info(userid, room)
        return room

    def rejoin_direct_message(self, roomid: RoomID) -> None:
        # Ensure that the room exists and is a direct message.
        room = self.__data.room.get_room(roomid)
        if room is None or room.purpose != RoomPurpose.DIRECT_MESSAGE:
            return

        # Join all occupants including left occupants to the room so they can receive
        # an incoming message.
        occupants = self.__data.room.get_room_occupants(room.id, include_left=True)
        for occupant in occupants:
            self.__data.room.join_room(room.id, occupant.userid)

    def join_room(self, roomid: RoomID, userid: UserID) -> None:
        # First, check permissions for the room the user is trying to join, to ensure
        # we can't pull any shenanigans and try to join a private room or chat we don't
        # have an invite to.
        room = self.__data.room.get_room(roomid)
        if (room is None) or (not room.public):
            raise MessageServiceException("Room does not exist!")

        self.__data.room.join_room(room.id, userid)

    def leave_room(self, roomid: RoomID, userid: UserID) -> None:
        self.__data.room.leave_room(roomid, userid)

    def update_room(
        self,
        roomid: RoomID,
        userid: UserID,
        name: Optional[str] = None,
        topic: Optional[str] = None,
        moderated: Optional[bool] = None,
        icon: Optional[AttachmentID] = None,
        icon_delete: bool = False,
    ) -> None:
        # Sanitize inputs.
        if icon == DefaultAvatarID or icon == DefaultRoomID or icon == FaviconID:
            icon = None
        if icon is not None:
            icondata = self.__data.attachment.lookup_attachment(icon)
            if icondata is None:
                # Skip adding this icon, it's not valid.
                raise MessageServiceException("Updated room icon is not valid!")

            if icondata.content_type not in AttachmentService.SUPPORTED_IMAGE_TYPES:
                # Trying to sneak a bad attachment in.
                raise MessageServiceException("Updated room icon is not valid!")

        room = self.__data.room.get_room(roomid)
        if room:
            changed = False
            old_icon = room.iconid

            # Update only if we changed name/topic.
            if name is not None:
                changed = changed or (room.name != name)
                room.name = name
            if topic is not None:
                changed = changed or (room.topic != topic)
                room.topic = topic
            if moderated is not None:
                changed = changed or (room.moderated != moderated)
                room.moderated = moderated

            # Allow updating icon or deleting icon.
            if icon is not None:
                room.iconid = icon
            elif icon_delete:
                room.iconid = None

            # Calculate whether we changed the icon.
            if room.iconid == DefaultAvatarID or room.iconid == DefaultRoomID or room.iconid == FaviconID:
                room.iconid = None
            if room.iconid != old_icon:
                changed = True

            if changed:
                self.__data.room.update_room(room, userid)

    def get_joined_rooms(self, userid: UserID) -> List[Room]:
        rooms = self.__data.room.get_joined_rooms(userid)

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            self.__infer_room_info(userid, room)

        return sorted(rooms, key=lambda r: r.last_action_timestamp, reverse=True)

    def get_room_occupants(self, roomid: RoomID) -> List[Occupant]:
        room = self.__data.room.get_room(roomid)
        if not room:
            return []

        occupants = [
            self.__attachments.resolve_occupant_icon(o)
            for o in self.__data.room.get_room_occupants(roomid, include_left=room.purpose == RoomPurpose.DIRECT_MESSAGE)
        ]
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

    def get_public_rooms(self, userid: UserID) -> List[Room]:
        rooms = self.__data.room.get_public_rooms()
        for room in rooms:
            self.__infer_room_info(userid, room)
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

        # Now, figure out all of the private conversations that we shouldn't duplicate users for.
        ignored: Set[UserID] = set()
        for room in rooms:
            if room.purpose != RoomPurpose.DIRECT_MESSAGE:
                continue
            if len(room.occupants) == 1:
                ignored.add(room.occupants[0].userid)
            elif len(room.occupants) == 2:
                not_me = [o for o in room.occupants if o.userid != userid]
                ignored.add(not_me[0].userid)

        # Now, look up all users we could chat with, given our criteria.
        potentialusers = sorted(
            self.__data.user.get_visible_users(userid, name=name),
            key=lambda u: u.nickname,
        )

        # Now, filter out any users that we've already got a chat with.
        potentialusers = [u for u in potentialusers if u.id not in ignored]

        # Now, resolve the icons of anyone left.
        for user in potentialusers:
            self.__attachments.resolve_user_icon(user)

        # Finally, combined the two.
        results: List[RoomSearchResult] = []
        for room in rooms:
            icon = room.icon
            handle: Optional[str] = None
            if room.purpose == RoomPurpose.DIRECT_MESSAGE:
                if len(room.occupants) == 1:
                    handle = "@" + room.occupants[0].username
                elif len(room.occupants) == 2:
                    not_me = [o for o in room.occupants if o.userid != userid]
                    handle = "@" + not_me[0].username

            if not icon:
                raise Exception("Logic error, should have been inferred above!")

            if room.id in memberof:
                results.append(RoomSearchResult(room.name, handle, room.purpose, True, room.id, None, icon))
            else:
                results.append(RoomSearchResult(room.name, handle, room.purpose, False, room.id, None, icon))
        for user in potentialusers:
            icon = user.icon
            if not icon:
                raise Exception("Logic error, should have been inferred above!")
            results.append(RoomSearchResult(user.nickname, f"@{user.username}", RoomPurpose.DIRECT_MESSAGE, False, None, user.id, icon))

        return results
