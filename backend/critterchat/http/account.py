import string
from flask import Blueprint, Response, make_response, render_template, redirect

from .app import (
    app,
    absolute_url_for,
    request,
    static_location,
    templates_location,
    loginprohibited,
    loginrequired,
    get_frontend_filename,
    error,
    info,
    g,
)
from ..common import AESCipher, Time, get_emoji_unicode_dict, get_aliases_unicode_dict
from ..data import UserPermission, FaviconID
from ..service import AttachmentService, EmoteService, UserService, UserServiceException


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
    return __login(username, password)


def __login(username: str, password: str) -> Response:
    attachmentservice = AttachmentService(g.config, g.data)

    if not g.config.authentication.local:
        error("Account login is disabled.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    original_username = username
    if username and username[0] == "@":
        # The user logged in with their handle, including the @.
        username = username[1:]

    if "@" in username:
        # The user is specifying username@server, right now we only support logging in to our
        # own instance that way, so ensure that that's what's going on.
        username, instance = username.split("@", 1)
        if instance.lower() != g.config.account_base.lower():
            error(f"Unsupported instance {instance.lower()}!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=original_username,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )

    user = g.data.user.from_username(username)
    if user is None:
        error("Unrecognized username or password!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=original_username,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if UserPermission.ACTIVATED not in user.permissions:
        error("Account is not activated!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=original_username,
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
                username=original_username,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )


@account.route("/login")
@loginprohibited
def login() -> Response:
    attachmentservice = AttachmentService(g.config, g.data)

    if not g.config.authentication.local:
        error("Account login is disabled.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

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

    original_username = username
    if username and username[0] == "@":
        # The user logged in with their handle, including the @.
        username = username[1:]

    if "@" in username:
        # The user is specifying username@server, right now we only support logging in to our
        # own instance that way, so ensure that that's what's going on.
        username, instance = username.split("@", 1)
        if instance.lower() != g.config.account_base.lower():
            error(f"Unsupported instance {instance.lower()}!")
            return Response(
                render_template(
                    "account/recover.html",
                    title="Recover Account Password",
                    username=original_username,
                    recovery=recovery,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )

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
                username=original_username,
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
                username=original_username,
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
                    username=original_username,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )
        else:
            info("Your account password was updated successfully, feel free to log in!")
            return Response(
                render_template(
                    "account/login.html",
                    title="Log In",
                    username=original_username,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )

    except UserServiceException as e:
        error(str(e))
        return Response(
            render_template(
                "account/recover.html",
                title="Recover Account Password",
                username=original_username,
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

    if not g.config.account_registration.enabled:
        error("Account registration is disabled.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

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
            # No reason to make the user type the same username and password, just
            # log them in using the credentials they just used.
            info("Your account was created successfully!")
            return __login(username, password1)

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

    if not g.config.account_registration.enabled:
        error("Account registration is disabled.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    return Response(render_template(
        "account/register.html",
        title="Register Account",
        favicon=attachmentservice.get_attachment_url(FaviconID),
    ))


@account.route("/register/<invite>", methods=["POST"])
@loginprohibited
def invitepost(invite: str) -> Response:
    # Before anything, re-validate the invite.
    if not g.data.user.validate_invite(invite):
        error("Invite is invalid or expired.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    attachmentservice = AttachmentService(g.config, g.data)
    emoteservice = EmoteService(g.config, g.data)

    user = g.data.user.from_invite(invite)
    jsname = get_frontend_filename('home')

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}
    emotes = {f":{key}:": val.to_dict() for key, val in emoteservice.get_all_emotes().items()}

    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    if not username:
        error("You need to choose a username!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                invite=invite,
                user=user,
                jsname=jsname,
                emojis=emojis,
                emotes=emotes,
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
                    invite=invite,
                    user=user,
                    jsname=jsname,
                    emojis=emojis,
                    emotes=emotes,
                    favicon=attachmentservice.get_attachment_url(FaviconID),
                )
            )

    if len(username) > 255:
        error("Your username is too long!")
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                invite=invite,
                user=user,
                jsname=jsname,
                emojis=emojis,
                emotes=emotes,
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
                invite=invite,
                user=user,
                jsname=jsname,
                emojis=emojis,
                emotes=emotes,
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
                invite=invite,
                user=user,
                jsname=jsname,
                emojis=emojis,
                emotes=emotes,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    try:
        # Create user, bypass activation since it is an invite, destroy invite.
        userservice = UserService(g.config, g.data)
        user = userservice.create_user(username, password1)
        userservice.add_permission(user.id, UserPermission.ACTIVATED)
        g.data.user.destroy_invite(invite)

        # No reason to make the user type the same username and password, just
        # log them in using the credentials they just used.
        info("Your account was created successfully!")
        return __login(username, password1)

    except UserServiceException as e:
        error(str(e))
        return Response(
            render_template(
                "account/register.html",
                title="Register Account",
                username=username,
                invite=invite,
                user=user,
                jsname=jsname,
                emojis=emojis,
                emotes=emotes,
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )


@account.route("/register/<invite>")
@loginprohibited
def invite(invite: str) -> Response:
    attachmentservice = AttachmentService(g.config, g.data)
    emoteservice = EmoteService(g.config, g.data)

    if not g.data.user.validate_invite(invite):
        error("Invite is invalid or expired.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    user = g.data.user.from_invite(invite)
    jsname = get_frontend_filename('home')

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}
    emotes = {f":{key}:": val.to_dict() for key, val in emoteservice.get_all_emotes().items()}

    return Response(render_template(
        "account/register.html",
        title="Register Account",
        invite=invite,
        user=user,
        jsname=jsname,
        emojis=emojis,
        emotes=emotes,
        favicon=attachmentservice.get_attachment_url(FaviconID),
    ))


app.register_blueprint(account)
