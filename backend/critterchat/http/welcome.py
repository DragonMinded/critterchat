from flask import Blueprint, Response, render_template

from .app import app, static_location, templates_location, loginprohibited, g


welcome = Blueprint(
    "welcome",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@welcome.route("/")
@loginprohibited
def home() -> Response:
    return Response(render_template(
        "home/welcome.html",
        title=f"Welcome to {g.config.name}",
        name=g.config.name,
    ))


app.register_blueprint(welcome)
