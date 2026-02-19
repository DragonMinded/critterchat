import hashlib
import json
import logging
import os
import time
import traceback
from functools import wraps
from typing import Any, Callable, cast

from flask import (
    Flask,
    Request,
    Response,
    jsonify as flask_jsonify,
    redirect,
    request as base_request,
    make_response,
    url_for as original_url_for,
    flash,
    g as base_g,
)
from flask.ctx import _AppCtxGlobals
from flask_socketio import SocketIO  # type: ignore
from flask_cors import CORS  # type: ignore

from ..common import AESCipher
from ..config import Config
from ..data import Data, User, UserPermission
from .templates import templates_location
from .static import static_location


__all__ = [
    "g",
    "app",
    "config",
    "socketio",
    "request",
    "templates_location",
    "static_location",
    "loginrequired",
    "loginprohibited",
    "error",
    "warning",
    "success",
    "info",
    "jsonify",
    "cacheable",
]


class UserException(Exception):
    code: int = 400


class CritterChatFlask(Flask):
    # Makes develpment slightly less hell, since this will cache Twemoji stuff for us.
    def get_send_file_max_age(self, name: str | None) -> int | None:
        if name and name.startswith("twemoji/"):
            return 86400
        return Flask.get_send_file_max_age(self, name)


logger = logging.getLogger(__name__)
app = CritterChatFlask(__name__)
CORS(app)
socketio = SocketIO(app, logger=logger, async_mode='gevent', cors_allowed_origins='*')
config: Config = Config()


# A quick hack to teach mypy about the valid SID parameter.
class CritterChatRequest(Request):
    sid: Any


request: CritterChatRequest = cast(CritterChatRequest, base_request)


# A quick hack to teach mypy about our request global parameters.
class CritterChatGlobal(_AppCtxGlobals):
    # What time the request arrived.
    timestamp: float

    # Our config global, always available.
    config: Config

    # Data object, we lie that it's always available because we only don't load
    # it when we're in static endpoints which never get to our code.
    data: Data

    # Optional parameters that could be set if the user is logged in.
    sessionID: str | None
    user: User | None


g: CritterChatGlobal = cast(CritterChatGlobal, base_g)


@app.before_request
def before_request() -> None:
    g.timestamp = time.time()
    g.config = config
    g.data = None  # type: ignore
    g.sessionID = None
    g.user = None

    if request.endpoint in {"static", "attachments.get_attachment"}:
        # This is just serving cached compiled frontends, skip loading from DB
        return

    g.data = Data(config)

    # Try to look up the session if there is one.
    ciphered_session = request.cookies.get("SessionID")
    if ciphered_session:
        try:
            aes = AESCipher(config.cookie_key)
            sessionID = aes.decrypt(ciphered_session)
        except Exception:
            sessionID = None
    else:
        sessionID = None

    # Try to associate with a user if there is one.
    g.sessionID = sessionID
    if sessionID is not None:
        g.user = g.data.user.from_session(sessionID)
    else:
        g.user = None


@app.after_request
def after_request(response: Response) -> Response:
    if not response.cache_control.max_age:
        # Make sure our REST calls don't get cached, so that the
        # live pages update in real-time.
        response.cache_control.no_cache = True
        response.cache_control.must_revalidate = True
        response.cache_control.private = True

    if request.query_string:
        path = f"{request.path}?{request.query_string.decode('utf-8')}"
    else:
        path = request.path
    content_length = response.calculate_content_length() or 0
    ts = int((time.time() - g.timestamp) * 10000) / 10.0
    logger.info(f'{request.remote_addr} - {request.method} - {path} - {response.status} - {content_length} - {ts}ms')

    return response


@app.teardown_request
def teardown_request(exception: Any) -> None:
    data = getattr(g, "data", None)
    if data is not None:
        data.close()


