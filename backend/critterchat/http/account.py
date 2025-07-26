from flask import Blueprint, Response, make_response, render_template, url_for, redirect

from .app import app, request, static_location, templates_location, loginprohibited, loginrequired, error, g
from ..common import AESCipher, Time
from ..data import UserPermission


account = Blueprint(
    "account",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@account.route("/login", methods=["POST"])
@loginprohibited
def loginpost() -> Response:
    username = request.form["username"]
    password = request.form["password"]

    user = g.data.user.from_username(username)
    if user is None:
        error("Unrecognized username or password!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=username,
            )
        )

    if UserPermission.ACTIVATED not in user.permissions:
        error("Account is not activated!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=username,
            )
        )

    if g.data.user.validate_password(user.id, password):
        aes = AESCipher(g.config.cookie_key)
        sessionID = g.data.user.create_session(user.id, expiration=90 * 86400)
        response = make_response(redirect(url_for("chat.home")))
        response.set_cookie(
            "SessionID",
            aes.encrypt(sessionID),
            expires=Time.now() + (90 * Time.SECONDS_IN_DAY),
        )
        return response
    else:
        error("Unrecognized username or password!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=username,
            )
        )


@account.route("/login")
@loginprohibited
def login() -> Response:
    return Response(render_template(
        "account/login.html",
        title="Log In",
    ))


@account.route("/logout")
@loginrequired
def logout() -> Response:
    g.data.user.destroy_session(g.sessionID)
    return redirect(url_for("welcome.home"))  # type: ignore


@account.route("/register")
@loginprohibited
def register() -> Response:
    return Response(render_template(
        "account/register.html",
        title="Register Account",
    ))


app.register_blueprint(account)
