from typing import List, Optional

from ..common import Time
from ..data import (
    Data,
    Action,
    ActionType,
    Occupant,
    Room,
    RoomSearchResult,
    NewOccupantID,
    NewActionID,
    NewRoomID,
    ActionID,
    RoomID,
    UserID,
)


class MessageServiceException(Exception):
    pass


class MessageService:
    def __init__(self, data: Data) -> None:
        self.__data = data

    def get_last_room_action(self, roomid: RoomID) -> Optional[Action]:
        history = self.__data.room.get_room_history(roomid, limit=1)
        return history[0] if history else None

    def get_room_history(self, roomid: RoomID) -> List[Action]:
        history = self.__data.room.get_room_history(roomid)
        history = [e for e in history if e.action in {ActionType.MESSAGE}]
        return history

    def get_room_updates(self, roomid: RoomID, after: ActionID) -> List[Action]:
        history = self.__data.room.get_room_history(roomid, after=after)
        history = [e for e in history if e.action in {ActionType.MESSAGE}]
        return history

    def add_message(self, roomid: RoomID, userid: UserID, message: str) -> Optional[Action]:
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
            return action
        return None

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
                    self.__infer_room_name(userid, room)
                    return room

        # Now, create a new room since we don't have an existing one.
        room = Room(NewRoomID, "", False)
        self.__data.room.create_room(room)
        self.join_room(room.id, userid)
        self.join_room(room.id, otherid)
        self.__infer_room_name(userid, room)
        return room

    def join_room(self, roomid: RoomID, userid: UserID) -> None:
        self.__data.room.join_room(roomid, userid)

    def leave_room(self, roomid: RoomID, userid: UserID) -> None:
        self.__data.room.leave_room(roomid, userid)

    def __infer_room_name(self, userid: UserID, room: Room) -> None:
        if not room.name:
            if room.public:
                room.name = "Unnamed Public Chat"
            else:
                # Figure out how many people are in the chat, name it after them.
                occupants = self.__data.room.get_room_occupants(room.id, include_left=True)
                if not occupants:
                    # This shouldn't happen, since we would have to be the sole occupant,
                    # but I guess there could be a race between grabbing the rooms and occupants,
                    # so let's just throw in a funny easter egg.
                    room.name = "An Empty Cavern"
                elif len(occupants) == 1:
                    room.name = "Chat with Myself"
                elif len(occupants) == 2:
                    not_me = [o for o in occupants if o.userid != userid]
                    if len(not_me) == 1:
                        room.name = f"Chat with {not_me[0].nickname}"
                    else:
                        room.name = "Unnamed Private Chat"
                else:
                    room.name = "Unnamed Private Chat"

    def get_joined_rooms(self, userid: UserID) -> List[Room]:
        rooms = self.__data.room.get_joined_rooms(userid)

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            self.__infer_room_name(userid, room)

        return rooms

    def get_matching_rooms(self, userid: UserID, *, name: Optional[str] = None) -> List[RoomSearchResult]:
        # First get the list of rooms that we can see based on our userID (joined rooms).
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
            self.__infer_room_name(userid, room)

        # Now, filter out any rooms that still don't meet our criteria.
        if name:
            lowername = name.lower()
            rooms = [r for r in rooms if lowername in r.name.lower()]
        rooms = sorted(rooms, key=lambda r: r.name)

        # Now, look up all users we could chat with, given our criteria.
        potentialusers = sorted(
            self.__data.user.get_visible_users(userid, name=name),
            key=lambda u: u.name,
        )

        # Now, combined the two.
        results: List[RoomSearchResult] = []
        for room in rooms:
            if room.id in memberof:
                results.append(RoomSearchResult(room.name, True, room.id, None))
            else:
                results.append(RoomSearchResult(room.name, False, room.id, None))
        for user in potentialusers:
            results.append(RoomSearchResult(user.name, False, None, user.id))

        return results
