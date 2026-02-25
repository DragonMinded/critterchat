from flask import Blueprint, Response, render_template

from .app import (
    app,
    static_location,
    templates_location,
    absolute_url_for,
    loginrequired,
    jsonify,
    uncacheable,
    get_frontend_version,
    get_frontend_filename,
    get_fingerprint_hash,
    g,
)
from ..common import get_emoji_unicode_dict, get_aliases_unicode_dict, EMOJI_CATEGORIES
from ..data import DefaultAvatarID, DefaultRoomID, FaviconID, User, UserPermission
from ..service import AttachmentService, EmoteService, MessageService


chat = Blueprint(
    "chat",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@chat.route("/chat")
@loginrequired
def home() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)
    emoteservice = EmoteService(g.config, g.data)
    messageservice = MessageService(g.config, g.data)

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}
    emotes = {f":{key}:": val.to_dict() for key, val in emoteservice.get_all_emotes().items()}

    userid = None if (not g.user) else User.from_id(g.user.id)
    username = None if (not g.user) else g.user.username
    permissions = set() if (not g.user) else g.user.permissions
    jsname = get_frontend_filename()
    cachebust = get_frontend_version() + "-" + get_fingerprint_hash()
    defaultreactions = [r for r in g.config.reactions.defaults if messageservice.validate_reaction(f":{r}:")]

    return Response(render_template(
        "home/chat.html",
        title=f"{g.config.name}",
        jsname=jsname,
        version=cachebust,
        emojis=emojis,
        emotes=emotes,
        emojicategories=EMOJI_CATEGORIES,
        userid=userid,
        username=username,
        admin=UserPermission.ADMINISTRATOR in permissions,
        maxabout=g.config.limits.about_length,
        maxmessage=g.config.limits.message_length,
        maxalttext=g.config.limits.alt_text_length,
        maxiconsize=g.config.limits.icon_size,
        maxicondimensions=[attachmentservice.MAX_ICON_WIDTH, attachmentservice.MAX_ICON_HEIGHT],
        maxnotificationsize=g.config.limits.notification_size,
        maxattachments=g.config.limits.attachment_max,
        maxattachmentsize=g.config.limits.attachment_size,
        reactionsenabled=g.config.reactions.enabled,
        reactionsdefaults=defaultreactions,
        defavi=attachmentservice.get_attachment_url(DefaultAvatarID),
        defroom=attachmentservice.get_attachment_url(DefaultRoomID),
        favicon=attachmentservice.get_attachment_url(FaviconID),
    ))


@chat.route("/chat/config.json")
@loginrequired
@uncacheable
@jsonify
def config() -> dict[str, object]:
    attachmentservice = AttachmentService(g.config, g.data)
    emoteservice = EmoteService(g.config, g.data)
    messageservice = MessageService(g.config, g.data)

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}
    emotes = {f":{key}:": val.to_dict() for key, val in emoteservice.get_all_emotes().items()}

    userid = None if (not g.user) else User.from_id(g.user.id)
    username = None if (not g.user) else g.user.username
    permissions = set() if (not g.user) else g.user.permissions
    defaultreactions = [r for r in g.config.reactions.defaults if messageservice.validate_reaction(f":{r}:")]

    return {
        "title": g.config.name,
        "emojis": emojis,
        "emotes": emotes,
        "emojicategories": EMOJI_CATEGORIES,
        "userid": userid,
        "username": username,
        "admin": UserPermission.ADMINISTRATOR in permissions,
        "maxabout": g.config.limits.about_length,
        "maxmessage": g.config.limits.message_length,
        "maxalttext": g.config.limits.alt_text_length,
        "maxiconsize": g.config.limits.icon_size,
        "maxicondimensions": [attachmentservice.MAX_ICON_WIDTH, attachmentservice.MAX_ICON_HEIGHT],
        "maxnotificationsize": g.config.limits.notification_size,
        "maxattachments": g.config.limits.attachment_max,
        "maxattachmentsize": g.config.limits.attachment_size,
        "reactionsenabled": g.config.reactions.enabled,
        "reactionsdefaults": defaultreactions,
        "defavi": attachmentservice.get_attachment_url(DefaultAvatarID),
        "defroom": attachmentservice.get_attachment_url(DefaultRoomID),
        "favicon": attachmentservice.get_attachment_url(FaviconID),
        "uploadicon": absolute_url_for('upload.icon_upload', component="upload"),
        "uploadavatar": absolute_url_for('upload.avatar_upload', component="upload"),
        "uploadnotifications": absolute_url_for('upload.notifications_upload', component="upload"),
        "uploadattachments": absolute_url_for('upload.attachments_upload', component="upload"),
    }


@chat.route("/chat/version.json")
@uncacheable
@jsonify
def version() -> dict[str, object]:
    return {"js": get_frontend_version() + "-" + get_fingerprint_hash()}


app.register_blueprint(chat)
