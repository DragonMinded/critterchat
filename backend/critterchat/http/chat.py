import json
import os
from flask import Blueprint, Response, render_template
from typing import Dict

from .app import app, static_location, templates_location, loginrequired, jsonify, g
from ..common import get_emoji_unicode_dict, get_aliases_unicode_dict
from ..data import Data, DefaultAvatarID, DefaultRoomID
from ..service import AttachmentService, EmoteService


chat = Blueprint(
    "chat",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


def _get_frontend_filename() -> str:
    # Attempt to look up our frontend JS.
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
    data = Data(g.config)
    attachmentservice = AttachmentService(g.config, data)
    emoteservice = EmoteService(g.config, data)

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}
    emotes = {f":{key}:": val for key, val in emoteservice.get_all_emotes().items()}

    username = None if (not g.user) else g.user.username
    jsname = _get_frontend_filename()
    cachebust = _get_frontend_version()

    return Response(render_template(
        "home/chat.html",
        title=f"{g.config.name}",
        jsname=jsname,
        cachebust=f"cachebust={cachebust}",
        version=cachebust,
        emojis=emojis,
        emotes=emotes,
        username=username,
        defavi=attachmentservice.get_attachment_url(DefaultAvatarID),
        defroom=attachmentservice.get_attachment_url(DefaultRoomID),
    ))


@chat.route("/chat/version.json")
@jsonify
def version() -> Dict[str, object]:
    return {"js": _get_frontend_version()}


app.register_blueprint(chat)
