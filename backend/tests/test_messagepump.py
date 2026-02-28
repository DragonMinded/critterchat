from critterchat.common import Time
from critterchat.data.types import AttachmentID, UserID, MetadataType, UserPermission, UserPreferences, User
from critterchat.data.attachment import Attachment, Emote
from critterchat.http.messagepump import SocketInfo, send_emote_deltas, send_profile_deltas

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


class TestMessagePumpUser:
    def test_send_profile_deltas_no_change(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        now = Time.now()
        info.profilets = now
        info.prefsts = now

        set_return(data.user.has_updated_user, False)
        set_return(data.user.has_updated_preferences, False)

        send_profile_deltas(config, data, socketio, info)

        assert socketio.sent == []

    def test_send_profile_deltas_profile_change(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        now = Time.now()
        info.profilets = now
        info.prefsts = now

        set_return(data.user.has_updated_user, True)
        set_return(data.user.has_updated_preferences, False)
        set_return(data.user.get_user, User(UserID(100), "testusername", set(), "testuser", "about me", None))

        send_profile_deltas(config, data, socketio, info)

        assert socketio.sent == [
            Message(
                'profile',
                {
                    'id': 'u100',
                    'username': 'testusername',
                    'nickname': 'testuser',
                    'about': 'about me',
                    'icon': 'http://localhost/attachments/defavi',
                    'full_username': '@testusername@localhost',
                },
                'testsid',
            )
        ]

    def test_send_profile_deltas_profile_change_admin(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(101))

        now = Time.now()
        info.profilets = now
        info.prefsts = now

        # In this case, the user being an admin means they should be able to see extra properties on the profile.
        set_return(data.user.has_updated_user, True)
        set_return(data.user.has_updated_preferences, False)
        set_return(data.user.get_user, User(UserID(101), "testusername", {UserPermission.ADMINISTRATOR}, "testuser", "about me", None))

        send_profile_deltas(config, data, socketio, info)

        assert socketio.sent == [
            Message(
                'profile',
                {
                    'id': 'u101',
                    'username': 'testusername',
                    'nickname': 'testuser',
                    'about': 'about me',
                    'icon': 'http://localhost/attachments/defavi',
                    'full_username': '@testusername@localhost',
                    'permissions': ['ADMINISTRATOR'],
                },
                'testsid',
            ),
        ]

    def test_send_profile_deltas_preferences_change(self) -> None:
        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(102))

        now = Time.now()
        info.profilets = now
        info.prefsts = now

        attachments = {a.id: a for a in [
            Attachment(AttachmentID(301), "local", "audio/mpeg", None, {}),
            Attachment(AttachmentID(302), "local", "audio/mpeg", None, {}),
        ]}

        set_return(data.user.has_updated_user, False)
        set_return(data.user.has_updated_preferences, True)
        set_return(data.user.get_preferences, UserPreferences.default(UserID(102)))
        set_return(data.attachment.get_notifications, {
            "notif1": attachments[AttachmentID(301)],
            "notif2": attachments[AttachmentID(302)],
        })
        set_lambda(data.attachment.lookup_attachment, lambda aid: attachments.get(aid))

        send_profile_deltas(config, data, socketio, info)

        assert socketio.sent == [
            Message(
                'preferences',
                {
                    'rooms_on_top': False,
                    'combined_messages': False,
                    'color_scheme': 'system',
                    'desktop_size': 'normal',
                    'mobile_size': 'normal',
                    'admin_controls': 'visible',
                    'title_notifs': True,
                    'mobile_audio_notifs': False,
                    'audio_notifs': [],
                    'notif_sounds': {
                        'notif1': 'http://localhost/attachments/5413df7c56aae113d75f9ba586367f5936c5a8fb.mp3',
                        'notif2': 'http://localhost/attachments/14738bc3beae961bb1bd566bcdec0611765cfa0d.mp3',
                    },
                },
                'testsid',
            ),
        ]
