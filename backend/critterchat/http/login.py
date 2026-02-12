import logging
import requests
from flask import Response, make_response, redirect
from typing import List, Optional

from .app import g, absolute_url_for
from ..common import AESCipher, Time
from ..data import AttachmentID, MetadataType, UserID
from ..service import AttachmentService, AttachmentServiceException, MastodonService, MastodonInstanceDetails


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


def avatar_to_attachment(avatar: str) -> Optional[AttachmentID]:
    # First, attempt to download the avatar itself.
    try:
        resp = requests.get(avatar)
    except Exception as e:
        logger.error(f"Failed to fetch user's avatar from {avatar}: {e}")
        resp = None

    if not resp or resp.status_code != 200:
        return None

    # Now, try to make sure this is a valid image.
    attachmentservice = AttachmentService(g.config, g.data)
    try:
        icon, width, height, content_type = attachmentservice.prepare_attachment_image(
            resp.content,
            AttachmentService.MAX_ICON_WIDTH,
            AttachmentService.MAX_ICON_HEIGHT,
        )
    except AttachmentServiceException:
        # Unrecognized format, invalid size, etc.
        return None

    if width != height:
        # Not square, ignore it.
        return None

    attachmentid = attachmentservice.create_attachment(content_type, None, {MetadataType.WIDTH: width, MetadataType.HEIGHT: height})
    if attachmentid is None:
        logger.error(f"Could not insert new attachment for {avatar}!")
        return None

    attachmentservice.put_attachment_data(attachmentid, icon)
    return attachmentid


def login_user_id(userid: UserID) -> Response:
    aes = AESCipher(g.config.cookie_key)
    sessionID = g.data.user.create_session(userid, expiration=90 * 86400)
    response = make_response(redirect(absolute_url_for("chat.home", component="base")))
    response.set_cookie(
        "SessionID",
        aes.encrypt(sessionID),
        expires=Time.now() + (90 * Time.SECONDS_IN_DAY),
        samesite="lax",
        httponly=True,
    )
    return response
