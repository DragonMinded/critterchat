from typing import Final, Literal, cast

from ..config import Config
from ..common import Time, emojize
from ..data import (
    Data,
    Action,
    ActionType,
    Attachment,
    Invite,
    Occupant,
    Room,
    RoomPurpose,
    SearchResult,
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
    InviteID,
    OccupantID,
    RoomID,
    UserID,
)
from .attachment import AttachmentService
from .emote import EmoteService
from .user import UserService


class MessageServiceException(Exception):
    pass


class MessageService:
    # Maximum number of displayable events we pull on first load of a chat.
    MAX_HISTORY: Final[int] = 100

    # Number of seconds in which only the inviter can cancel an invite.
    INVITE_SELF_CANCEL_GRACE_PERIOD_SECONDS: Final[int] = Time.SECONDS_IN_DAY * 3

    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data
        self.__user = UserService(self.__config, self.__data)
        self.__attachments = AttachmentService(self.__config, self.__data)
        self.__emotes = EmoteService(self.__config, self.__data)

    def migrate_legacy_names(self) -> None:
        # TODO: Once the implementation for per-room nicknames is done, this will need to
        # sweep those and ensure they're not messed up. This mostly handles checking for
        # old exploits and deleting nicknames that are no longer allowed which reverts the
        # user back to their globally-set nickname or username if unset.

        # Don't check for whether this migration ran, we want it to run every restart.
        pass

    def _resolve_attachments(self, actions: list[Action]) -> list[Action]:
        ids = {a.id for a in actions}
        if not ids:
            return actions

        actionmap = self.__data.attachment.get_action_attachments(ids)
        for action in actions:
            actionattachments = actionmap[action.id]

            attachments: list[Attachment] = []
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

    def get_last_action(self) -> ActionID | None:
        return self.__data.room.get_last_action()

    def get_room_history(self, roomid: RoomID, before: ActionID | None = None) -> list[Action]:
        room = self.__data.room.get_room(roomid)
        if not room:
            return []

        # We intentionally over-fetch joins/leaves for DMs here, because the "load more history"
        # component needs to know if there's any more history, and it does that by comparing
        # its own list of events to the oldest event to see if there's anything more to load. If
        # we filter out the first events (a join in every case) for DMs, it never knows to stop
        # showing the load more indicator.
        history = self.__data.room.get_room_history(
            room.id,
            before=before,
            types=ActionType.unread_types(),
            limit=self.MAX_HISTORY,
        )
        history = self._resolve_attachments(history)
        history = [self.__attachments.resolve_action_icon(e) for e in history]
        return history

    def get_room_updates(self, roomid: RoomID, after: ActionID) -> list[Action]:
        history = self.__data.room.get_room_history(roomid, after=after, types=ActionType.update_types())
        history = self._resolve_attachments(history)
        history = [self.__attachments.resolve_action_icon(e) for e in history]
        return history

    def add_message(
        self,
        roomid: RoomID,
        userid: UserID,
        message: str,
        sensitive: bool,
        attachments: list[AttachmentID],
    ) -> Action | None:
        # Ensure we're not trying to send too much text.
        message = emojize(message)
        if len(message) > self.__config.limits.message_length:
            raise MessageServiceException("You're trying to send a message that is too long!")

        # Now, make sure the room is valid.
        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("You cannot message a room that does not exist!")

        # Now, make sure the user adding to the room is here and not muted.
        occupants = self.__data.room.get_room_occupants(room.id, room.purpose == RoomPurpose.DIRECT_MESSAGE)
        for occupant in occupants:
            if occupant.userid == userid:
                if occupant.muted:
                    raise MessageServiceException("You are muted!")
                break
        else:
            raise MessageServiceException("You cannot message a room that you are not a member of!")

        # Now that we've passed checks, ensure that DMs re-open when messaging the other user again.
        self.rejoin_direct_message(roomid)

        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=userid,
        )

        messagedata: dict[str, object] = {"message": message, "reactions": {}}
        if sensitive:
            messagedata["sensitive"] = True

        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.MESSAGE,
            details=messagedata,
        )

        attachmentids: list[AttachmentID] = []
        response_attachments: list[Attachment] = []
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

    def lookup_action(self, actionid: ActionID) -> Action | None:
        if actionid not in self.__data.requestcache.actions:
            self.__data.requestcache.actions[actionid] = self.__data.room.get_action(actionid)
        return self.__data.requestcache.actions[actionid]

    def validate_reaction(self, reaction: str) -> bool:
        if not reaction:
            return False
        if reaction[0] != ":" or reaction[-1] != ":":
            return False
        actual = reaction[1:-1]

        # First, see if it is one of the valid emojis we have in our category list.
        if actual in self.__emotes.get_all_emojis():
            return True

        # Now, see if it is a custom emote.
        if self.__emotes.validate_emote(actual):
            return True

        # Wasn't a custom emote, nor one of our emojis. Reject it.
        return False

    def add_reaction(self, userid: UserID, actionid: ActionID, reaction: str) -> None:
        self._modify_reaction(userid, actionid, reaction, "add")

    def remove_reaction(self, userid: UserID, actionid: ActionID, reaction: str) -> None:
        self._modify_reaction(userid, actionid, reaction, "remove")

    def _modify_reaction(self, userid: UserID, actionid: ActionID, reaction: str, delta: Literal["add", "remove"]) -> None:
        # Verify that the reaction is a valid emote or emoji that we recognize.
        if not self.validate_reaction(reaction):
            return

        with self.__data.room.lock_actions():
            # Grab the action that we're about to modify.
            action = self.__data.room.get_action(actionid)
            if not action:
                raise MessageServiceException("You cannot react to a nonexistent message!")

            # Make sure we're allowed to add a reaction to the message.
            if action.action not in {ActionType.MESSAGE} or not action.occupant:
                raise MessageServiceException("You cannot react to something that isn't a message!")

            # Now, make sure the room is valid.
            room = self.__data.room.get_occupant_room(action.occupant.id)
            if not room:
                raise MessageServiceException("You cannot react to a message in a nonexistent room!")

            # And, make sure the user adding to the room is here and not muted.
            occupants = self.__data.room.get_room_occupants(room.id)
            myself: Occupant
            for occupant in occupants:
                if occupant.userid == userid:
                    myself = occupant
                    if occupant.muted:
                        raise MessageServiceException("You are muted!")
                    break
            else:
                raise MessageServiceException("You cannot react to a message in a room that you are not a member of!")

            # Alright. Now, let's actually modify the reaction table. We store reactions keyed by
            # the reaction itself, and instead of just a count the value is the list of occupants that
            # reacted to that message with that reaction. That way, clients can show who reacted
            # with what and you can remove reactions that you'd added previously.
            reactions = cast(dict[str, list[OccupantID]], action.details.get("reactions", {}))
            ordering = cast(list[str], action.details.get("reactions_order", []))
            for er in reactions:
                if er not in ordering:
                    ordering.append(er)

            modified = False
            if reaction not in reactions:
                if delta == "add":
                    # We're adding, so that's easy.
                    reactions[reaction] = [myself.id]
                    ordering.append(reaction)
                    modified = True

            else:
                existing = reactions[reaction]
                if delta == "add":
                    # Only modify if we don't already have this reaction.
                    if occupant.id not in existing:
                        existing.append(occupant.id)
                        modified = True

                else:
                    # Only modify if we already have this reaction.
                    if occupant.id in existing:
                        existing = [e for e in existing if e != occupant.id]
                        modified = True

                if existing:
                    reactions[reaction] = existing
                else:
                    del reactions[reaction]

            # Always make sure the ordering doesn't include reactions that don't exist.
            ordering = [o for o in ordering if o in reactions]

            if modified:
                # Finally, if we actually modified a reaction, then save it and generate an
                # action for updating clients.
                action.details["reactions"] = reactions
                action.details["reactions_order"] = ordering
                self.__data.room.update_action(action)

                # Generate the action that says we modified a message.
                action = Action(
                    actionid=NewActionID,
                    timestamp=Time.now(),
                    occupant=myself,
                    action=ActionType.CHANGE_MESSAGE,
                    # For this action, the details will be filled in at look-up time.
                    details={"actionid": action.id, "edited": ["reactions"], delta: reaction},
                )

                self.__data.room.insert_action(room.id, action)

    def lookup_occupant(self, occupantid: OccupantID, userid: UserID) -> User | None:
        occupant = self.__data.room.get_room_occupant(occupantid)
        if not occupant:
            return None

        # Grab generic info for user based on occupant.
        user = self.__data.user.get_user(occupant.userid)
        if not user:
            return None

        # Grab invite information, based on other occupant that sent invite.
        if occupant.invite:
            occupant.invite.user = self.__data.user.get_user(occupant.invite.userid)

            # Person looking this up can cancel if it's been > 72 hours since the invite was issued
            # or they were the one that invited the user.
            occupant.invite.cancellable = (
                occupant.invite.userid == userid or
                (occupant.invite.timestamp + self.INVITE_SELF_CANCEL_GRACE_PERIOD_SECONDS) < Time.now()
            )

            # In this case, we need to look up the occupant info of this user, because
            # they could have a different nickname in this particular room.
            if occupant.invite.user:
                room = self.__data.room.get_occupant_room(occupant.id)
                if room:
                    occupants = {
                        o.userid: o
                        for o in self.__data.room.get_room_occupants(room.id, include_left=True)
                    }
                    if occupant.invite.userid in occupants:
                        occupant.invite.user.nickname = occupants[occupant.invite.userid].nickname
                        occupant.invite.user.iconid = occupants[occupant.invite.userid].iconid

                self.__attachments.resolve_user_icon(occupant.invite.user)

        # Copy the data over so the client can display it.
        user.iconid = occupant.iconid
        user.nickname = occupant.nickname
        user.occupantid = occupantid
        user.moderator = occupant.moderator
        user.muted = occupant.muted
        user.inactive = occupant.inactive
        user.invite = occupant.invite
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

    def mute_occupant(self, occupantid: OccupantID) -> None:
        occupant = self.__data.room.get_room_occupant(occupantid)
        if not occupant:
            raise MessageServiceException("Occupant not found!")

        room = self.__data.room.get_occupant_room(occupantid)
        if not room:
            raise MessageServiceException("Occupant not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot mute occupant in non-public room!")

        self.__data.room.mute_room_occupant(room.id, occupant.userid)

    def unmute_occupant(self, occupantid: OccupantID) -> None:
        occupant = self.__data.room.get_room_occupant(occupantid)
        if not occupant:
            raise MessageServiceException("Occupant not found!")

        room = self.__data.room.get_occupant_room(occupantid)
        if not room:
            raise MessageServiceException("Occupant not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot unmute occupant in non-public room!")

        self.__data.room.unmute_room_occupant(room.id, occupant.userid)

    def mute_room_user(self, roomid: RoomID, userid: UserID) -> None:
        user = self.__data.user.get_user(userid)
        if not user:
            raise MessageServiceException("User not found!")

        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("Occupant not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot mute occupant in non-public room!")

        self.__data.room.mute_room_occupant(room.id, user.id)

    def unmute_room_user(self, roomid: RoomID, userid: UserID) -> None:
        user = self.__data.user.get_user(userid)
        if not user:
            raise MessageServiceException("User not found!")

        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("Occupant not found!")

        if room.purpose != RoomPurpose.ROOM:
            raise MessageServiceException("Cannot unmute occupant in non-public room!")

        self.__data.room.unmute_room_occupant(room.id, user.id)

    def __infer_room_info(self, userid: UserID, room: Room) -> None:
        if room.purpose == RoomPurpose.ROOM:
            room_name = "Unnamed Public Room"
            occupants = self.__data.room.get_room_occupants(room.id, include_invited=True)
        elif room.purpose == RoomPurpose.CHAT:
            room_name = "Unnamed Private Conversation"
            occupants = self.__data.room.get_room_occupants(room.id, include_invited=True)
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
                    # This should not happen, but let's account for it anyway.
                    room_name = "Unnamed Private Conversation"
            else:
                # This should never happen, but let's account for it anyway.
                room_name = "Unnamed Private Conversation"

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
        icon: AttachmentID | None,
        autojoin: bool = False,
        moderated: bool = False,
    ) -> Room:
        # Create a new public room, possibly with auto-join enabled, and return it. If auto-join is
        # enabled then join all existing users to the room after creating.
        room = Room(NewRoomID, name, topic, RoomPurpose.ROOM, moderated, False, icon, None)
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

    def create_private_chat(self, userid: UserID) -> Room:
        # Create a new private group chat.
        room = Room(NewRoomID, "", "", RoomPurpose.CHAT, False, False, None, None)
        self.__data.room.create_room(room)
        self.__data.room.join_room(room.id, userid)

        # Fetch room info so we can grab occupants.
        self.__infer_room_info(userid, room)
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
        room = Room(NewRoomID, "", "", RoomPurpose.DIRECT_MESSAGE, False, False, None, None)
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

    def lookup_room(self, roomid: RoomID, userid: UserID) -> Room | None:
        room = self.__data.room.get_room(roomid)
        if room:
            self.__infer_room_info(userid, room)
            self.__data.requestcache.occupants[roomid] = room.occupants
        else:
            self.__data.requestcache.occupants[roomid] = None

        return room

    def get_room_occupants(self, roomid: RoomID, userid: UserID) -> list[Occupant] | None:
        if roomid not in self.__data.requestcache.occupants:
            room = self.lookup_room(roomid, userid)
            if room:
                occupants = [
                    self.__attachments.resolve_occupant_icon(o)
                    for o in room.occupants
                ]
                self.__data.requestcache.occupants[roomid] = occupants
            else:
                self.__data.requestcache.occupants[roomid] = None

        return self.__data.requestcache.occupants[roomid]

    def get_occupant_room(self, occupantid: OccupantID) -> Room | None:
        occupant = self.__data.room.get_room_occupant(occupantid)
        if not occupant:
            return None

        room = self.__data.room.get_occupant_room(occupantid)
        if not room:
            return None

        self.__infer_room_info(occupant.userid, room)
        return room

    def update_public_room_autojoin(self, roomid: RoomID, userid: UserID, autojoin: bool) -> Room:
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

        # Figure out if we need to add people to the room.
        changed = room.autojoin != autojoin
        room.autojoin = autojoin

        if changed and room.autojoin:
            for user in self.__data.user.get_users():
                if UserPermission.ACTIVATED not in user.permissions:
                    continue

                self.__data.room.join_room(room.id, user.id)

        if changed:
            # Trigger an action so any clients that are admins can see the updated value.
            self.__data.room.update_room(room, userid)

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

    def join_room(self, roomid: RoomID, userid: UserID) -> None:
        # First, check permissions for the room the user is trying to join, to ensure
        # we can't pull any shenanigans and try to join a private room or chat we don't
        # have an invite to.
        room = self.__data.room.get_room(roomid)
        if room is None:
            raise MessageServiceException("Room does not exist!")

        if not room.public:
            if room.purpose == RoomPurpose.DIRECT_MESSAGE:
                # Verify that we're a participant in this direct message.
                occupants = self.__data.room.get_room_occupants(room.id, include_left=True)
                for occupant in occupants:
                    if occupant.userid == userid:
                        break
                else:
                    # This is somebody else's DM?! Get outta here!
                    raise MessageServiceException("Room does not exist!")

            elif room.purpose == RoomPurpose.CHAT:
                # Verify that we're already in the private message, or that we have an invite to
                # join this room.
                in_chat_already = False
                occupants = self.__data.room.get_room_occupants(room.id)
                for occupant in occupants:
                    if occupant.userid == userid:
                        in_chat_already = True

                # Check if the user has an invite to a non-public chat, and let them in if they do.
                if not in_chat_already and not self.__data.room.is_invited_to_room(room.id, userid):
                    raise MessageServiceException("Room does not exist!")

        self.__data.room.join_room(room.id, userid)

    def leave_room(self, roomid: RoomID, userid: UserID) -> None:
        self.__data.room.leave_room(roomid, userid)

    def update_room(
        self,
        roomid: RoomID,
        userid: UserID,
        name: str | None = None,
        topic: str | None = None,
        moderated: bool | None = None,
        autojoin: bool | None = None,
        icon: AttachmentID | None = None,
        icon_delete: bool = False,
    ) -> None:
        # First, make sure the room is valid.
        room = self.__data.room.get_room(roomid)
        if not room:
            raise MessageServiceException("You cannot update a room that does not exist!")
        occupants = self.__data.room.get_room_occupants(room.id, room.purpose == RoomPurpose.DIRECT_MESSAGE)

        # Now, make sure the user adding to the room is here and not muted.
        for occupant in occupants:
            if occupant.userid == userid:
                if occupant.muted:
                    raise MessageServiceException("You are muted!")
                break
        else:
            raise MessageServiceException("You cannot update a room that you are not a member of!")

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

        # Do this before the room update itself because otherwise the person doing the autojoin
        # update might not get the changed property. This action will join everyone to the room
        # who is not in the room before saving the room update. Force an update so the client gets
        # notified.
        if autojoin is not None:
            if autojoin != room.autojoin and room.purpose == RoomPurpose.ROOM:
                self.update_public_room_autojoin(room.id, userid, autojoin)
                changed = True

        if changed:
            self.__data.room.update_room(room, userid)

    def get_last_invite_update(self) -> tuple[int, int] | None:
        return self.__data.room.get_last_invite_update()

    def has_updated_invites(self, userid: UserID, last_checked: int, last_length: int) -> bool:
        return self.__data.room.has_updated_invites(userid, last_checked, last_length)

    def invite_to_room(self, roomid: RoomID, inviter: UserID, invited: UserID) -> None:
        room = self.__data.room.get_room(roomid)
        if room is None:
            raise MessageServiceException("Room does not exist!")

        # Verify that we're a participant in this room, can't be inviting to rooms we're not in.
        occupants = self.__data.room.get_room_occupants(room.id)
        for occupant in occupants:
            if occupant.userid == inviter:
                break
        else:
            # This is somebody else's room?! You can't invite to this!
            raise MessageServiceException("Room does not exist!")

        if room.purpose not in {RoomPurpose.ROOM, RoomPurpose.CHAT}:
            raise MessageServiceException("Cannot invite to this room!")

        self.__data.room.grant_room_invite(roomid, inviterid=inviter, invitedid=invited)

    def uninvite_to_room(self, roomid: RoomID, inviter: UserID, invited: UserID) -> None:
        room = self.__data.room.get_room(roomid)
        if room is None:
            raise MessageServiceException("Room does not exist!")

        # Verify that we're a participant in this room, can't be inviting to rooms we're not in.
        occupants = self.__data.room.get_room_occupants(room.id)
        for occupant in occupants:
            if occupant.userid == inviter:
                break
        else:
            # This is somebody else's room?! You can't invite to this!
            raise MessageServiceException("Room does not exist!")

        if room.purpose not in {RoomPurpose.ROOM, RoomPurpose.CHAT}:
            raise MessageServiceException("Cannot uninvite from this room!")

        # Ensure that you are actually allowed to uninvite this person.
        invites = [inv for inv in self.__data.room.get_room_invites(invited) if inv.room and inv.room.id == roomid]
        if not invites:
            raise MessageServiceException("Cannot uninvite from this room!")

        invite = invites[0]
        cancellable = (
            invite.userid == inviter or
            (invite.timestamp + self.INVITE_SELF_CANCEL_GRACE_PERIOD_SECONDS) < Time.now()
        )

        if cancellable:
            self.__data.room.revoke_room_invite(roomid, inviterid=inviter, invitedid=invited)
        else:
            raise MessageServiceException("Cannot uninvite from this room!")

    def dismiss_invite(self, userid: UserID, inviteid: InviteID) -> None:
        # Ensure that this user owns this invite, so we can't dismiss for another.
        invites = self.__data.room.get_room_invites(userid)
        invites = [inv for inv in invites if inv.id == inviteid]
        if invites:
            self.__data.room.dismiss_room_invite(invites[0].id)

    def acknowledge_invite(self, userid: UserID, inviteid: InviteID) -> None:
        # Ensure that this user owns this invite, so we can't acknowledge for another.
        invites = self.__data.room.get_room_invites(userid)
        invites = [inv for inv in invites if inv.id == inviteid]
        if invites:
            self.__data.room.acknowledge_room_invite(invites[0].id)

    def get_invited_rooms(self, userid: UserID) -> list[Invite]:
        invites = self.__data.room.get_room_invites(userid)
        for invite in invites:
            invite.user = self.__user.lookup_user(invite.userid)
            if invite.room is None:
                raise Exception("Logic error, rooms should exist when looking up invites directly!")
            self.__infer_room_info(userid, invite.room)
        return invites

    def get_joined_rooms(self, userid: UserID) -> list[Room]:
        rooms = self.__data.room.get_joined_rooms(userid)

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            self.__infer_room_info(userid, room)

        return sorted(rooms, key=lambda r: r.last_action_timestamp, reverse=True)

    def get_autojoin_rooms(self, userid: UserID) -> list[Room]:
        rooms = self.__data.room.get_autojoin_rooms()

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            self.__infer_room_info(userid, room)

        return sorted(rooms, key=lambda r: r.name)

    def join_autojoin_rooms(self, userid: UserID) -> None:
        rooms = self.__data.room.get_autojoin_rooms()
        for room in rooms:
            self.__data.room.join_room(room.id, userid)

    def get_public_rooms(self, userid: UserID) -> list[Room]:
        rooms = self.__data.room.get_public_rooms()
        for room in rooms:
            self.__infer_room_info(userid, room)
        return rooms

    def get_matching_rooms(self, userid: UserID, *, name: str | None = None) -> list[SearchResult]:
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
        ignored: set[UserID] = set()
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
            self.__data.user.get_visible_users(userid, "search", name=name),
            key=lambda u: u.nickname,
        )

        # Now, filter out any users that we've already got a chat with.
        potentialusers = [u for u in potentialusers if u.id not in ignored]

        # Now, resolve the icons of anyone left.
        for user in potentialusers:
            self.__attachments.resolve_user_icon(user)

        # Now, look up any invites that we might have and combine those.
        potentialinvites = {
            inv.room.id: inv.room for inv in self.get_invited_rooms(userid) if inv.room
        }

        # Finally, combined the two.
        results: list[SearchResult] = []
        for room in rooms:
            icon = room.icon
            handle: str | None = None
            if room.purpose == RoomPurpose.DIRECT_MESSAGE:
                if len(room.occupants) == 1:
                    handle = "@" + room.occupants[0].username
                elif len(room.occupants) == 2:
                    not_me = [o for o in room.occupants if o.userid != userid]
                    handle = "@" + not_me[0].username

            if not icon:
                raise Exception("Logic error, should have been inferred above!")

            invited = room.id in potentialinvites
            if invited:
                del potentialinvites[room.id]

            if room.id in memberof:
                results.append(SearchResult(room.name, handle, room.purpose, True, False, room.id, None, icon))
            else:
                results.append(SearchResult(room.name, handle, room.purpose, False, invited, room.id, None, icon))
        for user in potentialusers:
            icon = user.icon
            if not icon:
                raise Exception("Logic error, should have been inferred above!")
            results.append(SearchResult(
                user.nickname, f"@{user.username}", RoomPurpose.DIRECT_MESSAGE, False, False, None, user.id, icon
            ))

        # Now, handle adding on room invites that weren't handled above.
        if name:
            lowername = name.lower()
            potentialinvites = {
                k: v for (k, v) in potentialinvites.items()
                if lowername in v.name.lower()
            }

        for room in potentialinvites.values():
            icon = room.icon
            if not icon:
                raise Exception("Logic error, should have been inferred above!")
            results.append(SearchResult(room.name, None, room.purpose, False, True, room.id, None, icon))

        return sorted(results, key=lambda result: (result.name or "").lower())

    def get_matching_users(self, userid: UserID, roomid: RoomID, *, name: str | None = None) -> list[SearchResult]:
        # First, look up the room itself and get its joined occupants. Users should not be able to
        # deduce who is in a room by searching it.
        room = self.__data.room.get_room(roomid)
        if not room:
            return []

        if room.purpose not in {RoomPurpose.ROOM, RoomPurpose.CHAT}:
            return []

        occupants = {
            o.userid: o
            for o in self.__data.room.get_room_occupants(roomid, include_invited=True)
            if o.present or o.invite is not None
        }
        if userid not in occupants:
            # We're not in the room we're searching, no results for you!
            return []

        # Now, look up potential users that we could be inviting to this room.
        potentialusers = sorted(
            self.__data.user.get_visible_users(userid, "invite", name=name),
            key=lambda u: u.nickname,
        )

        # First, return all occupants, so that we can display in-room nickname/icon. Also display
        # any users that are in the chat already but have invites disabled.
        results: list[SearchResult] = []
        for occupant in occupants.values():
            self.__attachments.resolve_occupant_icon(occupant)
            icon = occupant.icon
            if not icon:
                raise Exception("Logic error, should have been inferred above!")

            results.append(SearchResult(
                occupant.nickname,
                f"@{occupant.username}",
                room.purpose,
                occupant.present,
                occupant.invite is not None,
                None,
                occupant.userid,
                icon,
            ))

        # Now, resolve the icons of everyone that we can invite who wasn't already in the above
        # list and send back the results.
        for user in potentialusers:
            if user.id in occupants:
                # Already displayed above.
                continue

            self.__attachments.resolve_user_icon(user)
            icon = user.icon
            if not icon:
                raise Exception("Logic error, should have been inferred above!")

            results.append(SearchResult(
                user.nickname,
                f"@{user.username}",
                room.purpose,
                user.id in occupants and occupants[user.id].present,
                user.id in occupants and occupants[user.id].invite is not None,
                None,
                user.id,
                icon,
            ))

        return sorted(results, key=lambda result: (result.name or "").lower())
