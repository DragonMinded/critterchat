import pytest
from sqlalchemy.orm import Session

from critterchat.data import UserID, RoomID, UserSettings, InfoState
from critterchat.data.user import UserData

from ..mocks import MockConfig


@pytest.mark.integration
class TestUserData:
    def test_user_crud(self, tx: Session) -> None:
        """
        Tests basic create, retrieve, update, delete for users in the system.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create the user
        user = userdata.create_account('test_user_crud', 'some_arbitrary_password')
        assert user is not None

        # Now, attempt to look up the user by both ID and username.
        by_id = userdata.get_user(user.id)
        by_username = userdata.from_username('test_user_crud')

        assert by_id is not None
        assert user.id == by_id.id
        assert by_username is not None
        assert user.id == by_username.id

        # Verify that we don't get exceptions trying to look up a nonexistent user.
        assert userdata.get_user(UserID(1000000)) is None
        assert userdata.from_username("nonexistent_username") is None

        # Now, verify user modifications.
        assert user.nickname == "test_user_crud"
        user.nickname = "updated_nickname"
        userdata.update_user(user)

        # Make sure that it reflects in the data.
        by_id = userdata.get_user(user.id)
        assert by_id is not None
        assert by_id.nickname == "updated_nickname"

        assert user.nickname == "updated_nickname"
        user.nickname = ""
        userdata.update_user(user)
        assert user.nickname == "test_user_crud"

        by_id = userdata.get_user(user.id)
        assert by_id is not None
        assert by_id.nickname == "test_user_crud"

        # No delete because we don't support user deletion since that would screw history.

    def test_settings_crud(self, tx: Session) -> None:
        """
        Tests basic create, retrieve, update, delete for user settings in the system.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create a user so we can have settings against it.
        user = userdata.create_account('test_settings_crud', 'some_arbitrary_password')
        assert user is not None

        sessionid = userdata.create_session(user.id)

        # Now, attempt to grab settings for this user.
        settings = userdata.get_settings(sessionid)
        assert settings is None

        settings = userdata.get_any_settings(user.id)
        assert settings is None

        # Now, create settings associated with a session.
        userdata.put_settings(sessionid, UserSettings(user.id, RoomID(12345), InfoState.HIDDEN))

        # Now, attmept to grab those settings.
        settings = userdata.get_settings(sessionid)
        assert settings is not None
        assert settings.userid == user.id
        assert settings.roomid == RoomID(12345)
        assert settings.info == InfoState.HIDDEN

        settings = userdata.get_any_settings(user.id)
        assert settings is not None
        assert settings.userid == user.id
        assert settings.roomid == RoomID(12345)
        assert settings.info == InfoState.HIDDEN

        # Now, attempt to update settings.
        userdata.put_settings(sessionid, UserSettings(user.id, RoomID(12345), InfoState.SHOWN))

        # Now, attmept to grab those settings.
        settings = userdata.get_settings(sessionid)
        assert settings is not None
        assert settings.userid == user.id
        assert settings.roomid == RoomID(12345)
        assert settings.info == InfoState.SHOWN

        settings = userdata.get_any_settings(user.id)
        assert settings is not None
        assert settings.userid == user.id
        assert settings.roomid == RoomID(12345)
        assert settings.info == InfoState.SHOWN

        # Finally, verify serdes for the settings object.
        settings_dict = settings.to_dict()
        new_settings = UserSettings.from_dict(user.id, settings_dict)
        assert settings.userid == new_settings.userid
        assert settings.roomid == new_settings.roomid
        assert settings.info == new_settings.info
