import pytest
from sqlalchemy.orm import Session

from critterchat.data import (
    NewAttachmentID,
    MetadataType,
)
from critterchat.data.attachment import AttachmentData

from ..mocks import MockConfig


@pytest.mark.integration
class TestAttachmentData:
    def test_attachment_crud(self, tx: Session) -> None:
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

    def test_emote_crud(self, tx: Session) -> None:
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
