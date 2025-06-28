from flask import Blueprint, Response, render_template

from .app import app, static_location, templates_location, loginrequired, g


chat = Blueprint(
    "chat",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@chat.route("/chat")
@loginrequired
def home() -> Response:
    return Response(render_template(
        "home/chat.html",
        title=f"{g.config.name}",
    ))


app.register_blueprint(chat)
