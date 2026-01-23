import traceback
from functools import wraps
from typing import Any, Callable, Dict, Optional, cast

from flask import (
    Flask,
    Request,
    Response,
    jsonify as flask_jsonify,
    redirect,
    request as base_request,
    make_response,
    url_for,
    flash,
    g,
)
from flask_socketio import SocketIO  # type: ignore
from flask_cors import CORS  # type: ignore

from ..common import AESCipher
from ..config import Config
from ..data import Data, UserPermission
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
    def get_send_file_max_age(self, name: Optional[str]) -> Optional[int]:
        if name and name.startswith("twemoji/"):
            return 86400
        return Flask.get_send_file_max_age(self, name)


app = CritterChatFlask(__name__)
CORS(app)
socketio = SocketIO(app, logger=True, async_mode='gevent', cors_allowed_origins='*')
config: Config = Config()


# A quick hack to teach mypy about the valid SID parameter.
class StreamingRequest(Request):
    sid: Any


request: StreamingRequest = cast(StreamingRequest, base_request)


@app.before_request
def before_request() -> None:
    g.config = config

    if request.endpoint in {"static"}:
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
    return response


@app.teardown_request
def teardown_request(exception: Any) -> None:
    data = getattr(g, "data", None)
    if data is not None:
        data.close()


def loginrequired(func: Callable[..., Response]) -> Callable[..., Response]:
    @wraps(func)
    def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
        if g.user is None or UserPermission.ACTIVATED not in g.user.permissions:
            return redirect(url_for("account.login"))  # type: ignore
        else:
            return func(*args, **kwargs)

    return decoratedfunction


def loginprohibited(func: Callable[..., Response]) -> Callable[..., Response]:
    @wraps(func)
    def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
        if not (g.user is None or UserPermission.ACTIVATED not in g.user.permissions):
            return redirect(url_for("chat.home"))  # type: ignore
        else:
            return func(*args, **kwargs)

    return decoratedfunction


def jsonify(func: Callable[..., Dict[str, Any]]) -> Callable[..., Response]:
    @wraps(func)
    def decoratedfunction(*args: Any, **kwargs: Any) -> Response:
        try:
            return flask_jsonify(func(*args, **kwargs))
        except Exception as e:
            if isinstance(e, UserException):
                code = e.code
            else:
                code = 500
                print(traceback.format_exc())

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
