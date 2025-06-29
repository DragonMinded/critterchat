from flask import Blueprint, Response, render_template
from typing import Dict

from .app import app, static_location, templates_location, loginrequired, g
from ..common import get_emoji_unicode_dict, get_aliases_unicode_dict


chat = Blueprint(
    "chat",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@chat.route("/chat")
@loginrequired
def home() -> Response:
    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}

    # TODO: Custom emotes from pystreaming.
    emotes: Dict[str, object] = {}

    return Response(render_template(
        "home/chat.html",
        title=f"{g.config.name}",
        emojis=emojis,
        emotes=emotes,
    ))


app.register_blueprint(chat)
