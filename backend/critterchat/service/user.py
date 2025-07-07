from typing import Dict, Optional

from ..config import Config
from ..data import Data, UserSettings, User, ActionID, RoomID, UserID


class UserServiceException(Exception):
    pass


class UserService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data

    def get_settings(self, userid: UserID) -> UserSettings:
        settings = self.__data.user.get_settings(userid)
        if settings:
            return settings

        return UserSettings(
            userid=userid,
            roomid=None,
            info=None,
        )

    def update_settings(self, userid: UserID, settings: UserSettings) -> None:
        if userid != settings.id:
            raise UserServiceException("Invaid User ID in settings bundle!")

        self.__data.user.put_settings(userid, settings)

    def lookup_user(self, user: UserID) -> Optional[User]:
        return self.__data.user.get_user(user)

    def mark_last_seen(self, userid: UserID, roomid: RoomID, actionid: ActionID) -> None:
        self.__data.user.mark_last_seen(userid, roomid, actionid)

    def get_last_seen_counts(self, userid: UserID) -> Dict[RoomID, int]:
        lastseen = self.__data.user.get_last_seen_counts(userid)
        return {ls[0]: ls[1] for ls in lastseen}
