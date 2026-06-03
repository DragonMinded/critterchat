import pytest

from critterchat.common import Time
from critterchat.data import (
    ConnectionLike,
    Action,
    ActionType,
    Occupant,
    Room,
    RoomPurpose,
    RoomID,
    NewActionID,
    NewOccupantID,
    NewRoomID,
    NewUserID,
    UserPermission,
)
from critterchat.data.attachment import AttachmentData
from critterchat.data.room import RoomData
from critterchat.data.user import UserData

from ..mocks import MockConfig


@pytest.mark.integration
class TestRoomData:
    def test_room_crud(self, tx: ConnectionLike) -> None:
        """
        Tests basic create, retrieve, update, delete for rooms in the system.
        """

        config = MockConfig()
        attachmentdata = AttachmentData(config, tx)
        roomdata = RoomData(config, tx)
        userdata = UserData(config, tx)

        # First, create a room
        room = Room(
            NewRoomID,
            "test room crud",
            "test room crud topic",
            RoomPurpose.ROOM,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room)
        assert room.id != NewRoomID
        assert room.last_action_timestamp is not None

        # Now, attempt to look up the room.
        by_id = roomdata.get_room(room.id)
        assert by_id is not None
        assert by_id.id == room.id

        # Ensure that looking up an invalid room doesn't crash us.
        assert roomdata.get_room(RoomID(1000000)) is None

        # Ensure we can grab the action history, which should be empty.
        history = roomdata.get_room_history(room.id)
        assert history == []

        # Now, attempt to modify the room.
        room.name = "test room crud updated"
        room.topic = "test room crud topic updated"
        roomdata.update_room(room, NewUserID)

        # Make sure it reflects in the data.
        by_id = roomdata.get_room(room.id)
        assert by_id is not None
        assert by_id.name == "test room crud updated"
        assert by_id.topic == "test room crud topic updated"
        assert by_id.iconid is None

        # Ensure that reading actions for this room shows the updated action from updating the room.
        history = roomdata.get_room_history(room.id)
        assert len(history) == 1
        assert history[0].action == ActionType.CHANGE_INFO
        assert history[0].occupant is None
        old_action_id = history[0].id

        # And verify that the action ID we detect on the network is correct.
        assert old_action_id == roomdata.get_last_action()

        # Now, join the room as a user and then make a change again.
        user = userdata.create_account("room_crud_user", "amazing_password")
        assert user is not None
        roomdata.join_room(room.id, user.id)

        # Make sure the action was recorded.
        history = roomdata.get_room_history(room.id, types=[ActionType.JOIN])
        assert len(history) == 1
        assert history[0].action == ActionType.JOIN
        assert history[0].occupant is not None
        assert history[0].occupant.userid == user.id

        # And verify that the action ID we detect on the network is correct.
        assert history[0].id == roomdata.get_last_action()

        # Now, edit the room as the user.
        aid = attachmentdata.insert_attachment('local', 'image/png', 'testing.png', {})
        assert aid is not None
        room.iconid = aid
        room.name = "test room updated by user"
        roomdata.update_room(room, user.id)

        # And make sure the data reflects.
        by_id = roomdata.get_room(room.id)
        assert by_id is not None
        assert by_id.name == "test room updated by user"
        assert by_id.topic == "test room crud topic updated"
        assert by_id.iconid == aid

        # And make sure we can find this info.
        history = roomdata.get_room_history(room.id, types=[ActionType.CHANGE_INFO], after=old_action_id)
        assert len(history) == 1
        assert history[0].action == ActionType.CHANGE_INFO
        assert history[0].occupant is not None
        assert history[0].occupant.userid == user.id
        new_action_id = history[0].id

        # And verify that the action ID we detect on the network is correct.
        assert new_action_id == roomdata.get_last_action()

        # Also make sure we can find the info by limiting the response to the last few actions.
        history = roomdata.get_room_history(room.id, limit=1)
        assert len(history) == 1
        assert history[0].action == ActionType.CHANGE_INFO
        assert history[0].occupant is not None
        assert history[0].occupant.userid == user.id

        # And make sure we can find the old events as well, ordered by newest to oldest.
        history = roomdata.get_room_history(room.id, before=new_action_id)
        assert len(history) == 2
        assert history[0].action == ActionType.JOIN
        assert history[0].occupant is not None
        assert history[0].occupant.userid == user.id
        assert history[1].action == ActionType.CHANGE_INFO
        assert history[1].occupant is None

        # And verify that the action ID we detect on the network is correct.
        assert new_action_id == roomdata.get_last_action()

        # No delete because we do not delete rooms currently.

    def test_shadow_join_room(self, tx: ConnectionLike) -> None:
        """
        Tests that we can shadow join a room properly.
        """

        config = MockConfig()
        roomdata = RoomData(config, tx)
        userdata = UserData(config, tx)

        # First, create a room
        room = Room(
            NewRoomID,
            "test shadow join",
            "",
            RoomPurpose.ROOM,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room)
        assert room.id != NewRoomID

        # Create a user that we can use.
        user = userdata.create_account("shadow_join_user", "amazing_password")
        assert user is not None

        # Make sure they're not actually in the room.
        assert [] == roomdata.get_room_occupants(room.id, include_left=False)
        assert [] == roomdata.get_room_occupants(room.id, include_left=True)

        # Shadow-join the room, verify that we're in but not present.
        roomdata.shadow_join_room(room.id, user.id)
        assert [] == roomdata.get_room_occupants(room.id, include_left=False)
        occupants = roomdata.get_room_occupants(room.id, include_left=True)
        assert len(occupants) == 1
        assert occupants[0].userid == user.id
        assert occupants[0].present is False

        # Now, regular join the room, verify that we're in and present.
        roomdata.join_room(room.id, user.id)
        occupants = roomdata.get_room_occupants(room.id, include_left=False)
        assert len(occupants) == 1
        assert occupants[0].userid == user.id
        assert occupants[0].present is True
        occupants = roomdata.get_room_occupants(room.id, include_left=True)
        assert len(occupants) == 1
        assert occupants[0].userid == user.id
        assert occupants[0].present is True

        # Now, try shadow-joining again, make sure that it doesn't override the join.
        roomdata.shadow_join_room(room.id, user.id)
        occupants = roomdata.get_room_occupants(room.id, include_left=False)
        assert len(occupants) == 1
        assert occupants[0].userid == user.id
        assert occupants[0].present is True
        occupants = roomdata.get_room_occupants(room.id, include_left=True)
        assert len(occupants) == 1
        assert occupants[0].userid == user.id
        assert occupants[0].present is True

        # Now, leave the room, ensure we're back to where we were after shadow-joining.
        roomdata.leave_room(room.id, user.id)
        assert [] == roomdata.get_room_occupants(room.id, include_left=False)
        occupants = roomdata.get_room_occupants(room.id, include_left=True)
        assert len(occupants) == 1
        assert occupants[0].userid == user.id
        assert occupants[0].present is False

    def test_get_joined_rooms(self, tx: ConnectionLike) -> None:
        """
        Verifies that get_joined_rooms operates properly.
        """

        config = MockConfig()
        roomdata = RoomData(config, tx)
        userdata = UserData(config, tx)

        # First, create a few rooms for users to be in or not be in.
        room1 = Room(
            NewRoomID,
            "test room 1",
            "",
            RoomPurpose.DIRECT_MESSAGE,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room1)

        room2 = Room(
            NewRoomID,
            "test room 2",
            "",
            RoomPurpose.DIRECT_MESSAGE,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room2)

        # Now, create some users to join those rooms.
        userdata.create_account("test_user_1", "arbitrary_password")
        userdata.create_account("test_user_2", "arbitrary_password")

        user1 = userdata.from_username("test_user_1")
        assert user1 is not None
        user2 = userdata.from_username("test_user_2")
        assert user2 is not None

        # Now, join one user to both rooms, the other user to one room and shadow join the other.
        # Shadow joining is just joining as already left, so that we can simulate how direct messages
        # are created without popping up on the other user's clients.
        roomdata.join_room(room1.id, user1.id)
        roomdata.join_room(room1.id, user2.id)

        roomdata.join_room(room2.id, user1.id)
        roomdata.shadow_join_room(room2.id, user2.id)

        # Now, verify that we get the right responses back for joined rooms for each user.
        rooms = {room.id for room in roomdata.get_joined_rooms(user1.id)}
        assert rooms == {room1.id, room2.id}
        rooms = {room.id for room in roomdata.get_left_rooms(user1.id)}
        assert rooms == set()

        rooms = {room.id for room in roomdata.get_joined_rooms(user2.id)}
        assert rooms == {room1.id}
        rooms = {room.id for room in roomdata.get_left_rooms(user2.id)}
        assert rooms == {room2.id}

        # Now, verify that we get all rooms back for joined rooms with include left.
        rooms = {room.id for room in roomdata.get_joined_rooms(user1.id, include_left=True)}
        assert rooms == {room1.id, room2.id}

        rooms = {room.id for room in roomdata.get_joined_rooms(user2.id, include_left=True)}
        assert rooms == {room1.id, room2.id}

    def test_get_room_occupants(self, tx: ConnectionLike) -> None:
        """
        Verifies that get_room_occupants operates properly.
        """

        config = MockConfig()
        roomdata = RoomData(config, tx)
        userdata = UserData(config, tx)
        attachmentdata = AttachmentData(config, tx)

        # First, create a few rooms for users to be in or not be in.
        room1 = Room(
            NewRoomID,
            "test room 1",
            "",
            RoomPurpose.CHAT,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room1)

        room2 = Room(
            NewRoomID,
            "test room 2",
            "",
            RoomPurpose.CHAT,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room2)

        # Now, create some users to join those rooms.
        userdata.create_account("test_user_1", "arbitrary_password")
        userdata.create_account("test_user_2", "arbitrary_password")
        userdata.create_account("test_user_3", "arbitrary_password")

        user1 = userdata.from_username("test_user_1")
        assert user1 is not None
        user2 = userdata.from_username("test_user_2")
        assert user2 is not None
        user3 = userdata.from_username("test_user_3")
        assert user3 is not None

        # Activate users so they don't appear inactive.
        user1.permissions.add(UserPermission.ACTIVATED)
        user2.permissions.add(UserPermission.ACTIVATED)
        user3.permissions.add(UserPermission.ACTIVATED)
        userdata.update_user(user1)
        userdata.update_user(user2)
        userdata.update_user(user3)

        # Now, join one user to both rooms, the other user to one room and shadow join the other.
        # Shadow joining is just joining as already left, so that we can simulate how direct messages
        # are created without popping up on the other user's clients.
        roomdata.join_room(room1.id, user1.id)
        roomdata.join_room(room1.id, user2.id)
        roomdata.grant_room_invite(room1.id, user3.id, user1.id)

        roomdata.join_room(room2.id, user1.id)
        roomdata.shadow_join_room(room2.id, user2.id)

        # Now, verify that we get the right responses back for users in each room.
        users1 = {occupant.userid: occupant for occupant in roomdata.get_room_occupants(room1.id)}
        assert users1.keys() == {user1.id, user2.id}
        users2 = {occupant.userid: occupant for occupant in roomdata.get_room_occupants(room2.id)}
        assert users2.keys() == {user1.id}

        # Verify some properties and ensure the occupants are different.
        assert users1[user1.id].id != users2[user1.id].id

        assert users1[user1.id].username == "test_user_1"
        assert not users1[user1.id].muted
        assert users1[user1.id].invite is None
        assert not users1[user1.id].inactive
        assert users1[user1.id].present

        assert users1[user2.id].username == "test_user_2"
        assert not users1[user2.id].muted
        assert users1[user2.id].invite is None
        assert not users1[user2.id].inactive
        assert users1[user2.id].present

        assert users2[user1.id].username == "test_user_1"
        assert not users2[user1.id].muted
        assert users2[user1.id].invite is None
        assert not users2[user1.id].inactive
        assert users2[user1.id].present

        # And verify that we get our occupants back for a given user.
        roomdata.update_room_occupant(room1.id, user1.id, "user1_room1_nick", None)
        roomdata.update_room_occupant(room2.id, user1.id, "user1_room2_nick", None)
        occupant_by_room = roomdata.get_joined_room_occupants(user1.id)
        assert occupant_by_room.keys() == {room1.id, room2.id}
        assert occupant_by_room[room1.id].id != occupant_by_room[room2.id].id
        assert occupant_by_room[room1.id].userid == user1.id
        assert occupant_by_room[room1.id].nickname == "user1_room1_nick"
        assert occupant_by_room[room2.id].userid == user1.id
        assert occupant_by_room[room2.id].nickname == "user1_room2_nick"

        # Put the nickname back for the rest of the test.
        roomdata.update_room_occupant(room1.id, user1.id, None, None)
        roomdata.update_room_occupant(room2.id, user1.id, None, None)

        # Now, verify that we get all users back for each room when specifying include left.
        users1 = {occupant.userid: occupant for occupant in roomdata.get_room_occupants(room1.id, include_left=True)}
        assert users1.keys() == {user1.id, user2.id, user3.id}
        users2 = {occupant.userid: occupant for occupant in roomdata.get_room_occupants(room2.id, include_left=True)}
        assert users2.keys() == {user1.id, user2.id}

        # Verify some properties and ensure the occupants are different.
        assert users1[user1.id].id != users2[user1.id].id
        assert users1[user2.id].id != users2[user2.id].id

        assert users1[user1.id].username == "test_user_1"
        assert not users1[user1.id].muted
        assert users1[user1.id].invite is None
        assert not users1[user1.id].inactive
        assert users1[user1.id].present

        assert users1[user2.id].username == "test_user_2"
        assert not users1[user2.id].muted
        assert users1[user2.id].invite is None
        assert not users1[user2.id].inactive
        assert users1[user2.id].present

        assert users1[user3.id].username == "test_user_3"
        assert not users1[user3.id].muted
        assert users1[user3.id].invite is not None
        assert not users1[user3.id].inactive
        assert not users1[user3.id].present

        assert users2[user1.id].username == "test_user_1"
        assert not users2[user1.id].muted
        assert users2[user1.id].invite is None
        assert not users2[user1.id].inactive
        assert users2[user1.id].present

        assert users2[user2.id].username == "test_user_2"
        assert not users2[user2.id].muted
        assert users2[user2.id].invite is None
        assert not users2[user2.id].inactive
        assert not users2[user2.id].present

        # Now, verify that we get all users back for each room when specifying include invited.
        users1 = {occupant.userid: occupant for occupant in roomdata.get_room_occupants(room1.id, include_invited=True)}
        assert users1.keys() == {user1.id, user2.id, user3.id}
        users2 = {occupant.userid: occupant for occupant in roomdata.get_room_occupants(room2.id, include_invited=True)}
        assert users2.keys() == {user1.id}

        # Verify some properties and ensure the occupants are different.
        assert users1[user1.id].id != users2[user1.id].id

        assert users1[user1.id].username == "test_user_1"
        assert not users1[user1.id].muted
        assert users1[user1.id].invite is None
        assert not users1[user1.id].inactive
        assert users1[user1.id].present

        assert users1[user2.id].username == "test_user_2"
        assert not users1[user2.id].muted
        assert users1[user2.id].invite is None
        assert not users1[user2.id].inactive
        assert users1[user2.id].present

        assert users1[user3.id].username == "test_user_3"
        assert not users1[user3.id].muted
        assert users1[user3.id].invite is not None
        assert not users1[user3.id].inactive
        assert not users1[user3.id].present

        assert users2[user1.id].username == "test_user_1"
        assert not users2[user1.id].muted
        assert users2[user1.id].invite is None
        assert not users2[user1.id].inactive
        assert users2[user1.id].present

        # Now, verify that we get all users back for each room when specifying include left and include invited
        users1 = {
            occupant.userid: occupant
            for occupant in roomdata.get_room_occupants(room1.id, include_left=True, include_invited=True)
        }
        assert users1.keys() == {user1.id, user2.id, user3.id}
        users2 = {
            occupant.userid: occupant
            for occupant in roomdata.get_room_occupants(room2.id, include_left=True, include_invited=True)
        }
        assert users2.keys() == {user1.id, user2.id}

        # Verify some properties and ensure the occupants are different.
        assert users1[user1.id].id != users2[user1.id].id
        assert users1[user2.id].id != users2[user2.id].id

        assert users1[user1.id].username == "test_user_1"
        assert not users1[user1.id].muted
        assert users1[user1.id].invite is None
        assert not users1[user1.id].inactive
        assert users1[user1.id].present

        assert users1[user2.id].username == "test_user_2"
        assert not users1[user2.id].muted
        assert users1[user2.id].invite is None
        assert not users1[user2.id].inactive
        assert users1[user2.id].present

        assert users1[user3.id].username == "test_user_3"
        assert not users1[user3.id].muted
        assert users1[user3.id].invite is not None
        assert not users1[user3.id].inactive
        assert not users1[user3.id].present

        assert users2[user1.id].username == "test_user_1"
        assert not users2[user1.id].muted
        assert users2[user1.id].invite is None
        assert not users2[user1.id].inactive
        assert users2[user1.id].present

        assert users2[user2.id].username == "test_user_2"
        assert not users2[user2.id].muted
        assert users2[user2.id].invite is None
        assert not users2[user2.id].inactive
        assert not users2[user2.id].present

        # Verify that nickname resolution for occupants is performed correctly.
        occupant = [o for o in roomdata.get_room_occupants(room1.id) if o.username == "test_user_1"][0]
        assert occupant.username == "test_user_1"
        assert occupant.nickname == "test_user_1"
        assert occupant.iconid is None

        # Set the user's nickname and make sure it shows up in occupants.
        aid1 = attachmentdata.insert_attachment('local', 'image/png', 'testing1.png', {})
        user = userdata.from_username("test_user_1")
        assert user is not None
        user.nickname = "test_nickname"
        user.iconid = aid1
        userdata.update_user(user)

        occupant = [o for o in roomdata.get_room_occupants(room1.id) if o.username == "test_user_1"][0]
        assert occupant.username == "test_user_1"
        assert occupant.nickname == "test_nickname"
        assert occupant.iconid == aid1

        # Set the user's per-room nickname and make sure it shows up.
        aid2 = attachmentdata.insert_attachment('local', 'image/png', 'testing2.png', {})
        roomdata.update_room_occupant(room1.id, user.id, "per_room_nickname", aid2)

        occupant = [o for o in roomdata.get_room_occupants(room1.id) if o.username == "test_user_1"][0]
        assert occupant.username == "test_user_1"
        assert occupant.nickname == "per_room_nickname"
        assert occupant.iconid == aid2

        # Finally, verify that if we have an occupant, we can look backwards and get the room they're in.
        fetched = roomdata.get_occupant_room(occupant.id)
        assert fetched is not None
        assert fetched.id == room1.id

    def test_edit_action(self, tx: ConnectionLike) -> None:
        """
        Tests that we can fetch and edit actions, for the purpose of edits and reactions.
        """

        config = MockConfig()
        roomdata = RoomData(config, tx)
        userdata = UserData(config, tx)

        # First, create a room
        room = Room(
            NewRoomID,
            "test edit action",
            "",
            RoomPurpose.ROOM,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room)
        assert room.id != NewRoomID

        # Now, join the room as a user and then add a message.
        user = userdata.create_account("room_edit_action_user", "amazing_password")
        assert user is not None
        roomdata.join_room(room.id, user.id)

        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=user.id,
        )
        newaction = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.MESSAGE,
            details={"message": "this is a test"},
        )
        roomdata.insert_action(room.id, newaction)
        assert newaction.id != NewActionID
        actionid = newaction.id

        # Now, try to fetch that action directly.
        action = roomdata.get_action(actionid)
        assert action is not None
        assert action.id == actionid
        assert action.action == ActionType.MESSAGE
        assert action.details == {"message": "this is a test"}
        assert action.occupant is not None
        assert action.occupant.userid == user.id
        assert action.occupant.username == "room_edit_action_user"

        # Now, attempt to modify the action. Lock the table to test the locking flow, even
        # though we don't really need to lock here.
        with roomdata.lock_actions():
            action.details = {"message": "this is an edit"}
            roomdata.update_action(action)

        # Now, try to fetch that action again.
        action = roomdata.get_action(actionid)
        assert action is not None
        assert action.id == actionid
        assert action.action == ActionType.MESSAGE
        assert action.details == {"message": "this is an edit"}
        assert action.occupant is not None
        assert action.occupant.userid == user.id
        assert action.occupant.username == "room_edit_action_user"

    def test_occupant_room_properties(self, tx: ConnectionLike) -> None:
        """
        Tests that we can fetch and update occupant properties in rooms.
        """

        config = MockConfig()
        roomdata = RoomData(config, tx)
        userdata = UserData(config, tx)

        # First, create a room
        room = Room(
            NewRoomID,
            "test edit action",
            "",
            RoomPurpose.ROOM,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room)
        assert room.id != NewRoomID

        # Now, join the room as a user.
        user = userdata.create_account("room_properties_user", "amazing_password")
        assert user is not None
        roomdata.join_room(room.id, user.id)

        # First, verify that they default to not muted and not moderator.
        occupant = [o for o in roomdata.get_room_occupants(room.id) if o.username == "room_properties_user"][0]
        assert occupant.inactive is True
        assert occupant.present is True
        assert occupant.moderator is False
        assert occupant.muted is False

        # Now, make sure they show up activated once we activate them.
        user.permissions.add(UserPermission.ACTIVATED)
        userdata.update_user(user)
        occupant = [o for o in roomdata.get_room_occupants(room.id) if o.username == "room_properties_user"][0]
        assert occupant.inactive is False
        assert occupant.present is True
        assert occupant.moderator is False
        assert occupant.muted is False

        # Now, mute the user.
        roomdata.mute_room_occupant(room.id, occupant.userid)
        occupant = [o for o in roomdata.get_room_occupants(room.id) if o.username == "room_properties_user"][0]
        assert occupant.inactive is False
        assert occupant.present is True
        assert occupant.moderator is False
        assert occupant.muted is True

        # Now moderate them.
        roomdata.grant_room_moderator(room.id, occupant.userid)
        occupant = [o for o in roomdata.get_room_occupants(room.id) if o.username == "room_properties_user"][0]
        assert occupant.inactive is False
        assert occupant.present is True
        assert occupant.moderator is True
        assert occupant.muted is True

        # Now, unmute them.
        roomdata.unmute_room_occupant(room.id, occupant.userid)
        occupant = [o for o in roomdata.get_room_occupants(room.id) if o.username == "room_properties_user"][0]
        assert occupant.inactive is False
        assert occupant.present is True
        assert occupant.moderator is True
        assert occupant.muted is False

        # Now unmoderate them.
        roomdata.revoke_room_moderator(room.id, occupant.userid)
        occupant = [o for o in roomdata.get_room_occupants(room.id) if o.username == "room_properties_user"][0]
        assert occupant.inactive is False
        assert occupant.present is True
        assert occupant.moderator is False
        assert occupant.muted is False

        # Finally, leave the room and make sure they're not present.
        roomdata.leave_room(room.id, occupant.userid)
        occupant = [o for o in roomdata.get_room_occupants(room.id, include_left=True) if o.username == "room_properties_user"][0]
        assert occupant.inactive is False
        assert occupant.present is False
        assert occupant.moderator is False
        assert occupant.muted is False

        # And, ensure that they don't show up in the list without specifically requesting them.
        assert [] == [o for o in roomdata.get_room_occupants(room.id) if o.username == "room_properties_user"]

    def test_room_invites(self, tx: ConnectionLike) -> None:
        """
        Tests room invite infrastructure.
        """

        config = MockConfig()
        roomdata = RoomData(config, tx)
        userdata = UserData(config, tx)

        # First, create a room
        room = Room(
            NewRoomID,
            "test edit action",
            "",
            RoomPurpose.ROOM,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room)
        assert room.id != NewRoomID

        # Now, join that room as a user who will be giving invites.
        inviter = userdata.create_account("room_invites_inviter", "amazing_password")
        assert inviter is not None
        roomdata.join_room(room.id, inviter.id)

        # And create somebody who will be receiving invites.
        invitee = userdata.create_account("room_invites_invitee", "amazing_password")
        assert invitee is not None

        # Make sure neither can see any room invites since there are none outstanding.
        assert [] == roomdata.get_room_invites(inviter.id)
        assert [] == roomdata.get_room_invites(invitee.id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert not roomdata.is_invited_to_room(room.id, invitee.id)

        # Verify that we haven't gotten any invite updates.
        ts_and_cnt = roomdata.get_last_invite_update()
        assert ts_and_cnt is None

        # Now, send an invite from the inviter to the invitee.
        roomdata.grant_room_invite(room.id, invitee.id, inviter.id)

        # Verify that they got the invite.
        assert [] == roomdata.get_room_invites(inviter.id)
        invites = roomdata.get_room_invites(invitee.id)
        assert len(invites) == 1
        assert invites[0].active is True
        assert invites[0].seen is False
        assert invites[0].room is not None
        assert invites[0].room.id == room.id
        assert invites[0].userid == inviter.id

        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert roomdata.is_invited_to_room(room.id, invitee.id)

        # We should get an invite update now.
        ts_and_cnt = roomdata.get_last_invite_update()
        assert ts_and_cnt is not None
        ts, cnt = ts_and_cnt

        assert cnt == 1
        assert not roomdata.has_updated_invites(inviter.id, ts, 0)
        assert roomdata.has_updated_invites(invitee.id, ts, 0)

        # Now, revoke the invite (uninvite the user).
        roomdata.revoke_room_invite(room.id, invitee.id, inviter.id)

        # Make sure we're back to not having any invites.
        assert [] == roomdata.get_room_invites(inviter.id)
        assert [] == roomdata.get_room_invites(invitee.id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert not roomdata.is_invited_to_room(room.id, invitee.id)

        # And make sure we get updates for this.
        assert not roomdata.has_updated_invites(inviter.id, ts, 0)
        assert roomdata.has_updated_invites(invitee.id, ts, 1)

        ts_and_cnt = roomdata.get_last_invite_update()
        assert ts_and_cnt is not None
        ts, cnt = ts_and_cnt
        assert cnt == 1

        # Make sure we can't invite if we're not in the room.
        roomdata.grant_room_invite(room.id, inviter.id, invitee.id)
        assert [] == roomdata.get_room_invites(inviter.id)
        assert [] == roomdata.get_room_invites(invitee.id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert not roomdata.is_invited_to_room(room.id, invitee.id)

        # Make sure invites didn't actually change.
        nts_and_ncnt = roomdata.get_last_invite_update()
        assert nts_and_ncnt is not None
        assert nts_and_ncnt[0] == ts
        assert nts_and_ncnt[1] == cnt

        # Make sure we can't invite somebody who's already in the room.
        roomdata.join_room(room.id, invitee.id)
        roomdata.grant_room_invite(room.id, inviter.id, invitee.id)
        assert [] == roomdata.get_room_invites(inviter.id)
        assert [] == roomdata.get_room_invites(invitee.id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert not roomdata.is_invited_to_room(room.id, invitee.id)

        # Now, leave again and test acknowledging and dismissing invites.
        roomdata.leave_room(room.id, invitee.id)
        roomdata.grant_room_invite(room.id, invitee.id, inviter.id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert roomdata.is_invited_to_room(room.id, invitee.id)

        invites = roomdata.get_room_invites(invitee.id)
        assert len(invites) == 1
        assert invites[0].active is True
        assert invites[0].seen is False

        # Acknowledge the invite so we can mark it as seen.
        roomdata.acknowledge_room_invite(invites[0].id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert roomdata.is_invited_to_room(room.id, invitee.id)

        invites = roomdata.get_room_invites(invitee.id)
        assert len(invites) == 1
        assert invites[0].active is True
        assert invites[0].seen is True

        # Now, dismiss the invite so we can test it as inactive.
        roomdata.dismiss_room_invite(invites[0].id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert roomdata.is_invited_to_room(room.id, invitee.id)

        invites = roomdata.get_room_invites(invitee.id)
        assert len(invites) == 1
        assert invites[0].active is False
        assert invites[0].seen is True

        # Now, join the room, verifying that the invite goes away.
        roomdata.join_room(room.id, invitee.id, inviter=inviter.id)
        assert [] == roomdata.get_room_invites(inviter.id)
        assert [] == roomdata.get_room_invites(invitee.id)
        assert not roomdata.is_invited_to_room(room.id, inviter.id)
        assert not roomdata.is_invited_to_room(room.id, invitee.id)

        # And verify that the inviter was recorded as having added the user.
        history = roomdata.get_room_history(room.id, limit=1)
        inviter_occupant = [o for o in roomdata.get_room_occupants(room.id) if o.userid == inviter.id][0]
        assert len(history) == 1
        assert history[0].action == ActionType.JOIN
        assert history[0].occupant is not None
        assert history[0].occupant.userid == invitee.id
        assert history[0].details == {"actor": inviter_occupant.id}
