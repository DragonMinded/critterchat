import re
from emoji import LANGUAGES, EMOJI_DATA, STATUS
from typing import Match


_EMOJI_UNICODE: dict[str, dict[str, str] | None] = {lang: None for lang in LANGUAGES}  # Cache for the language dicts
_ALIASES_UNICODE: dict[str, str] = {}  # Cache for the aliases dict
_BANNED_ALIASES: set[str] = {
    ":egg2:",
    ":cow2:",
    ":point_up_2:",
    ":cat2:",
    ":dog2:",
    ":mouse2:",
    ":pencil2:",
    ":pig2:",
    ":rabbit2:",
    ":tiger2:",
    ":train2:",
    ":whale2:",
}  # Aliases that are pure duplicates that we don't want around.
_RENAMED_ALIASES: dict[str, str] = {
    ":emoji_modifier_fitzpatrick_type_1_2:": ":emoji_modifier_1_light_skin_tone:",
    ":emoji_modifier_fitzpatrick_type_3:": ":emoji_modifier_2_medium-light_skin_tone:",
    ":emoji_modifier_fitzpatrick_type_4:": ":emoji_modifier_3_medium_skin_tone:",
    ":emoji_modifier_fitzpatrick_type_5:": ":emoji_modifier_4_medium-dark_skin_tone:",
    ":emoji_modifier_fitzpatrick_type_6:": ":emoji_modifier_5_dark_skin_tone:",
}  # Aliases that we want to rename for convenience.


# Delimeters for regex.
_DELIMITER = ':'
_EMOJI_NAME_PATTERN = '\\w\\-&.’”“()!#*+,/«»\u0300\u0301\u0302\u0303\u0306\u0308\u030a\u0327\u064b\u064e\u064f\u0650\u0653\u0654\u3099\u30fb\u309a\u0655'
_EMOJI_REGEX = re.compile(
    f'({_DELIMITER}[{_EMOJI_NAME_PATTERN}]+{_DELIMITER})'
)


def _get_emoji_unicode_dict(lang: str) -> dict[str, str]:
    """
    Generate dict containing all fully-qualified and component emoji name for a language
    The dict is only generated once per language and then cached in _EMOJI_UNICODE[lang]
    """

    if _EMOJI_UNICODE[lang] is None:
        _EMOJI_UNICODE[lang] = {
            data[lang]: emj for emj, data in EMOJI_DATA.items()
            if lang in data and data['status'] <= STATUS['fully_qualified']
        }

    return _EMOJI_UNICODE[lang]  # type: ignore


def get_aliases_unicode_dict() -> dict[str, str]:
    """
    Generate dict containing all fully-qualified and component aliases
    The dict is only generated once and then cached in _ALIASES_UNICODE
    """

    if not _ALIASES_UNICODE:
        _ALIASES_UNICODE.update(_get_emoji_unicode_dict('en'))
        for emj, data in EMOJI_DATA.items():
            if 'alias' in data and data['status'] <= STATUS['fully_qualified']:
                for alias in data['alias']:
                    if alias in _ALIASES_UNICODE:
                        continue
                    if alias in _BANNED_ALIASES:
                        continue
                    if alias in _RENAMED_ALIASES:
                        alias = _RENAMED_ALIASES[alias]
                    _ALIASES_UNICODE[alias] = emj

        for off, val in enumerate(range(0x1F1E6, 0x1F200)):
            ascval = chr(off + ord('a'))
            _ALIASES_UNICODE[f":regional_indicator_{ascval}:"] = chr(val) + chr(0x200B)

    return _ALIASES_UNICODE


def emojize(msg: str) -> str:
    """
    Performs the same thing as emoji.emojize() but does not include banned aliases since it
    instead uses the unicode dictionary from above. Allows us to sidestep the problem that
    our frontend has one set of aliases (computed in get_aliases_unicode_dict) but using
    emoji.emojize ends up using its own internal alias list.
    """

    aliases = get_aliases_unicode_dict()

    def replace(match: Match[str]) -> str:
        name_or_alias = match.group(1)
        return aliases.get(name_or_alias, match.group(1))

    return _EMOJI_REGEX.sub(replace, msg)
