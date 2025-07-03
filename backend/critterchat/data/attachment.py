from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer
from typing import Optional, Tuple

from .base import BaseData, metadata
from .types import AttachmentID, NewAttachmentID

"""
Table representing an attachment.
"""
attachment = Table(
    "attachment",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("system", String(32), nullable=False),
    Column("content_type", String(128), nullable=False),
    mysql_charset="utf8mb4",
)


class AttachmentData(BaseData):
    def insert_attachment(self, system: str, content_type: str) -> Optional[AttachmentID]:
        """
        Given an attachment system and content type, insert a pointer to that attachment.

        Parameters:
            system - The attachment system used for this attachment.
            content_type - The content type of this attachment.
        """

        sql = """
            INSERT INTO attachment
                (`system`, `content_type`)
            VALUES
                (:system, :content_type)
        """
        cursor = self.execute(sql, {
            "system": system, "content_type": content_type,
        })
        if cursor.rowcount != 1:
            return None

        return AttachmentID(cursor.lastrowid)

    def lookup_attachment(self, attachmentid: AttachmentID) -> Optional[Tuple[str, str]]:
        """
        Given an attachment ID, return that attachment's system and content type.

        Parameters:
            attachmentid - The attachment ID we're curious about.
        """

        if attachmentid is NewAttachmentID:
            return None

        sql = """
            SELECT `system`, `content_type` FROM attachment WHERE id = :id
        """
        cursor = self.execute(sql, {"id": attachmentid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return (str(result["system"]), str(result["content_type"]))
