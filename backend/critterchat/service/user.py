from typing import List

from ..data import Data, UserSettings, UserID, Room, RoomID


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
        rooms.append(Room(RoomID(12345), "This is a test"))
        rooms.append(Room(RoomID(23456), "This is another test"))
        rooms.append(Room(RoomID(12345), "This should rename"))
        return rooms
