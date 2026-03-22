import pytest
from freezegun import freeze_time
from sqlalchemy.orm import Session

from critterchat.common import Time
from critterchat.data import (
    NewActionID,
    NewUserID,
    NewOccupantID,
    NewRoomID,
    ActionID,
    AttachmentID,
    UserID,
    RoomID,
    Action,
    ActionType,
    UserPermission,
    UserPreferences,
    UISize,
    SearchPrivacy,
    InfoState,
    InvitePrivacy,
    Occupant,
    Room,
    RoomPurpose,
    UserSettings,
    UserNotification,
    User,
)
from critterchat.data.user import UserData
from critterchat.data.room import RoomData

from ..mocks import MockConfig


@pytest.mark.integration
class TestUserData:
    def test_user_crud(self, tx: Session) -> None:
        """
        Tests basic create, retrieve, update, delete for users in the system.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        with freeze_time("2026-01-01 6:00:00"):
            # First, create the user
            user = userdata.create_account('test_user_crud', 'some_arbitrary_password')
            assert user is not None

            # Attempt to create another user with the same name.
            second = userdata.create_account('test_user_crud', 'some_arbitrary_password')
            assert second is None

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
            assert userdata.get_user(NewUserID) is None

            # Verify that we can detect changes to this user.
            assert userdata.has_updated_user(user.id, Time.now() - 5) is True
            assert userdata.has_updated_user(user.id, Time.now() + 5) is False
            assert userdata.get_last_user_update() == Time.now()

        with freeze_time("2026-01-01 6:10:00"):
            # Now, verify user modifications.
            assert user.nickname == "test_user_crud"
            user.nickname = "updated_nickname"
            user.iconid = AttachmentID(999999)
            userdata.update_user(user)

            # Verify that we catch developer errors.
            with pytest.raises(ValueError):
                invalid = User(
                    userid=NewUserID,
                    username="does_not_matter",
                    permissions=set(),
                    nickname="",
                    about="",
                    iconid=None,
                )
                userdata.update_user(invalid)

            # Verify that we can detect changes to this user.
            assert userdata.has_updated_user(user.id, Time.now() - 5) is True
            assert userdata.has_updated_user(user.id, Time.now() + 5) is False
            assert userdata.get_last_user_update() == Time.now()

            # Make sure that it reflects in the data.
            by_id = userdata.get_user(user.id)
            assert by_id is not None
            assert by_id.nickname == "updated_nickname"
            assert by_id.iconid == AttachmentID(999999)

            assert user.nickname == "updated_nickname"
            user.nickname = ""
            user.iconid = None
            userdata.update_user(user)
            assert user.nickname == "test_user_crud"
            assert user.iconid is None

            by_id = userdata.get_user(user.id)
            assert by_id is not None
            assert by_id.nickname == "test_user_crud"
            assert by_id.iconid is None

        # No delete because we don't support user deletion since that would screw history.

        # Finally, verify that our get last user update still works even when we have only preferences updates.
        with freeze_time("2026-01-01 6:20:00"):
            prefs = UserPreferences.default(user.id)
            userdata.put_preferences(prefs)

            # Verify that we can detect changes to this user.
            assert userdata.has_updated_user(user.id, Time.now() - 5) is False
            assert userdata.has_updated_user(user.id, Time.now() + 5) is False
            assert userdata.get_last_user_update() == Time.now()

    def test_user_password(self, tx: Session) -> None:
        """
        Tests password verification and update functionality.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create the user
        user = userdata.create_account('test_user_password', 'some_arbitrary_password')
        assert user is not None

        # Now, verify that the password we created the account with validates.
        assert userdata.validate_password(user.id, 'some_arbitrary_password') is True
        assert userdata.validate_password(user.id, 'another_wrong_password') is False

        # Also verify that we always get "false" if the user is invalid.
        assert userdata.validate_password(NewUserID, 'some_arbitrary_password') is False
        assert userdata.validate_password(UserID(123456), 'some_arbitrary_password') is False

        # Now, change the password, verify that we still work.
        userdata.update_password(user.id, 'brand_new_password')
        assert userdata.validate_password(user.id, 'brand_new_password') is True
        assert userdata.validate_password(user.id, 'some_arbitrary_password') is False

        # Also verify that we catch when a developer makes a mistake.
        with pytest.raises(ValueError):
            userdata.update_password(NewUserID, 'brand_new_password')

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

        # Also verify that we can't create settings for an invalid user.
        with pytest.raises(ValueError):
            userdata.put_settings(sessionid, UserSettings(NewUserID, RoomID(12345), InfoState.HIDDEN))

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

    def test_session_crud(self, tx: Session) -> None:
        """
        Tests session handling create, retrieve, update and delete.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create a user so we can have sessions against it.
        user = userdata.create_account('test_session_crud', 'some_arbitrary_password')
        assert user is not None

        # Verify that we catch when a developer makes a mistake.
        with pytest.raises(ValueError):
            userdata.create_session(NewUserID)

        # Create a couple of sessions.
        session1 = userdata.create_session(user.id)
        session2 = userdata.create_session(user.id)

        # Make sure we can look up the user by either session.
        user1 = userdata.from_session(session1)
        assert user1 is not None
        assert user1.id == user.id
        user2 = userdata.from_session(session2)
        assert user2 is not None
        assert user2.id == user.id

        # Make sure we don't get any user from a made up session.
        user3 = userdata.from_session("i_made_this_up")
        assert user3 is None

        # Now, delete one of the sessions, make sure the other still works.
        userdata.destroy_session(session1)

        user1 = userdata.from_session(session1)
        assert user1 is None
        user2 = userdata.from_session(session2)
        assert user2 is not None
        assert user2.id == user.id

    def test_invite_crud(self, tx: Session) -> None:
        """
        Tests invite handling create, retrieve, update and delete.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create a user so we can have invites against it.
        user = userdata.create_account('test_invite_crud', 'some_arbitrary_password')
        assert user is not None

        # Create a couple of invites.
        invite1 = userdata.create_invite(user.id)
        invite2 = userdata.create_invite(user.id)

        # Verify that we can create invites not associated with a user.
        invite3 = userdata.create_invite(NewUserID)

        # Make sure we can look up the user by either invite.
        user1 = userdata.from_invite(invite1)
        assert user1 is not None
        assert user1.id == user.id
        user2 = userdata.from_invite(invite2)
        assert user2 is not None
        assert user2.id == user.id
        user3 = userdata.from_invite(invite3)
        assert user3 is None

        # Verify that the invite comes up valid for both.
        assert userdata.validate_invite(invite1) is True
        assert userdata.validate_invite(invite2) is True
        assert userdata.validate_invite(invite3) is True

        # Make sure we don't get any user from a made up invite.
        user3 = userdata.from_invite("i_made_this_up")
        assert user3 is None
        assert userdata.validate_invite("i_made_this_up") is False

        # Now, delete one of the invites, make sure the other still works.
        userdata.destroy_invite(invite1)

        user1 = userdata.from_invite(invite1)
        assert user1 is None
        user2 = userdata.from_invite(invite2)
        assert user2 is not None
        assert user2.id == user.id
        user3 = userdata.from_invite(invite3)
        assert user3 is None

        # Verify that the invite we invalidated comes up invalid.
        assert userdata.validate_invite(invite1) is False
        assert userdata.validate_invite(invite2) is True
        assert userdata.validate_invite(invite3) is True

    def test_recovery_crud(self, tx: Session) -> None:
        """
        Tests recovery handling create, retrieve, update and delete.
        """

        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create a user so we can have recoveries against it.
        user = userdata.create_account('test_recovery_crud', 'some_arbitrary_password')
        assert user is not None

        # Verify that we catch when a developer makes a mistake.
        with pytest.raises(ValueError):
            userdata.create_recovery(NewUserID)

        # Create a couple of recoveries.
        recovery1 = userdata.create_recovery(user.id)
        recovery2 = userdata.create_recovery(user.id)

        # Make sure we can look up the user by either recovery.
        user1 = userdata.from_recovery(recovery1)
        assert user1 is not None
        assert user1.id == user.id
        user2 = userdata.from_recovery(recovery2)
        assert user2 is not None
        assert user2.id == user.id

        # Make sure we don't get any user from a made up recovery.
        user3 = userdata.from_recovery("i_made_this_up")
        assert user3 is None

        # Now, change the password which should invalidate all recoveries.
        userdata.update_password(user.id, 'brand_new_password')

        user1 = userdata.from_recovery(recovery1)
        assert user1 is None
        user2 = userdata.from_recovery(recovery2)
        assert user2 is None

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
        assert userdata.has_updated_preferences(user.id, Time.now() - 5) is False
        assert userdata.has_updated_preferences(user.id, Time.now() + 5) is False

        # Verify that getting preferences for an invalid user always returns nothing.
        assert userdata.get_preferences(NewUserID) is None
        assert userdata.get_preferences(UserID(123456)) is None

        # Verify that we catch when a developer makes a mistake.
        with pytest.raises(ValueError):
            invalid = UserPreferences.default(NewUserID)
            userdata.put_preferences(invalid)

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
        assert userdata.has_updated_preferences(user.id, Time.now() - 5) is True
        assert userdata.has_updated_preferences(user.id, Time.now() + 5) is False

        # Now make some updates.
        prefs.desktop_size = UISize.SMALLEST
        prefs.mobile_size = UISize.LARGEST
        prefs.audio_notifs = {UserNotification.MENTIONED, UserNotification.USER_REACTED}
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
        assert userdata.has_updated_preferences(user.id, Time.now() - 5) is True
        assert userdata.has_updated_preferences(user.id, Time.now() + 5) is False

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

        # Verify that we always get back empty data when performing searches for a new user.
        assert [] == userdata.get_visible_users(NewUserID, "search")
        assert [] == userdata.get_visible_users(NewUserID, "invite")

        # Verify that getting users without a purpose always works.
        assert {user1.id, user2.id, user3.id, user4.id} == {u.id for u in userdata.get_users()}
        assert {user1.id, user2.id, user3.id, user4.id} == {u.id for u in userdata.get_users(name="users")}
        assert {user1.id} == {u.id for u in userdata.get_users(name="users_1")}
        assert {user4.id} == {u.id for u in userdata.get_users(name="fourth")}

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

    def test_seen_counts(self, tx: Session) -> None:
        """
        Verifies that users can track the last seen action in a given room properly.
        """

        config = MockConfig()
        userdata = UserData(config, tx)
        roomdata = RoomData(config, tx)

        # Create the data we need for the test.
        user = userdata.create_account('test_seen_counts_user', 'some_arbitrary_password')
        assert user is not None
        user.permissions.add(UserPermission.ACTIVATED)
        userdata.update_user(user)

        room1 = Room(
            NewRoomID,
            "test room counts 1",
            "",
            RoomPurpose.ROOM,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room1)
        room2 = Room(
            NewRoomID,
            "test room counts 2",
            "",
            RoomPurpose.DIRECT_MESSAGE,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room2)
        room3 = Room(
            NewRoomID,
            "test room counts 3",
            "",
            RoomPurpose.CHAT,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room3)

        roomdata.join_room(room1.id, user.id)
        roomdata.join_room(room2.id, user.id)
        roomdata.join_room(room3.id, user.id)

        # Before marking, we want to see that the seen counts are correct.
        assert {room1.id: 1, room2.id: 0, room3.id: 1} == {roomid: count for (roomid, count) in userdata.get_last_seen_counts(user.id)}

        # Get actions for each room, mark ourselves as having seen those actions so we can
        # test the case where we have nothing to count.
        expected: dict[RoomID, ActionID] = {}
        for roomid in [room1.id, room2.id]:
            history = roomdata.get_room_history(roomid, limit=1)
            userdata.mark_last_seen(user.id, roomid, history[0].id)
            expected[roomid] = history[0].id

        # We should match both counts and expected.
        assert {room1.id: 0, room2.id: 0, room3.id: 1} == {roomid: count for (roomid, count) in userdata.get_last_seen_counts(user.id)}
        assert expected == {roomid: actionid for (roomid, actionid) in userdata.get_last_seen_actions(user.id)}

        # Verify that we can't mark last seen of an action lower than what we've already marked.
        userdata.mark_last_seen(user.id, room1.id, ActionID(-1))
        userdata.mark_last_seen(user.id, room1.id, ActionID(-2))
        assert {room1.id: 0, room2.id: 0, room3.id: 1} == {roomid: count for (roomid, count) in userdata.get_last_seen_counts(user.id)}
        assert expected == {roomid: actionid for (roomid, actionid) in userdata.get_last_seen_actions(user.id)}

        # Verify that we can get updated counts when new actions are inserted.
        for _ in range(3):
            occupant = Occupant(occupantid=NewOccupantID, userid=user.id)
            action = Action(
                actionid=NewActionID,
                timestamp=Time.now(),
                occupant=occupant,
                action=ActionType.MESSAGE,
                details={"message": "test message"},
            )
            roomdata.insert_action(room1.id, action)

        # We should match both counts and expected.
        assert {room1.id: 3, room2.id: 0, room3.id: 1} == {roomid: count for (roomid, count) in userdata.get_last_seen_counts(user.id)}
        assert expected == {roomid: actionid for (roomid, actionid) in userdata.get_last_seen_actions(user.id)}

        # Also make sure that we don't crash when given an invalid user ID.
        assert [] == userdata.get_last_seen_counts(NewUserID)
        assert [] == userdata.get_last_seen_counts(UserID(-1))
        assert [] == userdata.get_last_seen_actions(NewUserID)
        assert [] == userdata.get_last_seen_actions(UserID(-1))
