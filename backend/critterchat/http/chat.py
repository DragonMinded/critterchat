from flask import Blueprint, Response, render_template

from .app import app, static_location, templates_location, loginrequired, g
from ..common import get_emoji_unicode_dict, get_aliases_unicode_dict
from ..data import Data
from ..service import EmoteService, UserService


chat = Blueprint(
    "chat",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@chat.route("/chat")
@loginrequired
def home() -> Response:
    data = Data(g.config)
    userservice = UserService(g.config, data)
    emoteservice = EmoteService(g.config, data)

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}
    emotes = {f":{key}:": val for key, val in emoteservice.get_all_emotes().items()}

    if g.userID is not None:
        user = userservice.lookup_user(g.userID)
    else:
        user = None

    username = None if (not user) else user.username

    return Response(render_template(
        "home/chat.html",
        title=f"{g.config.name}",
        emojis=emojis,
        emotes=emotes,
        username=username,
    ))


app.register_blueprint(chat)
