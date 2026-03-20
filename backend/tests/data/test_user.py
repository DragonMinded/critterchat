import pytest
from sqlalchemy.orm import Session

from critterchat.common import Time
from critterchat.data import UserID, RoomID, UserPermission, UserPreferences, UISize, SearchPrivacy, InvitePrivacy, UserSettings, InfoState
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

    def test_preferences_crud(self, tx: Session) -> None:
        """
        Tests basic create, retrieve, update, delete for user preferences in the system.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create a user so we can have settings against it.
        user = userdata.create_account('test_preferences_crud', 'some_arbitrary_password')
        assert user is not None

        # Now, attempt to grab the preferences that don't exist yet.
        prefs = userdata.get_preferences(user.id)
        assert prefs is None
        assert userdata.has_updated_preferences(user.id, Time.now() - 10) is False
        assert userdata.has_updated_preferences(user.id, Time.now() + 10) is False

        # Now, create a fresh preferences and save them.
        prefs = UserPreferences.default(user.id)
        userdata.put_preferences(prefs)

        # Now, attempt to grab the preferences again.
        new_prefs = userdata.get_preferences(user.id)
        assert new_prefs is not None
        assert new_prefs.userid == prefs.userid
        assert new_prefs.rooms_on_top == prefs.rooms_on_top
        assert new_prefs.combined_messages == prefs.combined_messages
        assert new_prefs.color_scheme == prefs.color_scheme
        assert new_prefs.desktop_size == prefs.desktop_size
        assert new_prefs.mobile_size == prefs.mobile_size
        assert new_prefs.admin_controls == prefs.admin_controls
        assert new_prefs.title_notifs == prefs.title_notifs
        assert new_prefs.search_privacy == prefs.search_privacy
        assert new_prefs.invite_privacy == prefs.invite_privacy
        assert new_prefs.mobile_audio_notifs == prefs.mobile_audio_notifs
        assert new_prefs.audio_notifs == prefs.audio_notifs

        # And make sure the availability boolean works.
        assert userdata.has_updated_preferences(user.id, Time.now() - 10) is True
        assert userdata.has_updated_preferences(user.id, Time.now() + 10) is False

        # Now make some updates.
        prefs.desktop_size = UISize.SMALLEST
        prefs.mobile_size = UISize.LARGEST
        userdata.put_preferences(prefs)

        # Now, attempt to grab the preferences again after update.
        new_prefs = userdata.get_preferences(user.id)
        assert new_prefs is not None
        assert new_prefs.userid == prefs.userid
        assert new_prefs.rooms_on_top == prefs.rooms_on_top
        assert new_prefs.combined_messages == prefs.combined_messages
        assert new_prefs.color_scheme == prefs.color_scheme
        assert new_prefs.desktop_size == prefs.desktop_size
        assert new_prefs.mobile_size == prefs.mobile_size
        assert new_prefs.admin_controls == prefs.admin_controls
        assert new_prefs.title_notifs == prefs.title_notifs
        assert new_prefs.search_privacy == prefs.search_privacy
        assert new_prefs.invite_privacy == prefs.invite_privacy
        assert new_prefs.mobile_audio_notifs == prefs.mobile_audio_notifs
        assert new_prefs.audio_notifs == prefs.audio_notifs

        # And make sure the availability boolean still works.
        assert userdata.has_updated_preferences(user.id, Time.now() - 10) is True
        assert userdata.has_updated_preferences(user.id, Time.now() + 10) is False

    def test_get_visible_users(self, tx: Session) -> None:
        """
        Verifies that get_visible_users understands and respects privacy settings given a purpose, and
        can properly filter out users when requested to by name match.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create some user accounts so we can test searching.
        user1 = userdata.create_account('test_get_visible_users_1', 'some_arbitrary_password')
        user2 = userdata.create_account('test_get_visible_users_2', 'some_arbitrary_password')
        user3 = userdata.create_account('test_get_visible_users_3', 'some_arbitrary_password')
        user4 = userdata.create_account('test_get_visible_users_4', 'some_arbitrary_password')
        assert user1 is not None
        assert user2 is not None
        assert user3 is not None
        assert user4 is not None

        # Nickname them so we can verify searching by username and nickname.
        user1.nickname = "first"
        user1.permissions.add(UserPermission.ACTIVATED)
        userdata.update_user(user1)

        user2.nickname = "second"
        user2.permissions.add(UserPermission.ACTIVATED)
        userdata.update_user(user2)

        user3.nickname = "third"
        user3.permissions.add(UserPermission.ACTIVATED)
        userdata.update_user(user3)

        user4.nickname = "fourth"
        userdata.update_user(user4)

        # Now, configure one each to be not visible given a particular search.
        user2_prefs = UserPreferences.default(user2.id)
        user2_prefs.search_privacy = SearchPrivacy.HIDDEN
        userdata.put_preferences(user2_prefs)

        user3_prefs = UserPreferences.default(user3.id)
        user3_prefs.invite_privacy = InvitePrivacy.DISALLOW
        userdata.put_preferences(user3_prefs)

        # Now, verify that we get the right accounts back for generic searches without names.
        assert {user1.id, user3.id} == {u.id for u in userdata.get_visible_users(user1.id, "search")}
        assert {user1.id, user2.id, user3.id} == {u.id for u in userdata.get_visible_users(user2.id, "search")}
        assert {user1.id, user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "search")}

        # And same for invite searches.
        assert {user1.id, user2.id} == {u.id for u in userdata.get_visible_users(user1.id, "invite")}
        assert {user1.id, user2.id} == {u.id for u in userdata.get_visible_users(user2.id, "invite")}
        assert {user1.id, user2.id, user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite")}

        # Now, re-run both of the above but with specific username searches.
        assert {user1.id, user3.id} == {u.id for u in userdata.get_visible_users(user1.id, "search", name="users")}
        assert {user1.id, user2.id, user3.id} == {u.id for u in userdata.get_visible_users(user2.id, "search", name="users")}
        assert {user1.id, user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "search", name="users")}
        assert {user1.id, user2.id} == {u.id for u in userdata.get_visible_users(user1.id, "invite", name="users")}
        assert {user1.id, user2.id} == {u.id for u in userdata.get_visible_users(user2.id, "invite", name="users")}
        assert {user1.id, user2.id, user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="users")}

        assert {user1.id} == {u.id for u in userdata.get_visible_users(user1.id, "search", name="users_1")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user2.id, "search", name="users_1")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user3.id, "search", name="users_1")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user1.id, "invite", name="users_1")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user2.id, "invite", name="users_1")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="users_1")}

        assert set() == {u.id for u in userdata.get_visible_users(user1.id, "search", name="users_2")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user2.id, "search", name="users_2")}
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "search", name="users_2")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user1.id, "invite", name="users_2")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user2.id, "invite", name="users_2")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="users_2")}

        assert {user3.id} == {u.id for u in userdata.get_visible_users(user1.id, "search", name="users_3")}
        assert {user3.id} == {u.id for u in userdata.get_visible_users(user2.id, "search", name="users_3")}
        assert {user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "search", name="users_3")}
        assert set() == {u.id for u in userdata.get_visible_users(user1.id, "invite", name="users_3")}
        assert set() == {u.id for u in userdata.get_visible_users(user2.id, "invite", name="users_3")}
        assert {user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="users_3")}

        assert {user1.id} == {u.id for u in userdata.get_visible_users(user1.id, "search", name="first")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user2.id, "search", name="first")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user3.id, "search", name="first")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user1.id, "invite", name="first")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user2.id, "invite", name="first")}
        assert {user1.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="first")}

        assert set() == {u.id for u in userdata.get_visible_users(user1.id, "search", name="second")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user2.id, "search", name="second")}
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "search", name="second")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user1.id, "invite", name="second")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user2.id, "invite", name="second")}
        assert {user2.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="second")}

        assert {user3.id} == {u.id for u in userdata.get_visible_users(user1.id, "search", name="third")}
        assert {user3.id} == {u.id for u in userdata.get_visible_users(user2.id, "search", name="third")}
        assert {user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "search", name="third")}
        assert set() == {u.id for u in userdata.get_visible_users(user1.id, "invite", name="third")}
        assert set() == {u.id for u in userdata.get_visible_users(user2.id, "invite", name="third")}
        assert {user3.id} == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="third")}

        # Negative testing too.
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "search", name="users_4")}
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="users_4")}
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "search", name="fourth")}
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="fourth")}
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "search", name="nobody")}
        assert set() == {u.id for u in userdata.get_visible_users(user3.id, "invite", name="nobody")}
