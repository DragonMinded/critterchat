import emoji

from typing import Any


_EMOJI_UNICODE: dict[str, Any] = {lang: None for lang in emoji.LANGUAGES}  # Cache for the language dicts
_ALIASES_UNICODE: dict[str, str] = {}  # Cache for the aliases dict


def get_emoji_unicode_dict(lang: str) -> dict[str, Any]:
    """
    Generate dict containing all fully-qualified and component emoji name for a language
    The dict is only generated once per language and then cached in _EMOJI_UNICODE[lang]
    """

    if _EMOJI_UNICODE[lang] is None:
        _EMOJI_UNICODE[lang] = {data[lang]: emj for emj, data in emoji.EMOJI_DATA.items()
                                if lang in data and data['status'] <= emoji.STATUS['fully_qualified']}

    return _EMOJI_UNICODE[lang]  # type: ignore


def get_aliases_unicode_dict() -> dict[str, str]:
    """
    Generate dict containing all fully-qualified and component aliases
    The dict is only generated once and then cached in _ALIASES_UNICODE
    """

    if not _ALIASES_UNICODE:
        _ALIASES_UNICODE.update(get_emoji_unicode_dict('en'))
        for emj, data in emoji.EMOJI_DATA.items():
            if 'alias' in data and data['status'] <= emoji.STATUS['fully_qualified']:
                for alias in data['alias']:
                    _ALIASES_UNICODE[alias] = emj

        for off, val in enumerate(range(0x1F1E6, 0x1F200)):
            ascval = chr(off + ord('a'))
            _ALIASES_UNICODE[f":regional_indicator_{ascval}:"] = chr(val) + chr(0x200B)

    return _ALIASES_UNICODE
