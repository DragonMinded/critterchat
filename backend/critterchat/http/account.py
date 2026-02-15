import logging
import secrets
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
from .login import (
    get_mastodon_providers,
    avatar_to_attachment,
    copy_profile_enabled,
    login_user_id,
    logout_all,
    ensure_logged_out_all,
)
from ..common import get_emoji_unicode_dict, get_aliases_unicode_dict
from ..data import UserPermission, FaviconID
from ..service import (
    AttachmentService,
    EmoteService,
    MastodonService,
    MastodonServiceException,
    UserService,
    UserServiceException,
)


account = Blueprint(
    "account",
    __name__,
    template_folder=templates_location,
    static_folder=static_location,
)


logger = logging.getLogger(__name__)


VALID_USERNAME_CHARACTERS = string.ascii_letters + string.digits + "_."
VALID_RANDOM_PASWORD_CHARACTERS = string.ascii_letters + string.digits


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
                    mastodon_providers=get_mastodon_providers(),
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
                mastodon_providers=get_mastodon_providers(),
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
                mastodon_providers=get_mastodon_providers(),
                favicon=attachmentservice.get_attachment_url(FaviconID),
            )
        )

    if g.data.user.validate_password(user.id, password):
        return login_user_id(user.id)
    else:
        error("Unrecognized username or password!")
        return Response(
            render_template(
                "account/login.html",
                title="Log In",
                username=original_username,
                mastodon_providers=get_mastodon_providers(),
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

    return ensure_logged_out_all(Response(render_template(
        "account/login.html",
        title="Log In",
        mastodon_providers=get_mastodon_providers(),
        favicon=attachmentservice.get_attachment_url(FaviconID),
    )))


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
                    mastodon_providers=get_mastodon_providers(),
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
                    mastodon_providers=get_mastodon_providers(),
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
    return logout_all()


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

    for ch in username:
        if ch not in VALID_USERNAME_CHARACTERS:
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
                    mastodon_providers=get_mastodon_providers(),
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

    for ch in username:
        if ch not in VALID_USERNAME_CHARACTERS:
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


@account.route("/auth/mastodon")
@loginprohibited
def mastodonauth() -> Response:
    mastodonservice = MastodonService(g.config, g.data)
    userservice = UserService(g.config, g.data)

    # First, grab the code, and use that to get a user token.
    code = request.args.get('code')
    base_url = request.args.get('state')

    if not code or not base_url:
        error("Authorization code is missing or invalid.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    instance = mastodonservice.lookup_instance(base_url)
    if not instance:
        logger.error(f"Failed to find registered instance under {base_url}")
        error("Authorization code is missing or invalid.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    try:
        token = mastodonservice.get_user_token(instance, code)
    except MastodonServiceException as e:
        logger.error(f"Failed to validate login code: {e}")
        token = None

    if not token:
        error("Authorization code is invalid.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    # Now, grab the user's profile details so we can find the local account associated with this.
    profile = mastodonservice.get_user_profile(instance, token)
    if not profile:
        error("Authorization code is invalid.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    # Deauth this token, since we no longer need it.
    mastodonservice.return_user_token(instance, token)

    # Now, see if we can log in as this user, or must create an account.
    existing_user = mastodonservice.get_user(instance, profile.username)
    if existing_user:
        # This user already exists, simply log them in!
        logger.info(f"Logging {profile.username!r} user in after successful auth against {base_url}.")
        return login_user_id(existing_user.id)

    # User does not exist, so we must create a new user account. Arbitrarily choose the
    # mastodon username as our username, and add underscores if there are already existing
    # accounts that match what we chose.
    sanitized_username = ""
    for character in profile.username:
        if character in VALID_USERNAME_CHARACTERS:
            sanitized_username += character

    if not sanitized_username:
        error("Mastodon account does not have a valid username.")
        return make_response(redirect(absolute_url_for("welcome.home", component="base")))

    while True:
        # See if our username already exists.
        taken_user = userservice.find_user(sanitized_username)
        if not taken_user:
            break

        sanitized_username = sanitized_username + "_"

    # The sanitized username is what we'll use for our username. We will pick a completely
    # random password since it does not matter what is used here.
    logger.info(
        f"Creating new user {sanitized_username!r} based on {profile.username!r} user after successful auth against {base_url}."
    )
    password = ''.join(secrets.choice(VALID_RANDOM_PASWORD_CHARACTERS) for _ in range(32))
    user = userservice.create_user(sanitized_username, password)
    userservice.add_permission(user.id, UserPermission.ACTIVATED)

    # Then, we will create a link between this new user and the mastodon credentials we grabbed.
    mastodonservice.link_user(instance, profile.username, user.id)

    # Finally, since we crated a new account, let's set the user's profile up for them.
    if copy_profile_enabled(base_url):
        avatar_id = None
        if profile.avatar:
            avatar_id = avatar_to_attachment(profile.avatar)
        userservice.update_user(user.id, name=profile.nickname, about=profile.note, icon=avatar_id)
        logger.info(f"Copying {profile.username!r} user profile info from their {base_url} Mastodon profile.")
    else:
        logger.info(f"Skipped copying {profile.username!r} user profile info from their {base_url} Mastodon profile.")

    # And now, log them in!
    return login_user_id(user.id)


app.register_blueprint(account)
