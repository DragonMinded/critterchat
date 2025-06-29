import argparse
from werkzeug.middleware.proxy_fix import ProxyFix

from federateddergchat.http import app, config, socketio

from federateddergchat.config import load_config


# Since the sockets and REST files use decorators for hooking, simply importing these hooks the desired functions
import federateddergchat.http.welcome  # noqa
import federateddergchat.http.chat  # noqa
import federateddergchat.http.account  # noqa
import federateddergchat.http.socket  # noqa


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the chat application backend.")
    parser.add_argument("-p", "--port", help="Port to listen on. Defaults to 5678", type=int, default=5678)
    parser.add_argument("-d", "--debug", help="Enable debug mode. Defaults to off", action="store_true")
    parser.add_argument("-n", "--nginx-proxy", help="Number of nginx proxies in front of this server. Defaults to 0", type=int, default=0)
    parser.add_argument("-c", "--config", help="Config file to parse for instance settings. Defaults to config.yaml", type=str, default="config.yaml")
    args = parser.parse_args()

    load_config(args.config, config)
    app.secret_key = config.cookie_key

    if args.nginx_proxy > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_host=args.nginx_proxy, x_proto=args.nginx_proxy, x_for=args.nginx_proxy)  # type: ignore
    socketio.run(app, host='0.0.0.0', port=args.port, debug=args.debug)
