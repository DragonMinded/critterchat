import requests
from typing import Dict, List, Optional

from ..config import Config
from ..data import Data, MastodonInstance


class MastodonServiceException(Exception):
    pass


class MastodonInstanceDetails:
    def __init__(
        self,
        base_url: str,
        connected: bool,
        domain: Optional[str],
        title: Optional[str],
        icons: Dict[str, str],
    ) -> None:
        self.base_url = base_url
        self.connected = connected
        self.domain = domain
        self.title = title
        self.icons = icons


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

    def lookup_instance(self, base_url: str) -> Optional[MastodonInstance]:
        # Attempt to grab existing instance from the DB.
        return self.__data.mastodon.lookup_instance(base_url)

    def get_instance_details(self, instance: MastodonInstance) -> MastodonInstanceDetails:
        # First, validate the instance.
        if not self._validate_instance(instance):
            return MastodonInstanceDetails(
                base_url=instance.base_url,
                connected=False,
                domain=None,
                title=None,
                icons={},
            )

        # Now, hit the public instance information page and grab details.
        resp = requests.get(
            self._meth(instance.base_url, "/api/v2/instance"),
            json={
                "client_name": self.__config.name,
                "redirect_uris": self._meth(self.__config.base_url, "/auth/mastodon"),
                "scopes": "profile",
                "website": self.__config.base_url,
            },
        )
        if resp.status_code != 200:
            # Couldn't pull info, return dummy data.
            return MastodonInstanceDetails(
                base_url=instance.base_url,
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
            connected=True,
            domain=domain,
            title=title,
            icons=actual_icons,
        )

    def _validate_instance(self, instance: MastodonInstance) -> bool:
        # Verifies that our credentials are correct for this instance.
        if not instance.client_token:
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
            if resp.status_code != 200:
                return False

            body = resp.json()
            if str(body.get("token_type")) != "Bearer":
                return False

            # Save the validated instance.
            instance.client_token = str(body.get("access_token"))

        # Now, verify that the token is still valid.
        resp = requests.get(
            self._meth(instance.base_url, "/api/v1/apps/verify_credentials"),
            headers={
                "Authorization": f"Bearer {instance.client_token}",
            },
        )
        if resp.status_code != 200:
            return False

        # Yes, we're connected!
        return True

    def register_instance(self, base_url: str) -> MastodonInstance:
        # First, if we're already registered, verify that our credentials already work.
        existing = self.lookup_instance(base_url)
        if existing and self._validate_instance(existing):
            return existing

        # Now, register this app against this instance.
        resp = requests.post(
            self._meth(base_url, "/api/v1/apps"),
            json={
                "client_name": self.__config.name,
                "redirect_uris": self._meth(self.__config.base_url, "/auth/mastodon"),
                "scopes": "profile",
                "website": self.__config.base_url,
            },
        )
        if resp.status_code != 200:
            raise MastodonServiceException(f"Got {resp.status_code} from {base_url} when registering application!")

        body = resp.json()
        client_id = str(body["client_id"])
        client_secret = str(body["client_secret"])
        instance = MastodonInstance(
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
