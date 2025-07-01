from typing import List

from ..data import Data, UserSettings, UserID, Room


class UserServiceException(Exception):
    pass


class UserService:
    def __init__(self, data: Data) -> None:
        self.__data = data

    def get_settings(self, userid: UserID) -> UserSettings:
        settings = self.__data.user.get_settings(userid)
        if settings:
            return settings

        return UserSettings(
            userid=userid,
            roomid=None,
        )

    def update_settings(self, userid: UserID, settings: UserSettings) -> None:
        if userid != settings.id:
            raise UserServiceException("Invaid User ID in settings bundle!")

        self.__data.user.put_settings(userid, settings)

    def get_joined_rooms(self, userid: UserID) -> List[Room]:
        rooms = self.__data.room.get_joined_rooms(userid)

        # Figure out any rooms that don't have a set name, and infer the name of the room.
        for room in rooms:
            if not room.name:
                if room.public:
                    room.name = "Unnamed Public Chat"
                else:
                    # Figure out how many people are in the chat, name it after them.
                    occupants = self.__data.room.get_room_occupants(room.id)
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

        return rooms
