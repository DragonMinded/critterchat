from sqlalchemy import Table, Column
from sqlalchemy.types import String, Integer
from typing import List, Optional

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

"""
Table representing a custom emote.
"""
emote = Table(
    "emote",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("alias", String(64), nullable=False, unique=True),
    Column("attachment_id", Integer),
    mysql_charset="utf8mb4",
)


class Attachment:
    def __init__(self, attachment_id: AttachmentID, system: str, content_type: str) -> None:
        self.id = attachment_id
        self.system = system
        self.content_type = content_type


class Emote:
    def __init__(self, alias: str, attachment_id: AttachmentID, system: str, content_type: str) -> None:
        self.alias = alias
        self.attachment_id = attachment_id
        self.system = system
        self.content_type = content_type


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

    def remove_attachment(self, attachmentid: AttachmentID) -> None:
        """
        Given an attachment ID, remove the reference to it in the DB.
        """
        sql = """
            DELETE FROM attachment WHERE `id` = :attachmentid LIMIT 1
        """
        self.execute(sql, {"attachmentid": attachmentid})

    def lookup_attachment(self, attachmentid: AttachmentID) -> Optional[Attachment]:
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
        return Attachment(attachmentid, str(result["system"]), str(result["content_type"]))

    def get_emotes(self) -> List[Emote]:
        """
        Look up all custom emotes in the DB.
        """

        sql = """
            SELECT
                attachment.id AS attachment_id, attachment.system AS `system`, attachment.content_type AS content_type,
                emote.alias AS alias
            FROM emote
            JOIN attachment ON attachment.id = emote.attachment_id
        """
        cursor = self.execute(sql, {})
        return [
            Emote(
                result['alias'],
                AttachmentID(result['attachment_id']),
                result['system'],
                result['content_type'],
            ) for result in cursor.mappings()
        ]

    def add_emote(self, alias: str, attachmentid: AttachmentID) -> None:
        """
        Given an alias and an attachment ID, insert a new emote.
        """

        sql = """
            INSERT INTO emote (`alias`, `attachment_id`) VALUES (:alias, :attachmentid)
        """
        self.execute(sql, {"alias": alias, "attachmentid": attachmentid})

    def remove_emote(self, alias: str) -> None:
        sql = """
            DELETE FROM emote WHERE `alias` = :alias LIMIT 1
        """
        self.execute(sql, {"alias": alias})
