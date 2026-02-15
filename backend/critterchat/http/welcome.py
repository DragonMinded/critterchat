from flask import Blueprint, Response, render_template

from .app import app, static_location, templates_location, loginprohibited, g
from .login import get_mastodon_providers, ensure_logged_out_all
from ..data import FaviconID
from ..service import AttachmentService


welcome = Blueprint(
    "welcome",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@welcome.route("/")
@loginprohibited
def home() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)

    return ensure_logged_out_all(Response(render_template(
        "home/welcome.html",
        title=f"Welcome to {g.config.name}",
        mastodon_providers=get_mastodon_providers(),
        favicon=attachmentservice.get_attachment_url(FaviconID),
    )))


app.register_blueprint(welcome)
