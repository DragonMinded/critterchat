import logging
import requests
import urllib
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..data import Data, MastodonProfile, MastodonInstance, NewMastodonInstanceID


logger = logging.getLogger(__name__)


class MastodonServiceException(Exception):
    pass


class MastodonInstanceDetails:
    def __init__(
        self,
        base_url: str,
        authorize_url: Optional[str],
        connected: bool,
        domain: Optional[str],
        title: Optional[str],
        icons: Dict[str, str],
    ) -> None:
        self.base_url = base_url
        self.authorize_url = authorize_url
        self.connected = connected
        self.domain = domain
        self.title = title
        self.icons = icons


class MastodonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text = ""
        self.predepth = 0
        self.liststack: List[str] = []
        self.listcount: List[int] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in {"p", "blockquote", "pre"}:
            needsNewline = bool(self.text) and self.text[-1] != "\n"
            newLine = "\n" if needsNewline else ""

            if newLine:
                self.text += newLine
            if tag == "pre":
                self.predepth += 1
        elif tag in {"span", "code"}:
            # Spans are just wrapper elements with no formatting. Code usually denotes
            # fixed width, but we don't support any formatting yet.
            pass
        elif tag == "br":
            # No support for formatting yet.
            self.text += "\n"
        elif tag == "a":
            # Right now, just underline links.
            pass
        elif tag == "b":
            # No support for formatting yet.
            pass
        elif tag in {"i", "em"}:
            # No support for formatting yet.
            pass
        elif tag == "u":
            # No support for formatting yet.
            pass
        elif tag == "ul":
            # Unordered list start.
            self.liststack.append("ul")
            self.listcount.append(0)
        elif tag == "ol":
            # Ordered list start.
            self.liststack.append("ol")
            self.listcount.append(0)
        elif tag == "li":
            # Check if we're ordered or unordered.
            needsNewline = bool(self.text) and self.text[-1] != "\n"
            newLine = "\n" if needsNewline else ""

            if self.liststack and self.listcount:
                if self.liststack[-1] == "ol":
                    # Counted list.
                    text = newLine + (" " * len(self.liststack)) + str(self.listcount[-1] + 1) + ". "
                    self.text += text
                elif self.liststack[-1] == "ul":
                    # Uncounted list. Add an indented middot.
                    text = newLine + (" " * len(self.liststack)) + "- "
                    self.text += text
                self.listcount[-1] += 1
        else:
            logger.info(f"Unsupported start tag {tag} in HTML parser")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "blockquote", "pre"}:
            # Simple, handle this by adding up to two newlines as long as it
            # doesn't already have those.
            while self.text[-2:] != "\n\n":
                self.text += "\n"

            if tag == "pre":
                self.predepth -= 1
                if self.predepth < 0:
                    self.predepth = 0
        elif tag == "a":
            # No support for formatting yet.
            pass
        elif tag == "b":
            # No support for formatting yet.
            pass
        elif tag in {"i", "em"}:
            # No support for formatting yet.
            pass
        elif tag == "u":
            # No support for formatting yet.
            pass
        elif tag in {"span", "code", "br"}:
            pass
        elif tag in {"ul", "ol"}:
            if self.liststack:
                self.liststack = self.liststack[:-1]
            if self.listcount:
                self.listcount = self.listcount[:-1]

            self.text += "\n\n"

            if len(self.liststack) != len(self.listcount):
                # Never should hit this, so except on it so I can debug.
                raise Exception("Logic error, should never get out of sync!")
        elif tag == "li":
            # Nothing to do on close.
            pass
        else:
            logger.info(f"Unsupported end tag {tag} in HTML parser")

    def handle_data(self, data: str) -> None:
        if self.predepth == 0:
            # Get rid of newlines in favor of spaces, like HTML does.
            data = data.replace("\r\n", "\n")
            data = data.replace("\r", "\n")
            while "\n\n" in data:
                data = data.replace("\n\n", "\n")
            data = data.replace("\n", " ")

        self.text += data

    def parsed(self) -> str:
        text = self.text

        while text and text[0].isspace():
            text = text[1:]
        while text and text[-1].isspace():
            text = text[:-1]

        return text


