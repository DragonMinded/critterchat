import logging
from typing import List

from .app import g
from ..service import MastodonService, MastodonInstanceDetails


logger = logging.getLogger(__name__)


def get_mastodon_providers() -> List[MastodonInstanceDetails]:
    mastodonservice = MastodonService(g.config, g.data)

    # First, grab all of the known instances that we need to pull info for.
    instances = mastodonservice.get_configured_instances()

    # Now, look up all of the info about each one so we can display thumbnails and login.
    retval: List[MastodonInstanceDetails] = []
    for instance in instances:
        details = mastodonservice.get_instance_details(instance)
        if not details.connected:
            logger.warn(f"Skipping {instance.base_url} because it is not registered!")
            continue

        if not details.domain or not details.title:
            logger.warn(f"Skipping {instance.base_url} because we could not pull the instance title!")
            continue

        # Figure out the best icon for our display.
        icon_size = 0
        icon_uri = None

        for size, uri in details.icons.items():
            if 'x' not in size:
                continue

            x, _ = size.split("x", 1)
            try:
                size_int = int(x)
            except ValueError:
                continue

            if icon_size == 0:
                icon_size = size_int
                icon_uri = uri
                continue

            if size_int < 32:
                # Don't care about super small icons.
                continue

            if size_int < icon_size:
                # Smaller than what we found.
                icon_size = size_int
                icon_uri = uri

        if icon_uri:
            details.icons = {f'{icon_size}x{icon_size}': icon_uri}
        else:
            details.icons = {}

        retval.append(details)

    return retval
