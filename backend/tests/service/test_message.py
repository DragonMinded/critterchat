import pytest

from critterchat.config import Config
from critterchat.data import (
    ConnectionLike,
    Data,
    ActionType,
)
from critterchat.service.message import MessageService


@pytest.mark.integration
class TestMessageService:
    def test_message_attachments(self, config: Config, tx: ConnectionLike) -> None:
        """
        Tests a regression found when adding SQLite backend, to ensure attachments get linked to messages.
        """

        data = Data(config, tx)
        ms = MessageService(config, data)

        # First, create a user
        user = data.user.create_account("test_message_attachments_user", "amazing_password")
        assert user is not None

        # ...and a room
        room = ms.create_public_room("test message attachments", "", None)

        # Now, join the room as a user and attempt to send a message.
        ms.join_room(room.id, user.id)

        # Create an attachment to attach to the message we're going to send.
        aid = data.attachment.insert_attachment('local', 'image/png', 'testing.png', {})
        assert aid is not None

        action = ms.add_message(room.id, user.id, "this is a test", False, [aid])
        assert action is not None

        # Verify the action is what we expected.
        assert action.action == ActionType.MESSAGE
        assert action.occupant is not None
        assert action.occupant.userid == user.id
        assert action.details == {"message": "this is a test", "reactions": {}}
        assert len(action.attachments) == 1
        assert action.attachments[0].id == aid
        assert action.attachments[0].mimetype == "image/png"
