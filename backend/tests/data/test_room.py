import pytest
from sqlalchemy.orm import Session

from critterchat.data import ActionType, Room, RoomPurpose, RoomID, NewRoomID, NewUserID
from critterchat.data.room import RoomData

from ..mocks import MockConfig


@pytest.mark.integration
class TestRoomData:
    def test_room_crud(self, tx: Session) -> None:
        config = MockConfig()
        roomdata = RoomData(config, tx)

        # First, create a room
        room = Room(
            NewRoomID,
            "test room crud",
            "test room crud topic",
            RoomPurpose.ROOM,
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
