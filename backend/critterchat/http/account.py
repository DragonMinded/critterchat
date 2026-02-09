import string
from flask import Blueprint, Response, make_response, render_template, redirect

from .app import app, absolute_url_for, request, static_location, templates_location, loginprohibited, loginrequired, error, info, g
from ..common import AESCipher, Time
from ..data import UserPermission, FaviconID
from ..service import AttachmentService, UserService, UserServiceException


account = Blueprint(
    "account",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


@account.route("/login", methods=["POST"])
@loginprohibited
def loginpost() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)
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
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if UserPermission.ACTIVATED not in user.permissions:
        error("Account is not activated!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=username,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if g.data.user.validate_password(user.id, password):
        aes = AESCipher(g.config.cookie_key)
        sessionID = g.data.user.create_session(user.id, expiration=90 * 86400)
        response = make_response(redirect(absolute_url_for("chat.home", component="base")))
        response.set_cookie(
            "SessionID",
            aes.encrypt(sessionID),
            expires=Time.now() + (90 * Time.SECONDS_IN_DAY),
            samesite="strict",
            httponly=True,
        )
        return response
    else:
        error("Unrecognized username or password!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=username,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )


@account.route("/login")
@loginprohibited
def login() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)

    return Response(render_template(
        "account/login.html",
        title="Log In",
        favicon=attachmentservice.get_attachment_url(FaviconID),
    ))


@account.route("/recover/<recovery>", methods=["POST"])
def recoverpost(recovery: str) -> Response:
    attachmentservice = AttachmentService(g.config, g.data)
    userservice = UserService(g.config, g.data)
    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    if not username:
        error("You need to specify your username!")
        return Response(
            render_template(
                "account/recover.html",
                title="Recover Account Password",
                recovery=recovery,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if password1 != password2:
        error("Your passwords do not match each other!")
        return Response(
            render_template(
                "account/recover.html",
                title="Recover Account Password",
                username=username,
                recovery=recovery,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if len(password1) < 6:
        error("Your password is not long enough (six characters)!")
        return Response(
            render_template(
                "account/recover.html",
                title="Recover Account Password",
                username=username,
                recovery=recovery,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    try:
        user = userservice.recover_user_password(username, recovery, password1)
        if UserPermission.ACTIVATED not in user.permissions:
            info("Your account password has been updated but your account has not been activated yet!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=user.username,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )
        else:
            info("Your account password was updated successfully, feel free to log in!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=user.username,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )

    except UserServiceException as e:
        error(str(e))
        return Response(
            render_template(
                "account/recover.html",
                title="Recover Account Password",
                username=username,
                recovery=recovery,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )
    return ""


@account.route("/recover/<recovery>")
def recover(recovery: str) -> Response:
    attachmentservice = AttachmentService(g.config, g.data)

    return Response(render_template(
        "account/recover.html",
        title="Recover Account Password",
        recovery=recovery,
        favicon=attachmentservice.get_attachment_url(FaviconID),
    ))


@account.route("/logout")
@loginrequired
def logout() -> Response:
    # Should always be true on loginrequired endpoints, but let's be safe.
    if g.sessionID:
        g.data.user.destroy_session(g.sessionID)
    return redirect(absolute_url_for("welcome.home", component="base"))  # type: ignore


@account.route("/register", methods=["POST"])
@loginprohibited
def registerpost() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)
    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    if not username:
        error("You need to choose a username!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                favicon=attachmentservice.get_attachment_url(FaviconID),
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
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )

    if len(username) > 255:
        error("Your username is too long!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if password1 != password2:
        error("Your passwords do not match each other!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                username=username,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if len(password1) < 6:
        error("Your password is not long enough (six characters)!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                username=username,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    try:
        userservice = UserService(g.config, g.data)
        user = userservice.create_user(username, password1)
        if UserPermission.ACTIVATED not in user.permissions:
            info("Your account has been created but has not been activated yet!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=username,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )
        else:
            info("Your account was created successfully, feel free to log in!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=username,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )

    except UserServiceException as e:
        error(str(e))
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                username=username,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )


@account.route("/register")
@loginprohibited
def register() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)

    return Response(render_template(
        "account/register.html",
        title="Register Account",
        favicon=attachmentservice.get_attachment_url(FaviconID),
    ))


app.register_blueprint(account)
