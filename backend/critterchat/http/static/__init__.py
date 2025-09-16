import os

static_location = os.path.abspath(os.path.dirname(__file__))
default_avatar = os.path.join(os.path.abspath(os.path.dirname(__file__)), "avi.png")
default_room = os.path.join(os.path.abspath(os.path.dirname(__file__)), "room.png")
default_icon = os.path.join(os.path.abspath(os.path.dirname(__file__)), "icon.png")


__all__ = [
    "static_location",
    "default_avatar",
    "default_room",
    "default_icon",
]