def absolute_url_for(endpoint: str, *, component: str, filename: str | None = None, **values: Any) -> str:
    if endpoint == "static":
        if filename is None:
            raise Exception("Logic error, should always provide filename with static resource lookup!")

        uri = original_url_for(endpoint, filename=filename, **values)
    else:
        if filename is not None:
            raise Exception("Logic error, should never provide filename with non-static resource lookup!")

        uri = original_url_for(endpoint, **values)

    while uri and (uri[0] == "/"):
        uri = uri[1:]

    if component == "upload":
        base = config.upload_url
    elif component == "attachment":
        base = config.attachments.prefix
        if not (base.startswith("http://") or base.startswith("https://")):
            while base[0] == "/":
                base = base[1:]

            while base[-1] == "/":
                base = base[:-1]

            uri = f"{base}/{uri}"
            base = config.base_url
    elif component == "base":
        base = config.base_url
    else:
        raise Exception(f"Logic error, unknown component {component}!")

    while base[-1] == "/":
        base = base[:-1]

    return f"{base}/{uri}"


FINGERPRINT_INCLUDE_FILES = [
    "autocomplete.css",
    "chat.css",
    "emojisearch.css",
    "jquery.modal.css",
]


def get_fingerprint_hash() -> str:
    # Intentionally not caching, because if we cache this but not the below chat.js,
    # then on deploy users might get two notifications for an update instead of one
    # depending on how fast the deploy happens.

    file_hash = hashlib.md5()
    for file in FINGERPRINT_INCLUDE_FILES:
        filepath = os.path.join(static_location, file)
        with open(filepath, "rb") as bfp:
            file_hash.update(bfp.read())

    return file_hash.hexdigest()


def get_frontend_filename(entry: str = 'chat') -> str:
    # Attempt to look up our frontend JS, used also for cache-busting.
    jspath = os.path.join(static_location, "webpack-assets.json")
    with open(jspath, "rb") as bfp:
        jsdata = bfp.read().decode('utf-8')
        jsblob = json.loads(jsdata)
        return str(jsblob[entry]['js'])


def get_frontend_version() -> str:
    return get_frontend_filename().replace('.js', '').replace('chat.', '')


@app.context_processor
def extrafunctions() -> dict[str, Any]:
    cachebust = get_frontend_version() + "-" + get_fingerprint_hash()
    colorscheme = request.cookies.get("ColorScheme", "system")

    return {
        "absolute_url_for": absolute_url_for,
        "config": config,
        "cachebust": f"cachebust={cachebust}",
        "colorscheme": colorscheme,
    }


def loginrequired(func: Callable[..., Response]) -> Callable[..., Response]:
    @wraps(func)
    def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
        if g.user is None or UserPermission.ACTIVATED not in g.user.permissions:
            return redirect(absolute_url_for("account.login", component='base'))  # type: ignore
        else:
            return func(*args, **kwargs)

    return decoratedfunction


def loginprohibited(func: Callable[..., Response]) -> Callable[..., Response]:
    @wraps(func)
    def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
        if not (g.user is None or UserPermission.ACTIVATED not in g.user.permissions):
            return redirect(absolute_url_for("chat.home", component='base'))  # type: ignore
        else:
            return func(*args, **kwargs)

    return decoratedfunction


def jsonify(func: Callable[..., dict[str, Any]]) -> Callable[..., Response]:
    @wraps(func)
    def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
        try:
            return flask_jsonify(func(*args, **kwargs))
        except Exception as e:
            if isinstance(e, UserException):
                code = e.code
            else:
                code = 500
                logger.error(traceback.format_exc())

            return make_response(flask_jsonify(
                {
                    "error": str(e),
                }
            ), code)

    return decoratedfunction


def cacheable(max_age: int) -> Callable[[Callable[..., Response]], Callable[..., Response]]:
    def __cache(func: Callable[..., Response]) -> Callable[..., Response]:
        @wraps(func)
        def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
            response = func(*args, **kwargs)
            response.cache_control.max_age = max_age
            return response

        return decoratedfunction

    return __cache


def uncacheable(func: Callable[..., Response]) -> Callable[..., Response]:
    @wraps(func)
    def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
        response = func(*args, **kwargs)
        response.cache_control.no_cache = True
        return response

    return decoratedfunction


def error(msg: str) -> None:
    flash(msg, "error")


def warning(msg: str) -> None:
    flash(msg, "warning")


def success(msg: str) -> None:
    flash(msg, "success")


def info(msg: str) -> None:
    flash(msg, "info")