class MastodonService:
    def __init__(self, config: Config, data: Data) -> None:
        self.__config = config
        self.__data = data

    def _meth(self, base_url: str, path: str) -> str:
        while base_url[-1] == "/":
            base_url = base_url[:-1]
        while path and path[0] == "/":
            path = path[1:]

        return f"{base_url}/{path}"

    def get_all_instances(self) -> List[MastodonInstance]:
        # Just grab all known instances.
        return self.__data.mastodon.get_instances()

    def get_configured_instances(self) -> List[MastodonInstance]:
        # Grab all known instances that are also in our configuration. Note that if you do not
        # register an instance but put it in your config, it won't show up here. Note also that
        # if you register an instance but later remove it from your config, it will also not
        # show up here. Note that this does not get the instance details itself either.
        retval: List[MastodonInstance] = []
        for instance in self.__config.authentication.mastodon:
            obj = self.__data.mastodon.lookup_instance(instance.base_url)
            if obj:
                retval.append(obj)
        return retval

    def lookup_instance(self, base_url: str) -> Optional[MastodonInstance]:
        # Attempt to grab existing instance from the DB.
        return self.__data.mastodon.lookup_instance(base_url)

    def get_instance_details(self, instance: MastodonInstance) -> MastodonInstanceDetails:
        # First, validate the instance.
        if not self._validate_instance(instance):
            return MastodonInstanceDetails(
                base_url=instance.base_url,
                authorize_url=None,
                connected=False,
                domain=None,
                title=None,
                icons={},
            )

        # Look up authorization endpoints from the well-known endpoint.
        try:
            resp = requests.get(self._meth(instance.base_url, "/.well-known/oauth-authorization-server"))
        except Exception as e:
            logger.error(f"Failed to probe {instance.base_url}: {e}")
            resp = None

        if not resp or resp.status_code != 200:
            # Couldn't pull info, return dummy data.
            return MastodonInstanceDetails(
                base_url=instance.base_url,
                authorize_url=None,
                connected=False,
                domain=None,
                title=None,
                icons={},
            )

        body = resp.json()
        auth_endpoint = str(body["authorization_endpoint"])

        # Add on our params so that we can provide a successful auth.
        auth_endpoint += "?" + urllib.parse.urlencode({
            'response_type': 'code',
            'client_id': instance.client_id,
            'redirect_uri': self._meth(self.__config.base_url, "/auth/mastodon"),
            'scope': 'profile',
            'state': instance.base_url,
        })

        # Now, hit the public instance information page and grab details.
        try:
            resp = requests.get(self._meth(instance.base_url, "/api/v2/instance"))
        except Exception as e:
            logger.error(f"Failed to probe {instance.base_url}: {e}")
            resp = None

        if not resp or resp.status_code != 200:
            # Couldn't pull info, return dummy data.
            return MastodonInstanceDetails(
                base_url=instance.base_url,
                authorize_url=auth_endpoint,
                connected=True,
                domain=None,
                title=None,
                icons={},
            )

        body = resp.json()
        domain = str(body["domain"])
        title = str(body["title"])
        icons = body.get("icon", [])

        actual_icons: Dict[str, str] = {}
        if isinstance(icons, list):
            for icon in icons:
                if isinstance(icon, dict):
                    src = str(icon.get("src"))
                    size = str(icon.get("size"))

                    if src and size:
                        actual_icons[size] = src

        return MastodonInstanceDetails(
            base_url=instance.base_url,
            authorize_url=auth_endpoint,
            connected=True,
            domain=domain,
            title=title,
            icons=actual_icons,
        )

    def _validate_instance(self, instance: MastodonInstance) -> bool:
        # Verifies that our credentials are correct for this instance.
        if not instance.client_token:
            try:
                resp = requests.post(
                    self._meth(instance.base_url, "/oauth/token"),
                    json={
                        "client_id": instance.client_id,
                        "client_secret": instance.client_secret,
                        "redirect_uri": self._meth(self.__config.base_url, "/auth/mastodon"),
                        "grant_type": "client_credentials",
                        "scope": "profile",
                    },
                )
            except Exception as e:
                logger.error(f"Failed to probe {instance.base_url}: {e}")
                resp = None

            if not resp or resp.status_code != 200:
                return False

            body = resp.json()
            if str(body.get("token_type")) != "Bearer":
                return False

            # Save the validated instance.
            instance.client_token = str(body.get("access_token"))

        # Now, verify that the token is still valid.
        try:
            resp = requests.get(
                self._meth(instance.base_url, "/api/v1/apps/verify_credentials"),
                headers={
                    "Authorization": f"Bearer {instance.client_token}",
                },
            )
        except Exception as e:
            logger.error(f"Failed to probe {instance.base_url}: {e}")
            resp = None

        if not resp or resp.status_code != 200:
            return False

        # Yes, we're connected!
        return True

    def register_instance(self, base_url: str) -> MastodonInstance:
        # First, if we're already registered, verify that our credentials already work.
        existing = self.lookup_instance(base_url)
        if existing and self._validate_instance(existing):
            return existing

        # Now, register this app against this instance.
        try:
            resp = requests.post(
                self._meth(base_url, "/api/v1/apps"),
                json={
                    "client_name": self.__config.name,
                    "redirect_uris": self._meth(self.__config.base_url, "/auth/mastodon"),
                    "scopes": "profile",
                    "website": self.__config.base_url,
                },
            )
        except Exception as e:
            logger.error(f"Failed to probe {base_url}: {e}")
            resp = None

        if not resp or resp.status_code != 200:
            if resp:
                raise MastodonServiceException(f"Got {resp.status_code} from {base_url} when registering application!")
            else:
                raise MastodonServiceException(f"Failed to get response from {base_url} when registering application!")

        body = resp.json()
        client_id = str(body["client_id"])
        client_secret = str(body["client_secret"])
        instance = MastodonInstance(
            instanceid=NewMastodonInstanceID,
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Verify credentials work.
        if not self._validate_instance(instance):
            raise MastodonServiceException(f"Could not validate freshly-obtained credentials from {base_url}!")

        # Save this in the DB.
        self.__data.mastodon.store_instance(instance)
        return instance

    def get_user_token(self, instance: MastodonInstance, code: str) -> Optional[str]:
        # First, attempt to look up and validate the instance itself.
        if not self._validate_instance(instance):
            logger.error(f"Instance {instance.base_url} is not registered or is disconnected!")
            return None

        try:
            resp = requests.post(
                self._meth(instance.base_url, "/oauth/token"),
                json={
                    "client_id": instance.client_id,
                    "client_secret": instance.client_secret,
                    "redirect_uri": self._meth(self.__config.base_url, "/auth/mastodon"),
                    "grant_type": "authorization_code",
                    "code": code,
                    "scope": "profile",
                },
            )
        except Exception as e:
            logger.error(f"Failed to fetch user token for {instance.base_url}: {e}")
            resp = None

        if not resp or resp.status_code != 200:
            return None

        body = resp.json()
        if str(body.get("token_type")) != "Bearer":
            return None

        return str(body.get("access_token"))

    def get_user_profile(self, instance: MastodonInstance, token: str) -> Optional[MastodonProfile]:
        # First, ensure our client connection to the instance is good.
        if not self._validate_instance(instance):
            logger.error(f"Instance {instance.base_url} is not registered or is disconnected!")
            return None

        # Now, fetch the profile.
        try:
            resp = requests.get(
                self._meth(instance.base_url, "/api/v1/accounts/verify_credentials"),
                headers={
                    "Authorization": f"Bearer {token}",
                },
            )
        except Exception as e:
            logger.error(f"Failed to fetch user profile for {instance.base_url}: {e}")
            resp = None

        if not resp or resp.status_code != 200:
            if resp:
                raise MastodonServiceException(f"Got {resp.status_code} from {instance.base_url} when fetching user profile!")
            else:
                return None

        body = resp.json()
        username = str(body["username"])
        displayname = str(body["display_name"])
        avatar = str(body["avatar"])
        note = str(body["note"])

        parser = MastodonParser()
        parser.feed(note)
        parser.close()
        note = parser.parsed()

        return MastodonProfile(
            instance_url=instance.base_url,
            username=username,
            nickname=displayname,
            avatar=avatar,
            note=note,
        )
