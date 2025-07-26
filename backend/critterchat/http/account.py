import string
from flask import Blueprint, Response, make_response, render_template, url_for, redirect

from .app import app, request, static_location, templates_location, loginprohibited, loginrequired, error, info, g
from ..common import AESCipher, Time
from ..data import Data, UserPermission
from ..service import UserService, UserServiceException


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


@account.route("/register", methods=["POST"])
@loginprohibited
def registerpost() -> Response:
    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    if not username:
        error("You need to choose a username!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
            )
        )

    valid_names = string.ascii_letters + string.digits + "_."
    for ch in username:
        if ch not in valid_names:
            error("You cannot use non-alphanumeric characters in your username!")
            return Response(
                render_template(
                    "account/register.html",
                    title="Register Account",
                )
            )

    if password1 != password2:
        error("Your passwords do not match each other!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                username=username,
            )
        )

    if len(password1) < 6:
        error("Your password is not long enough (six characters)!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                username=username,
            )
        )

    try:
        data = Data(g.config)
        userservice = UserService(g.config, data)
        user = userservice.create_user(username, password1)
        if UserPermission.ACTIVATED not in user.permissions:
            info("Your account has been created but has not been activated yet!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=username,
                )
            )
        else:
            info("Your account was created successfully, feel free to log in!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=username,
                )
            )

    except UserServiceException as e:
        error(str(e))
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                username=username,
            )
        )


@account.route("/register")
@loginprohibited
def register() -> Response:
    return Response(render_template(
        "account/register.html",
        title="Register Account",
    ))


app.register_blueprint(account)
