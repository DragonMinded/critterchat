from gevent import monkey
monkey.patch_all()

import argparse  # noqa
import logging  # noqa
from flask.logging import default_handler  # noqa
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa

from critterchat.http import app, config, socketio  # noqa

from critterchat.config import Config, load_config  # noqa
from critterchat.data import Data  # noqa
from critterchat.service import AttachmentService, MessageService, UserService  # noqa

# Since the sockets and REST files use decorators for hooking, simply importing these hooks the desired functions
import critterchat.http.welcome  # noqa
import critterchat.http.chat  # noqa
import critterchat.http.account  # noqa
import critterchat.http.upload  # noqa
import critterchat.http.socket  # noqa

# This is only hooked when local storage is enabled.
from critterchat.http.attachments import attachments  # noqa


logger = logging.getLogger(__name__)


def perform_initialization_work(config: Config) -> None:
    data = Data(config)

    # Ensure that the default avatars are copied to the attachment storage system.
    attachmentservice = AttachmentService(config, data)
    logger.info("Creating any default attachments required.")
    attachmentservice.create_default_attachments()
    logger.info("Migrating any legacy attachments to current system.")
    attachmentservice.migrate_legacy_attachments()

    # Ensure that any nickname loopholes are fixed.
    userservice = UserService(config, data)
    logger.info("Migrating any legacy names to current rules.")
    userservice.migrate_legacy_names()

    # Ensure any per-room nicknames loopholes are fixed.
    messageservice = MessageService(config, data)
    logger.info("Migrating any per-room legacy names to current rules.")
    messageservice.migrate_legacy_names()

    logger.info("Done with initialization.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the chat application backend.")
    parser.add_argument("-p", "--port", help="Port to listen on. Defaults to 5678", type=int, default=5678)
    parser.add_argument("-d", "--debug", help="Enable debug mode. Defaults to off", action="store_true")
    parser.add_argument("-s", "--sql-query-log", help="Enable logging of SQL queries. Defaults to off", action="store_true")
    parser.add_argument("-n", "--nginx-proxy", help="Number of nginx proxies in front of this server. Defaults to 0", type=int, default=0)
    parser.add_argument("-c", "--config", help="Config file to parse for instance settings. Defaults to config.yaml", type=str, default="config.yaml")
    args = parser.parse_args()

    load_config(args.config, config)
    app.secret_key = config.cookie_key

    root_logger = logging.getLogger()
    while root_logger.hasHandlers():
        root_logger.removeHandler(logger.handlers[0])
    root_logger.addHandler(default_handler)
    root_logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    if args.sql_query_log:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    # Attach local storage handler if we're local attachment type.
    if config.attachments.system == "local":
        app.register_blueprint(attachments)

    # Perform any one-time initialization that needs to happen.
    perform_initialization_work(config)

    if args.nginx_proxy > 0:
        logger.info(f"Fixing proxy headers with a depth of {args.nginx_proxy}")
        app.wsgi_app = ProxyFix(app.wsgi_app, x_host=args.nginx_proxy, x_proto=args.nginx_proxy, x_for=args.nginx_proxy, x_prefix=args.nginx_proxy)  # type: ignore
    logger.info(f"Running server listening on port {args.port}")
    socketio.run(app, host='0.0.0.0', port=args.port, debug=args.debug)
