import pytest

from critterchat.common import Time
from critterchat.data import (
    ConnectionLike,
    NewActionID,
    NewAttachmentID,
    NewOccupantID,
    NewRoomID,
    Action,
    ActionType,
    MetadataType,
    Occupant,
    Room,
    RoomPurpose,
)
from critterchat.data.attachment import AttachmentData
from critterchat.data.room import RoomData
from critterchat.data.user import UserData

from ..mocks import MockConfig


@pytest.mark.integration
class TestAttachmentData:
    def test_attachment_crud(self, tx: ConnectionLike) -> None:
        """
        Tests basic create, retrieve, update, delete for generic attachments in the system.
        """

        config = MockConfig()
        attachmentdata = AttachmentData(config, tx)

        # Verify that we have no attachments in the system.
        attachments = attachmentdata.get_attachments()
        assert attachments == []
        attachment = attachmentdata.lookup_attachment(NewAttachmentID)
        assert attachment is None

        # Now, create an attachment.
        aid = attachmentdata.insert_attachment('local', 'text/plain', 'test.txt', {})
        assert aid is not None

        # Now, look up that attachment.
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is not None
        assert attachment.id == aid
        assert attachment.system == "local"
        assert attachment.content_type == "text/plain"
        assert attachment.original_filename == "test.txt"
        assert attachment.metadata == {}

        # And verify that we can list it using the attachment list.
        attachments = attachmentdata.get_attachments()
        assert len(attachments) == 1
        assert attachments[0].id == aid

        # Ensure that messing with a new attachment ID doesn't change any existing data.
        attachmentdata.overwrite_attachment_metadata(NewAttachmentID, {MetadataType.ALT_TEXT: "this is alt text"})
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is not None
        assert attachment.id == aid
        assert attachment.system == "local"
        assert attachment.content_type == "text/plain"
        assert attachment.original_filename == "test.txt"
        assert attachment.metadata == {}

        attachmentdata.update_attachment_metadata(NewAttachmentID, {MetadataType.SENSITIVE: True})
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is not None
        assert attachment.id == aid
        assert attachment.system == "local"
        assert attachment.content_type == "text/plain"
        assert attachment.original_filename == "test.txt"
        assert attachment.metadata == {}

        attachmentdata.remove_attachment(NewAttachmentID)
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is not None
        assert attachment.id == aid
        assert attachment.system == "local"
        assert attachment.content_type == "text/plain"
        assert attachment.original_filename == "test.txt"
        assert attachment.metadata == {}

        # Now, wholesale update the attachment's metadata and ensure that it's present when fetching.
        attachmentdata.overwrite_attachment_metadata(aid, {MetadataType.ALT_TEXT: "this is alt text"})
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is not None
        assert attachment.id == aid
        assert attachment.system == "local"
        assert attachment.content_type == "text/plain"
        assert attachment.original_filename == "test.txt"
        assert attachment.metadata == {MetadataType.ALT_TEXT: "this is alt text"}

        # Now, update attachment metadata without a strict overwrite.
        attachmentdata.update_attachment_metadata(aid, {MetadataType.SENSITIVE: True})
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is not None
        assert attachment.id == aid
        assert attachment.system == "local"
        assert attachment.content_type == "text/plain"
        assert attachment.original_filename == "test.txt"
        assert attachment.metadata == {MetadataType.ALT_TEXT: "this is alt text", MetadataType.SENSITIVE: True}

        attachmentdata.update_attachment_metadata(aid, {MetadataType.SENSITIVE: False})
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is not None
        assert attachment.id == aid
        assert attachment.system == "local"
        assert attachment.content_type == "text/plain"
        assert attachment.original_filename == "test.txt"
        assert attachment.metadata == {MetadataType.ALT_TEXT: "this is alt text", MetadataType.SENSITIVE: False}

        # Now, remove the attachment and verify it no longer appears in the DB.
        attachmentdata.remove_attachment(aid)
        attachment = attachmentdata.lookup_attachment(aid)
        assert attachment is None
        attachments = attachmentdata.get_attachments()
        assert attachments == []

    def test_emote_crud(self, tx: ConnectionLike) -> None:
        """
        Tests basic create, retrieve, update, delete for emotes in the system.
        """

        config = MockConfig()
        attachmentdata = AttachmentData(config, tx)

        # First ensure that the DB is actually empty, as expected.
        emotes = attachmentdata.get_emotes()
        assert emotes == []
        emote = attachmentdata.get_emote('testing')
        assert emote is None

        # Now, insert a new emote and then try to look it up.
        aid = attachmentdata.insert_attachment('local', 'image/png', 'testing.png', {})
        assert aid is not None
        attachmentdata.add_emote('testing', aid)

        # Now, look it up!
        emote = attachmentdata.get_emote('testing')
        assert emote is not None
        assert emote.alias == "testing"
        assert emote.attachmentid == aid
        assert emote.system == "local"
        assert emote.content_type == "image/png"
        assert emote.metadata == {}

        # Also ensure it's in the list of all emotes.
        emotes = attachmentdata.get_emotes()
        assert len(emotes) == 1
        assert emotes[0].alias == "testing"
        assert emotes[0].attachmentid == aid

        # Also, attempt to look up an invalid emote.
        emote = attachmentdata.get_emote('another')
        assert emote is None

        # Now, remove the emote and ensure it's not there anymore.
        attachmentdata.remove_emote('testing')
        attachmentdata.remove_attachment(aid)
        emote = attachmentdata.get_emote('testing')
        assert emote is None
        emotes = attachmentdata.get_emotes()
        assert emotes == []

    def test_notification_crud(self, tx: ConnectionLike) -> None:
        """
        Tests basic create, retrieve, update, delete for notifications in the system.
        """

        config = MockConfig()
        attachmentdata = AttachmentData(config, tx)
        userdata = UserData(config, tx)

        # We need a couple users to test notifications with.
        user1 = userdata.create_account('notification_test_1', 'best_password')
        user2 = userdata.create_account('notification_test_2', 'best_password')
        assert user1 is not None
        assert user2 is not None

        # Ensure that neither user has notifications.
        notifications = attachmentdata.get_notifications(user1.id)
        assert notifications == {}
        notifications = attachmentdata.get_notifications(user2.id)
        assert notifications == {}

        # Add a notification to the first user, ensure we can fetch it.
        aid = attachmentdata.insert_attachment('local', 'audio/mpeg', 'testing.mp3', {})
        assert aid is not None
        attachmentdata.set_notification(user1.id, 'testing', aid)

        notifications = attachmentdata.get_notifications(user1.id)
        assert set(notifications.keys()) == {'testing'}
        assert notifications['testing'].id == aid
        assert notifications['testing'].system == "local"
        assert notifications['testing'].content_type == "audio/mpeg"
        assert notifications['testing'].original_filename == "testing.mp3"
        assert notifications['testing'].metadata == {}
        notification = attachmentdata.get_notification(user1.id, 'testing')
        assert notification is not None
        assert notification.id == aid
        assert notification.system == "local"
        assert notification.content_type == "audio/mpeg"
        assert notification.original_filename == "testing.mp3"
        assert notification.metadata == {}

        # Also be sure that the other user is not affected, and that other notifications aren't either.
        notification = attachmentdata.get_notification(user1.id, 'another')
        assert notification is None
        notification = attachmentdata.get_notification(user2.id, 'testing')
        assert notification is None
        notifications = attachmentdata.get_notifications(user2.id)
        assert notifications == {}

        # Ensure removing isn't cross-coupled.
        attachmentdata.remove_notification(user2.id, 'testing')
        notification = attachmentdata.get_notification(user1.id, 'testing')
        assert notification is not None

        # Now, remove the notification, ensure we can't find it anymore.
        attachmentdata.remove_notification(user1.id, 'testing')
        attachmentdata.remove_attachment(aid)
        notification = attachmentdata.get_notification(user1.id, 'testing')
        assert notification is None

        notifications = attachmentdata.get_notifications(user1.id)
        assert notifications == {}
        notifications = attachmentdata.get_notifications(user2.id)
        assert notifications == {}

    def test_action_attachment_linking(self, tx: ConnectionLike) -> None:
        """
        Tests linking, unlinking and fetching attachments for an action in the system.
        """

        config = MockConfig()
        attachmentdata = AttachmentData(config, tx)
        userdata = UserData(config, tx)
        roomdata = RoomData(config, tx)

        # To link an attachment to an action, we need so many things. We need an action,
        # which necessitates a room and an occupant, which then necessitates a user.
        user = userdata.create_account('action_link_test', 'best_password')
        assert user is not None

        room = Room(
            NewRoomID,
            "action link room",
            "action link room topic",
            RoomPurpose.ROOM,
            False,
            False,
            None,
            None,
        )
        roomdata.create_room(room)
        assert room.id != NewRoomID

        roomdata.join_room(room.id, user.id)

        # Create two actions so we can differentiate later.
        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=user.id,
        )
        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.MESSAGE,
            details={"message": "this is a test"},
        )
        roomdata.insert_action(room.id, action)
        assert action.id != NewActionID
        action1 = action.id

        occupant = Occupant(
            occupantid=NewOccupantID,
            userid=user.id,
        )
        action = Action(
            actionid=NewActionID,
            timestamp=Time.now(),
            occupant=occupant,
            action=ActionType.MESSAGE,
            details={"message": "this is a second test"},
        )
        roomdata.insert_action(room.id, action)
        assert action.id != NewActionID
        action2 = action.id

        # Now, we need an attachment to link.
        aid = attachmentdata.insert_attachment('local', 'image/png', 'testing.png', {})
        assert aid is not None

        # First, ensure that neither action has any detected attachments.
        attachments = attachmentdata.get_action_attachments(action1)
        assert attachments == {action1: []}
        attachments = attachmentdata.get_action_attachments(action2)
        assert attachments == {action2: []}
        attachments = attachmentdata.get_action_attachments([action1, action2])
        assert attachments == {action1: [], action2: []}

        # Now, link an attachment to the first action.
        with attachmentdata.lock_action_attachments():
            attachmentdata.link_action_attachment(action1, aid)

        # Now, verify that we can reach this attachment.
        attachments = attachmentdata.get_action_attachments(action1)
        assert set(attachments.keys()) == {action1}
        assert len(attachments[action1]) == 1
        assert attachments[action1][0].actionid == action1
        assert attachments[action1][0].attachmentid == aid
        assert attachments[action1][0].content_type == "image/png"
        assert attachments[action1][0].original_filename == "testing.png"
        assert attachments[action1][0].metadata == {}

        attachments = attachmentdata.get_action_attachments(action2)
        assert attachments == {action2: []}
        attachments = attachmentdata.get_action_attachments([action1, action2])
        assert set(attachments.keys()) == {action1, action2}
        assert len(attachments[action1]) == 1
        assert attachments[action1][0].actionid == action1
        assert attachments[action1][0].attachmentid == aid
        assert attachments[action1][0].content_type == "image/png"
        assert attachments[action1][0].original_filename == "testing.png"
        assert attachments[action1][0].metadata == {}
        assert len(attachments[action2]) == 0

        # Now, unlink that attachment and verify again.
        with attachmentdata.lock_action_attachments():
            attachmentdata.unlink_action_attachment(action1, aid)

        attachments = attachmentdata.get_action_attachments(action1)
        assert attachments == {action1: []}
        attachments = attachmentdata.get_action_attachments(action2)
        assert attachments == {action2: []}
        attachments = attachmentdata.get_action_attachments([action1, action2])
        assert attachments == {action1: [], action2: []}
