from critterchat.http.messagepump import send_emote_deltas
from critterchat.data.types import AttachmentID, MetadataType
from critterchat.data.attachment import Attachment, Emote

from .mocks import MockConfig, MockData, MockSocketIO, Message, set_return, set_lambda


class TestMessagePumpEmotes:
    def test_send_emote_deltas_empty(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()

        emotes: set[str] = set()
        set_return(data.attachment.get_emotes, [])

        emotes = send_emote_deltas(config, data, socketio, emotes)

        assert emotes == set()
        assert socketio.sent == []

    def test_send_emote_deltas_no_change(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()

        emotes: set[str] = {'a', 'b', 'c'}
        set_return(data.attachment.get_emotes, [
            Emote("a", AttachmentID(101), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("b", AttachmentID(102), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("c", AttachmentID(103), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
        ])

        emotes = send_emote_deltas(config, data, socketio, emotes)

        assert emotes == {'a', 'b', 'c'}
        assert socketio.sent == []

    def test_send_emote_deltas_addition(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()

        emotes: set[str] = {'a', 'b', 'c'}
        set_return(data.attachment.get_emotes, [
            Emote("a", AttachmentID(201), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("b", AttachmentID(202), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("c", AttachmentID(203), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("d", AttachmentID(204), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
        ])
        set_lambda(data.attachment.lookup_attachment, lambda aid: (
            Attachment(AttachmentID(204), "local", "image/png", None, {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}) if aid == AttachmentID(204) else None
        ))

        emotes = send_emote_deltas(config, data, socketio, emotes)

        assert emotes == {'a', 'b', 'c', 'd'}
        assert socketio.sent == [
            Message(
                "emotechanges",
                {'additions': {':d:': {'uri': 'http://localhost/attachments/5b86e764755ec92458d8881789088538a93d6268.png', 'dimensions': [32, 32]}}, 'deletions': []},
            ),
        ]

    def test_send_emote_deltas_subtraction(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()

        emotes: set[str] = {'a', 'b', 'c'}
        set_return(data.attachment.get_emotes, [
            Emote("a", AttachmentID(201), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("b", AttachmentID(202), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
        ])

        emotes = send_emote_deltas(config, data, socketio, emotes)

        assert emotes == {'a', 'b'}
        assert socketio.sent == [
            Message(
                "emotechanges",
                {'additions': {}, 'deletions': [':c:']},
            ),
        ]

    def test_send_emote_deltas_addition_subtraction(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()

        emotes: set[str] = {'a', 'b', 'c'}
        set_return(data.attachment.get_emotes, [
            Emote("b", AttachmentID(202), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("c", AttachmentID(203), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
            Emote("d", AttachmentID(204), "local", "image/png", {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}),
        ])
        set_lambda(data.attachment.lookup_attachment, lambda aid: (
            Attachment(AttachmentID(204), "local", "image/png", None, {MetadataType.WIDTH: 32, MetadataType.HEIGHT: 32}) if aid == AttachmentID(204) else None
        ))

        emotes = send_emote_deltas(config, data, socketio, emotes)

        assert emotes == {'b', 'c', 'd'}
        assert socketio.sent == [
            Message(
                "emotechanges",
                {'additions': {':d:': {'uri': 'http://localhost/attachments/5b86e764755ec92458d8881789088538a93d6268.png', 'dimensions': [32, 32]}}, 'deletions': [':a:']},
            ),
        ]
