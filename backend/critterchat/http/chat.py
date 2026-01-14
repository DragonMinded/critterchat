import hashlib
import json
import os
from flask import Blueprint, Response, render_template
from typing import Dict

from .app import app, static_location, templates_location, loginrequired, jsonify, g
from ..common import get_emoji_unicode_dict, get_aliases_unicode_dict
from ..data import DefaultAvatarID, DefaultRoomID, FaviconID, User
from ..service import AttachmentService, EmoteService


chat = Blueprint(
    "chat",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


FINGERPRINT_INCLUDE_FILES = [
    "autocomplete.css",
    "chat.css",
    "emojisearch.css",
    "jquery.modal.min.css",
]


def _get_fingerprint_hash() -> str:
    # Intentionally not caching, because if we cache this but not the below chat.js,
    # then on deploy users might get two notifications for an update instead of one
    # depending on how fast the deploy happens.

    file_hash = hashlib.md5()
    for file in FINGERPRINT_INCLUDE_FILES:
        filepath = os.path.join(static_location, file)
        with open(filepath, "rb") as bfp:
            file_hash.update(bfp.read())

    return file_hash.hexdigest()


def _get_frontend_filename() -> str:
    # Attempt to look up our frontend JS, used also for cache-busting.
    jspath = os.path.join(static_location, "webpack-assets.json")
    with open(jspath, "rb") as bfp:
        jsdata = bfp.read().decode('utf-8')
        jsblob = json.loads(jsdata)
        return str(jsblob['main']['js'])


def _get_frontend_version() -> str:
    return _get_frontend_filename().replace('.js', '').replace('chat.', '')


@chat.route("/chat")
@loginrequired
def home() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)
    emoteservice = EmoteService(g.config, g.data)

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}
    emotes = {f":{key}:": val for key, val in emoteservice.get_all_emotes().items()}

    userid = None if (not g.user) else User.from_id(g.user.id)
    username = None if (not g.user) else g.user.username
    jsname = _get_frontend_filename()
    cachebust = _get_frontend_version() + "-" + _get_fingerprint_hash()

    return Response(render_template(
        "home/chat.html",
        title=f"{g.config.name}",
        jsname=jsname,
        cachebust=f"cachebust={cachebust}",
        version=cachebust,
        emojis=emojis,
        emotes=emotes,
        userid=userid,
        username=username,
        defavi=attachmentservice.get_attachment_url(DefaultAvatarID),
        defroom=attachmentservice.get_attachment_url(DefaultRoomID),
        favicon=attachmentservice.get_attachment_url(FaviconID),
    ))


@chat.route("/chat/version.json")
@jsonify
def version() -> Dict[str, object]:
    return {"js": _get_frontend_version() + "-" + _get_fingerprint_hash()}


app.register_blueprint(chat)
