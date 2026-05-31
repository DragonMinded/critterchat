import pytest
from freezegun import freeze_time
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

        with freeze_time("2026-01-01 6:00:00"):
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
