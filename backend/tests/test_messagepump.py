from critterchat.common import Time
from critterchat.data.types import (
    ActionID,
    AttachmentID,
    OccupantID,
    RoomID,
    UserID,
    Action,
    ActionType,
    MetadataType,
    Occupant,
    Room,
    RoomPurpose,
    UserPermission,
    UserPreferences,
    User,
)
from critterchat.data.attachment import Attachment, Emote
from critterchat.http.messagepump import SocketInfo, send_emote_deltas, send_profile_deltas, send_chat_deltas

from .mocks import MockConfig, MockData, MockSocketIO, Message, set_return, set_lambda


class TestMessagePumpEmotes:
    def test_send_emote_deltas_empty(self) -> None:
        """
        Ensure that we don't send anything to the client and don't crash if there's absolutely no emotes.
        """

        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()

        emotes: set[str] = set()
        set_return(data.attachment.get_emotes, [])

        emotes = send_emote_deltas(config, data, socketio, emotes)

        assert emotes == set()
        assert socketio.sent == []

    def test_send_emote_deltas_no_change(self) -> None:
        """
        Ensure that nothing gets sent to the client when there are no changes to emotes.
        """

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
        """
        Ensure that when an emote is added to the DB it gets sent to clients.
        """

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
        """
        Ensure that when an emote is removed from the DB it gets sent to clients.
        """

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
        """
        Ensure that we can correctly handle both additions and removals at the same time. This should
        be pretty rare, but we should handle it correctly.
        """

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
        """
        Ensure that if neither the profile nor preferences have updates, nothing gets sent to the
        client.
        """

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
        """
        Ensure that if the user profile for a user has changed, it gets sent to the client of the user
        in question.
        """

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
        """
        Ensure that when the profile is emitted to the client, if the user is an admin they get the extra
        fields that they should be able to see on the profile.
        """

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
        """
        Ensure that if a user's preferences has been updated that it gets sent out to connected clients
        for that user.
        """

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


