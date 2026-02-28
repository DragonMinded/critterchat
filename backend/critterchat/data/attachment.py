import contextlib
import json
from sqlalchemy import Table, Column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import String, Integer, JSON
from typing import Iterable, Iterator

from .base import BaseData, metadata
from .types import MetadataType, ActionID, AttachmentID, NewActionID, NewAttachmentID, UserID, NewUserID

"""
Table representing an attachment.
"""
attachment = Table(
    "attachment",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("system", String(32), nullable=False),
    Column("content_type", String(128), nullable=False),
    Column("original_filename", String(256), nullable=True),
    Column("metadata", JSON),
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

"""
Table representing a user's custom notification sounds.
"""
notification = Table(
    "notification",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("type", String(64), nullable=False),
    Column("attachment_id", Integer),
    UniqueConstraint("user_id", "type", name="user_id_type"),
    mysql_charset="utf8mb4",
)

"""
Table representing an action's attachments, such as images or files.
"""
action_attachment = Table(
    "action_attachment",
    metadata,
    Column("id", Integer, nullable=False, primary_key=True, autoincrement=True),
    Column("action_id", Integer, nullable=False, index=True),
    Column("attachment_id", Integer, nullable=False),
    UniqueConstraint("action_id", "attachment_id", name="action_id_attachment_id"),
    mysql_charset="utf8mb4",
)


class Attachment:
    def __init__(
        self,
        attachmentid: AttachmentID,
        system: str,
        content_type: str,
        original_filename: str | None,
        metadata: dict[MetadataType, object],
    ) -> None:
        self.id = attachmentid
        self.system = system
        self.content_type = content_type
        self.original_filename = original_filename
        self.metadata = metadata


class Emote:
    def __init__(
        self,
        alias: str,
        attachmentid: AttachmentID,
        system: str,
        content_type: str,
        metadata: dict[MetadataType, object],
    ) -> None:
        self.alias = alias
        self.attachmentid = attachmentid
        self.system = system
        self.content_type = content_type
        self.metadata = metadata


class ActionAttachment:
    def __init__(
        self,
        actionid: ActionID,
        attachmentid: AttachmentID,
        content_type: str,
        original_filename: str | None,
        metadata: dict[MetadataType, object],
    ) -> None:
        self.actionid = actionid
        self.attachmentid = attachmentid
        self.content_type = content_type
        self.original_filename = original_filename
        self.metadata = metadata


class AttachmentData(BaseData):
    def insert_attachment(
        self,
        system: str,
        content_type: str,
        original_filename: str | None,
        metadata: dict[MetadataType, object],
    ) -> AttachmentID | None:
        """
        Given an attachment system and content type, insert a pointer to that attachment.

        Parameters:
            system - The attachment system used for this attachment.
            content_type - The content type of this attachment.
            original_filename - The original filename of the attachment, if applicable.
            metadata - Any metadata about the attachment, such as dimensions.
        """

        sql = """
            INSERT INTO attachment
                (`system`, `content_type`, `original_filename`, `metadata`)
            VALUES
                (:system, :content_type, :filename, :metadata)
        """
        cursor = self.execute(sql, {
            "system": system,
            "content_type": content_type,
            "filename": original_filename,
            "metadata": json.dumps(metadata),
        })
        if cursor.rowcount != 1:
            return None

        return AttachmentID(cursor.lastrowid)

    def overwrite_attachment_metadata(self, attachmentid: AttachmentID, metadata: dict[MetadataType, object]) -> None:
        """
        Given an existing attachment, completely overwrite it's metadata. Normally
        never called, but can be necessary during migrations to backfill missing metadata.
        Note that this completely overwrites the metadata with new metadata.
        """

        sql = """
            UPDATE attachment
            SET metadata = :metadata
            WHERE id = :id
            LIMIT 1
        """
        self.execute(sql, {"id": attachmentid, "metadata": json.dumps(metadata)})

    def update_attachment_metadata(self, attachmentid: AttachmentID, metadata: dict[MetadataType, object]) -> None:
        """
        Given an existing attachment, update it's metadata. Normally never called, but
        can be necessary during migrations to backfill missing metadata. Note that this
        does not update any metadata not explicitly specified in the incoming metadata
        dictionary, so it's safe to only update the values you want to change.
        """

        with self.transaction():
            sql = "SELECT metadata FROM attachment WHERE id = :id"
            cursor = self.execute(sql, {"id": attachmentid})
            if cursor.rowcount != 1:
                existing = {}
            else:
                result = cursor.mappings().fetchone()
                existing = json.loads(str(result["metadata"] or "{}"))

            existing = {**existing, **metadata}
            sql = """
                UPDATE attachment
                SET metadata = :metadata
                WHERE id = :id
                LIMIT 1
            """
            self.execute(sql, {"id": attachmentid, "metadata": json.dumps(existing)})

    def remove_attachment(self, attachmentid: AttachmentID) -> None:
        """
        Given an attachment ID, remove the reference to it in the DB.
        """
        sql = """
            DELETE FROM attachment WHERE `id` = :attachmentid LIMIT 1
        """
        self.execute(sql, {"attachmentid": attachmentid})

    def lookup_attachment(self, attachmentid: AttachmentID) -> Attachment | None:
        """
        Given an attachment ID, return that attachment's system and content type.

        Parameters:
            attachmentid - The attachment ID we're curious about.
        """

        if attachmentid == NewAttachmentID:
            return None

        sql = """
            SELECT `system`, `content_type`, `original_filename`, `metadata` FROM attachment WHERE id = :id
        """
        cursor = self.execute(sql, {"id": attachmentid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return Attachment(
            attachmentid,
            str(result["system"] or ""),
            str(result["content_type"] or ""),
            str(result["original_filename"] or "") or None,
            json.loads(str(result["metadata"] or "{}")),
        )

    def get_attachments(self) -> list[Attachment]:
        """
        Look up all known attachments in the system.
        """

        sql = """
            SELECT `id`, `system`, `content_type`, `original_filename`, `metadata`
            FROM attachment
        """
        cursor = self.execute(sql)
        return [
            Attachment(
                AttachmentID(result['id']),
                str(result['system'] or ""),
                str(result['content_type'] or ""),
                str(result['original_filename'] or "") or None,
                json.loads(str(result["metadata"] or "{}")),
            ) for result in cursor.mappings()
        ]

    def get_emotes(self) -> list[Emote]:
        """
        Look up all custom emotes in the DB.
        """

        sql = """
            SELECT
                attachment.id AS attachment_id,
                attachment.system AS `system`,
                attachment.content_type AS content_type,
                attachment.metadata AS metadata,
                emote.alias AS alias
            FROM emote
            JOIN attachment ON attachment.id = emote.attachment_id
        """
        cursor = self.execute(sql)
        return [
            Emote(
                result['alias'],
                AttachmentID(result['attachment_id']),
                str(result['system'] or ""),
                str(result['content_type'] or ""),
                json.loads(str(result["metadata"] or "{}")),
            ) for result in cursor.mappings()
        ]

    def get_emote(self, alias: str) -> Emote | None:
        """
        Look up a custom emote by alias in the DB.
        """

        sql = """
            SELECT
                attachment.id AS attachment_id,
                attachment.system AS `system`,
                attachment.content_type AS content_type,
                attachment.metadata AS metadata,
                emote.alias AS alias
            FROM emote
            JOIN attachment ON attachment.id = emote.attachment_id
            WHERE emote.alias = :alias
        """
        cursor = self.execute(sql, {"alias": alias})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return Emote(
            result['alias'],
            AttachmentID(result['attachment_id']),
            str(result['system'] or ""),
            str(result['content_type'] or ""),
            json.loads(str(result["metadata"] or "{}")),
        )

    def add_emote(self, alias: str, attachmentid: AttachmentID) -> None:
        """
        Given an alias and an attachment ID, insert a new emote.
        """

        sql = """
            INSERT INTO emote (`alias`, `attachment_id`) VALUES (:alias, :attachmentid)
        """
        self.execute(sql, {"alias": alias, "attachmentid": attachmentid})

    def remove_emote(self, alias: str) -> None:
        """
        Given an alias for an existing emote, remove it from our tracking list.
        """

        sql = """
            DELETE FROM emote WHERE `alias` = :alias LIMIT 1
        """
        self.execute(sql, {"alias": alias})

    def get_notifications(self, userid: UserID) -> dict[str, Attachment]:
        """
        Look up all custom notifications for a user.
        """
        if userid == NewUserID:
            return {}

        sql = """
            SELECT
                attachment.id AS attachment_id,
                attachment.system AS `system`,
                attachment.content_type AS content_type,
                attachment.original_filename as filename,
                attachment.metadata AS metadata,
                notification.type AS type
            FROM notification
            JOIN attachment ON attachment.id = notification.attachment_id
            WHERE notification.user_id = :userid
        """
        cursor = self.execute(sql, {"userid": userid})
        return {
            str(result['type']): Attachment(
                AttachmentID(result['attachment_id']),
                str(result['system'] or ""),
                str(result['content_type'] or ""),
                str(result['filename'] or "") or None,
                json.loads(str(result["metadata"] or "{}")),
            ) for result in cursor.mappings()
        }

    def get_notification(self, userid: UserID, notificationtype: str) -> Attachment | None:
        """
        Look up a custom notification for a user based on type.
        """
        if userid == NewUserID:
            return None

        sql = """
            SELECT
                attachment.id AS attachment_id,
                attachment.system AS `system`,
                attachment.content_type AS content_type,
                attachment.original_filename as filename,
                attachment.metadata AS metadata,
                notification.type AS type
            FROM notification
            JOIN attachment ON attachment.id = notification.attachment_id
            WHERE notification.user_id = :userid AND notification.type = :type
        """
        cursor = self.execute(sql, {"userid": userid, "type": notificationtype})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return Attachment(
            AttachmentID(result['attachment_id']),
            str(result['system'] or ""),
            str(result['content_type'] or ""),
            str(result['filename'] or "") or None,
            json.loads(str(result["metadata"] or "{}")),
        )

    def set_notification(self, userid: UserID, notificationtype: str, attachmentid: AttachmentID) -> None:
        """
        Given a custom notification and an attachment ID, insert or update the notification for a user.
        """
        if userid == NewUserID:
            return

        sql = """
            INSERT INTO notification (`user_id`, `type`, `attachment_id`)
            VALUES (:userid, :type, :aid)
            ON DUPLICATE KEY UPDATE `attachment_id` = :aid
        """
        self.execute(sql, {"userid": userid, "type": notificationtype, "aid": attachmentid})

    def remove_notification(self, userid: UserID, notificationtype: str) -> None:
        """
        Remove any existing notification of this type for this user.
        """
        if userid == NewUserID:
            return

        sql = """
            DELETE FROM notification WHERE `user_id` = :userid AND `type` = :type LIMIT 1
        """
        self.execute(sql, {"userid": userid, "type": notificationtype})

    @contextlib.contextmanager
    def lock_action_attachments(self) -> Iterator[None]:
        """
        Locks the action attachments table for exclusive write, when needing to attach data to a new
        attachment without other clients polling incomplete actions. Use in a with block.
        """
        self.execute("LOCK TABLES attachment WRITE, action_attachment WRITE")
        try:
            yield
        finally:
            self.execute("UNLOCK TABLES")

    def get_action_attachments(self, actionid: ActionID | Iterable[ActionID]) -> dict[ActionID, list[ActionAttachment]]:
        """
        Look up all action attachments for a given action or actions in the system.
        """
        if actionid == NewActionID:
            return {}

        ids: list[ActionID] = []
        try:
            ids = [x for x in actionid]  # type: ignore
        except TypeError:
            ids = [actionid]  # type: ignore

        if not ids:
            return {}

        sql = """
            SELECT
                action_attachment.action_id AS action_id,
                attachment.id AS attachment_id,
                attachment.content_type AS content_type,
                attachment.original_filename AS original_filename,
                attachment.metadata AS metadata
            FROM action_attachment
            JOIN attachment ON attachment.id = action_attachment.attachment_id
            WHERE action_attachment.action_id IN :ids
        """
        cursor = self.execute(sql, {"ids": ids})

        retval: dict[ActionID, list[ActionAttachment]] = {}
        for aid in ids:
            retval[aid] = []

        for result in cursor.mappings():
            attachment = ActionAttachment(
                actionid=ActionID(result['action_id']),
                attachmentid=AttachmentID(result['attachment_id']),
                content_type=str(result['content_type'] or ""),
                original_filename=str(result['original_filename'] or "") or None,
                metadata=json.loads(str(result["metadata"] or "{}")),
            )

            retval[attachment.actionid].append(attachment)

        return retval

    def link_action_attachment(self, actionid: ActionID, attachmentid: AttachmentID) -> None:
        """
        Given an action ID and an attachment ID, create a link between the two for later retrieval.
        """

        if actionid == NewActionID:
            raise Exception("Logic error, should not try to link an action and an attachment with a new action ID!")
        if attachmentid == NewAttachmentID:
            raise Exception("Logic error, should not try to link an action and an attachment with a new attachment ID!")

        sql = """
            INSERT INTO action_attachment (`action_id`, `attachment_id`) VALUES (:actionid, :attachmentid)
        """
        self.execute(sql, {"actionid": actionid, "attachmentid": attachmentid})

    def unlink_action_attachment(self, actionid: ActionID, attachmentid: AttachmentID) -> None:
        """
        Given an action ID and an attachment ID, remove an existinga link between the two.
        """

        if actionid == NewActionID:
            raise Exception("Logic error, should not try to unlink an action and an attachment with a new action ID!")
        if attachmentid == NewAttachmentID:
            raise Exception("Logic error, should not try to unlink an action and an attachment with a new attachment ID!")

        sql = """
            DELETE FROM action_attachment WHERE `action_id` = :actionid AND `attachment_id` = :attachmentid LIMIT 1
        """
        self.execute(sql, {"actionid": actionid, "attachmentid": attachmentid})
