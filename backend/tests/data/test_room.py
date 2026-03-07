import pytest
from sqlalchemy.orm import Session

from critterchat.data import ActionType, Room, RoomPurpose, RoomID, NewRoomID, NewUserID, UserPermission
from critterchat.data.room import RoomData
from critterchat.data.user import UserData

from ..mocks import MockConfig


@pytest.mark.integration
class TestRoomData:
    def test_room_crud(self, tx: Session) -> None:
        """
        Tests basic create, retrieve, update, delete for rooms in the system.
        """

        config = MockConfig()
        roomdata = RoomData(config, tx)

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

        # Ensure that reading actions for this room shows the updated action from updating the room.
        history = roomdata.get_room_history(room.id)
        assert len(history) == 1
        assert history[0].action == ActionType.CHANGE_INFO

        # No delete because we do not delete rooms currently.

    def test_get_joined_rooms(self, tx: Session) -> None:
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

    def test_get_room_occupants(self, tx: Session) -> None:
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