class TestMessagePumpActions:
    def test_send_chat_deltas_no_monitoring(self) -> None:
        """
        Ensure that in the unlikely care where a user is in no chats, the message pump loop for sending
        updated chat actions continues to work.
        """

        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        # We know about nothing because we're in no rooms.
        info.fetchlimit = {}
        info.lastseen = {}

        set_return(data.room.get_joined_rooms, [])
        set_return(data.user.get_last_seen_counts, {})

        send_chat_deltas(config, data, socketio, info)

        assert socketio.sent == []

    def test_send_chat_deltas_join_room_empty(self) -> None:
        """
        Verifies that if the user is joined to a room that they didn't join themselves, we notify them of
        this using the correct packets.
        """

        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        # Start with the understanding that we're in no rooms.
        info.fetchlimit = {}
        info.lastseen = {}

        set_return(data.room.get_joined_rooms, [
            Room(RoomID(401), "test room", "test topic", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100000), newest_action=ActionID(100001)),
        ])
        set_return(data.user.get_last_seen_counts, [
            (RoomID(401), 2),
        ])

        send_chat_deltas(config, data, socketio, info)

        # Ensure that we're now tracking this new room.
        assert info.fetchlimit == {RoomID(401): ActionID(100001)}
        assert info.lastseen == {RoomID(401): 2}

        # Chat actions are not included here because the client will pull the last 100 when it is told
        # about the new room and the user clicks on it. If not, then there's no need to send actions that
        # happened before the join occurred.
        assert socketio.sent == [
            Message(
                'roomlist',
                {
                    'rooms': [
                        {
                            'id': 'r401',
                            'type': RoomPurpose.ROOM,
                            'name': 'test room',
                            'customname': 'test room',
                            'topic': 'test topic',
                            'public': True,
                            'moderated': False,
                            'oldest_action': 'a100000',
                            'newest_action': 'a100001',
                            'last_action_timestamp': 0,
                            'icon': 'http://localhost/attachments/defroom',
                            'deficon': 'http://localhost/attachments/defroom',
                        },
                    ],
                    'counts': [
                        {'roomid': 'r401', 'count': 2},
                    ],
                },
                'testsid',
            ),
        ]

    def test_send_chat_deltas_join_room_monitoring(self) -> None:
        """
        Same as the above test, but verifies that things work even when the user is already watching some rooms.
        """

        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        # Start with the understanding that we're in one room but not the other.
        info.fetchlimit = {RoomID(501): ActionID(100101)}
        info.lastseen = {RoomID(501): 2}

        set_return(data.room.get_room_history, [])
        set_return(data.room.get_joined_rooms, [
            Room(RoomID(501), "test room 1", "test topic 1", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100100), newest_action=ActionID(100101)),
            Room(RoomID(502), "test room 2", "test topic 2", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100102), newest_action=ActionID(100104)),
        ])
        set_return(data.user.get_last_seen_counts, [
            (RoomID(501), 2),
            (RoomID(502), 3),
        ])

        send_chat_deltas(config, data, socketio, info)

        # Ensure that we're now tracking this new room.
        assert info.fetchlimit == {RoomID(501): ActionID(100101), RoomID(502): ActionID(100104)}
        assert info.lastseen == {RoomID(501): 2, RoomID(502): 3}

        # Chat actions are not included here because the client will pull the last 100 when it is told
        # about the new room and the user clicks on it. If not, then there's no need to send actions that
        # happened before the join occurred.
        assert socketio.sent == [
            Message(
                'roomlist',
                {
                    'rooms': [
                        {
                            'id': 'r501',
                            'type': RoomPurpose.ROOM,
                            'name': 'test room 1',
                            'customname': 'test room 1',
                            'topic': 'test topic 1',
                            'public': True,
                            'moderated': False,
                            'oldest_action': 'a100100',
                            'newest_action': 'a100101',
                            'last_action_timestamp': 0,
                            'icon': 'http://localhost/attachments/defroom',
                            'deficon': 'http://localhost/attachments/defroom',
                        },
                        {
                            'id': 'r502',
                            'type': RoomPurpose.ROOM,
                            'name': 'test room 2',
                            'customname': 'test room 2',
                            'topic': 'test topic 2',
                            'public': True,
                            'moderated': False,
                            'oldest_action': 'a100102',
                            'newest_action': 'a100104',
                            'last_action_timestamp': 0,
                            'icon': 'http://localhost/attachments/defroom',
                            'deficon': 'http://localhost/attachments/defroom',
                        },
                    ],
                    'counts': [
                        # The room we already knew about isn't included here since the client should have
                        # an accurate count of notifications. It doesn't for this newly joined room however.
                        {'roomid': 'r502', 'count': 3},
                    ],
                },
                'testsid',
            ),
        ]

    def test_send_chat_deltas_clear_badges(self) -> None:
        """
        Verify that when a client clears notification badges in a room that we update other clients of the same
        user with this info to clear badges on those other logged in instances. That way users don't have to click
        around between different chats to clear notifications on each client they have running.
        """

        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        info.fetchlimit = {RoomID(601): ActionID(100201), RoomID(602): ActionID(100204)}
        info.lastseen = {RoomID(601): 2, RoomID(602): 3}

        set_return(data.room.get_room_history, [])
        set_return(data.room.get_joined_rooms, [
            Room(RoomID(601), "test room 1", "test topic 1", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100200), newest_action=ActionID(100201)),
            Room(RoomID(602), "test room 2", "test topic 2", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100202), newest_action=ActionID(100204)),
        ])
        set_return(data.user.get_last_seen_counts, [
            (RoomID(601), 2),
            (RoomID(602), 0),
        ])

        send_chat_deltas(config, data, socketio, info)

        # Ensure that we're now tracking this new room.
        assert info.fetchlimit == {RoomID(601): ActionID(100201), RoomID(602): ActionID(100204)}
        assert info.lastseen == {RoomID(601): 2, RoomID(602): 0}

        # We only include counts that went down to zero here, since we're just informing the client that
        # we cleared a room's notifications.
        assert socketio.sent == [
            Message(
                'roomlist',
                {
                    'counts': [
                        {'roomid': 'r602', 'count': 0},
                    ],
                },
                'testsid',
            ),
        ]

    def test_send_chat_deltas_no_changes_for_client(self) -> None:
        """
        Verify that if this client has no changes, even though it's monitoring things, it doesn't get any messages.
        """

        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        info.fetchlimit = {RoomID(701): ActionID(100301), RoomID(702): ActionID(100304)}
        info.lastseen = {RoomID(701): 2, RoomID(702): 3}

        set_return(data.room.get_room_history, [])
        set_return(data.room.get_joined_rooms, [
            Room(RoomID(701), "test room 1", "test topic 1", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100300), newest_action=ActionID(100301)),
            Room(RoomID(702), "test room 2", "test topic 2", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100302), newest_action=ActionID(100304)),
        ])
        set_return(data.user.get_last_seen_counts, [
            (RoomID(701), 2),
            (RoomID(702), 3),
        ])

        send_chat_deltas(config, data, socketio, info)

        # Ensure that we're now tracking this new room.
        assert info.fetchlimit == {RoomID(701): ActionID(100301), RoomID(702): ActionID(100304)}
        assert info.lastseen == {RoomID(701): 2, RoomID(702): 3}

        # We only include counts that went down to zero here, since we're just informing the client that
        # we cleared a room's notifications.
        assert socketio.sent == []

    def test_send_chat_deltas_changes_for_client(self) -> None:
        """
        Verify that when actual actions are pending for a client, we send them and update our tracking accordingly.
        """

        config = MockConfig()
        data = MockData()
        socketio = MockSocketIO()
        info = SocketInfo("testsid", "testsession", UserID(100))

        info.fetchlimit = {RoomID(801): ActionID(100401), RoomID(802): ActionID(100404)}
        info.lastseen = {RoomID(801): 2, RoomID(802): 3}

        occupant = Occupant(OccupantID(200000), UserID(900), "testusername", "test nickname")
        actions = {
            RoomID(802): [
                Action(ActionID(100405), 123456, occupant, ActionType.MESSAGE, {"message": "testing 123"}),
                Action(ActionID(100406), 123456, None, ActionType.CHANGE_INFO, {"name": "test room 2!", "topic": "test topic 2!", "iconid": None, "moderated": False}),
            ],
        }

        set_lambda(data.room.get_room_history, lambda roomid, before=None, after=None, types=None: actions.get(roomid, []))
        set_return(data.room.get_joined_rooms, [
            Room(RoomID(801), "test room 1", "test topic 1", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100400), newest_action=ActionID(100401)),
            Room(RoomID(802), "test room 2!", "test topic 2!", RoomPurpose.ROOM, False, None, None, oldest_action=ActionID(100402), newest_action=ActionID(100406)),
        ])
        set_return(data.user.get_last_seen_counts, [
            (RoomID(801), 2),
            (RoomID(802), 5),
        ])

        send_chat_deltas(config, data, socketio, info)

        # Ensure that we're now tracking this new room.
        assert info.fetchlimit == {RoomID(801): ActionID(100401), RoomID(802): ActionID(100406)}
        assert info.lastseen == {RoomID(801): 2, RoomID(802): 5}

        # We include the actions themselves, as well as a room list without counts. The latter is because the client
        # needs to know about the ordering of the rooms given actions occurred. In the future we might consider sending
        # this info only when the ordering itself changes.
        assert socketio.sent == [
            Message(
                'chatactions',
                {
                    'roomid': 'r802',
                    'actions': [
                        {
                            'id': 'a100405',
                            'order': 100405,
                            'timestamp': 123456,
                            'occupant': {
                                'id': 'o200000',
                                'userid': 'u900',
                                'username': 'testusername',
                                'nickname': 'test nickname',
                                'inactive': False,
                                'moderator': False,
                                'muted': False,
                                'icon': 'http://localhost/attachments/defavi'
                            },
                            'action': ActionType.MESSAGE,
                            'details': {'message': 'testing 123', 'reactions': {}},
                            'attachments': []
                        },
                        {
                            'id': 'a100406',
                            'order': 100406,
                            'timestamp': 123456,
                            'occupant': None,
                            'action': ActionType.CHANGE_INFO,
                            'details': {'name': 'test room 2!', 'topic': 'test topic 2!', 'iconid': None, 'moderated': False, 'icon': 'http://localhost/attachments/defroom'},
                            'attachments': [],
                        },
                    ],
                },
                'testsid'
            ),
            Message(
                'roomlist',
                {
                    'rooms': [
                        {
                            'id': 'r801',
                            'type': RoomPurpose.ROOM,
                            'name': 'test room 1',
                            'customname': 'test room 1',
                            'topic': 'test topic 1',
                            'public': True,
                            'moderated': False,
                            'oldest_action': 'a100400',
                            'newest_action': 'a100401',
                            'last_action_timestamp': 0,
                            'icon': 'http://localhost/attachments/defroom',
                            'deficon': 'http://localhost/attachments/defroom',
                        },
                        {
                            'id': 'r802',
                            'type': RoomPurpose.ROOM,
                            'name': 'test room 2!',
                            'customname': 'test room 2!',
                            'topic': 'test topic 2!',
                            'public': True,
                            'moderated': False,
                            'oldest_action': 'a100402',
                            'newest_action': 'a100406',
                            'last_action_timestamp': 0,
                            'icon': 'http://localhost/attachments/defroom',
                            'deficon': 'http://localhost/attachments/defroom',
                        },
                    ],
                },
                'testsid',
            ),
        ]
