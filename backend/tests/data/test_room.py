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
