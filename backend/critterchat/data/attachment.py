import contextlib
from sqlalchemy import Table, Column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import String, Integer
from typing import Dict, Iterable, Iterator, List, Optional, Union

from .base import BaseData, metadata
from .types import ActionID, AttachmentID, NewActionID, NewAttachmentID, UserID, NewUserID

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
    def __init__(self, attachmentid: AttachmentID, system: str, content_type: str, original_filename: Optional[str]) -> None:
        self.id = attachmentid
        self.system = system
        self.content_type = content_type
        self.original_filename = original_filename


class Emote:
    def __init__(self, alias: str, attachmentid: AttachmentID, system: str, content_type: str) -> None:
        self.alias = alias
        self.attachmentid = attachmentid
        self.system = system
        self.content_type = content_type


class ActionAttachment:
    def __init__(self, actionid: ActionID, attachmentid: AttachmentID, content_type: str, original_filename: Optional[str]) -> None:
        self.actionid = actionid
        self.attachmentid = attachmentid
        self.content_type = content_type
        self.original_filename = original_filename


class AttachmentData(BaseData):
    def insert_attachment(self, system: str, content_type: str, original_filename: Optional[str]) -> Optional[AttachmentID]:
        """
        Given an attachment system and content type, insert a pointer to that attachment.

        Parameters:
            system - The attachment system used for this attachment.
            content_type - The content type of this attachment.
        """

        sql = """
            INSERT INTO attachment
                (`system`, `content_type`, `original_filename`)
            VALUES
                (:system, :content_type, :filename)
        """
        cursor = self.execute(sql, {
            "system": system, "content_type": content_type, "filename": original_filename
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
            SELECT `system`, `content_type`, `original_filename` FROM attachment WHERE id = :id
        """
        cursor = self.execute(sql, {"id": attachmentid})
        if cursor.rowcount != 1:
            return None

        result = cursor.mappings().fetchone()
        return Attachment(attachmentid, str(result["system"] or ""), str(result["content_type"] or ""), str(result["original_filename"] or "") or None)

    def get_attachments(self) -> List[Attachment]:
        """
        Look up all known attachments in the system.
        """

        sql = """
            SELECT `id`, `system`, `content_type`, `original_filename`
            FROM attachment
        """
        cursor = self.execute(sql, {})
        return [
            Attachment(
                AttachmentID(result['id']),
                str(result['system'] or ""),
                str(result['content_type'] or ""),
                str(result['original_filename'] or "") or None,
            ) for result in cursor.mappings()
        ]

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
                str(result['system'] or ""),
                str(result['content_type'] or ""),
            ) for result in cursor.mappings()
        ]

    def get_emote(self, alias: str) -> Optional[Emote]:
        """
        Look up a custom emote by alias in the DB.
        """

        sql = """
            SELECT
                attachment.id AS attachment_id, attachment.system AS `system`, attachment.content_type AS content_type,
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

    def get_notifications(self, userid: UserID) -> Dict[str, Attachment]:
        """
        Look up all custom notifications for a user.
        """
        if userid is NewUserID:
            return {}

        sql = """
            SELECT
                attachment.id AS attachment_id, attachment.system AS `system`, attachment.content_type AS content_type, attachment.original_filename as filename,
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
            ) for result in cursor.mappings()
        }

    def get_notification(self, userid: UserID, notificationtype: str) -> Optional[Attachment]:
        """
        Look up a custom notification for a user based on type.
        """
        if userid is NewUserID:
            return None

        sql = """
            SELECT
                attachment.id AS attachment_id, attachment.system AS `system`, attachment.content_type AS content_type, attachment.original_filename as filename,
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
        )

    def set_notification(self, userid: UserID, notificationtype: str, attachmentid: AttachmentID) -> None:
        """
        Given a custom notification and an attachment ID, insert or update the notification for a user.
        """
        if userid is NewUserID:
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
        if userid is NewUserID:
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
        sql = "LOCK TABLES attachment WRITE, action_attachment WRITE"
        self.execute(sql, {})
        try:
            yield
        finally:
            sql = "UNLOCK TABLES"
            self.execute(sql, {})

    def get_action_attachments(self, actionid: Union[ActionID, Iterable[ActionID]]) -> Dict[ActionID, List[ActionAttachment]]:
        """
        Look up all action attachments for a given action or actions in the system.
        """
        if actionid is NewActionID:
            return {}

        ids: List[ActionID] = []
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
                attachment.original_filename AS original_filename
            FROM action_attachment
            JOIN attachment ON attachment.id = action_attachment.attachment_id
            WHERE action_attachment.action_id IN :ids
        """
        cursor = self.execute(sql, {"ids": ids})

        retval: Dict[ActionID, List[ActionAttachment]] = {}
        for aid in ids:
            retval[aid] = []

        for result in cursor.mappings():
            attachment = ActionAttachment(
                ActionID(result['action_id']),
                AttachmentID(result['attachment_id']),
                str(result['content_type'] or ""),
                str(result['original_filename'] or "") or None,
            )

            retval[attachment.actionid].append(attachment)

        return retval

    def link_action_attachment(self, actionid: ActionID, attachmentid: AttachmentID) -> None:
        """
        Given an action ID and an attachment ID, create a link between the two for later retrieval.
        """

        if actionid is NewActionID:
            raise Exception("Logic error, should not try to link an action and an attachment with a new action ID!")
        if attachmentid is NewAttachmentID:
            raise Exception("Logic error, should not try to link an action and an attachment with a new attachment ID!")

        sql = """
            INSERT INTO action_attachment (`action_id`, `attachment_id`) VALUES (:actionid, :attachmentid)
        """
        self.execute(sql, {"actionid": actionid, "attachmentid": attachmentid})

    def unlink_action_attachment(self, actionid: ActionID, attachmentid: AttachmentID) -> None:
        """
        Given an action ID and an attachment ID, remove an existinga link between the two.
        """

        if actionid is NewActionID:
            raise Exception("Logic error, should not try to unlink an action and an attachment with a new action ID!")
        if attachmentid is NewAttachmentID:
            raise Exception("Logic error, should not try to unlink an action and an attachment with a new attachment ID!")

        sql = """
            DELETE FROM action_attachment WHERE `action_id` = :actionid AND `attachment_id` = :attachmentid LIMIT 1
        """
        self.execute(sql, {"actionid": actionid, "attachmentid": attachmentid})
