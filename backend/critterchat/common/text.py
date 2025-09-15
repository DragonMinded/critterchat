from typing import List


KNOWN_SPACES: List[str] = [
    "\u0020",
    "\u00A0",
    "\u180E",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2008",
    "\u200A",
    "\u200B",
    "\u202F",
    "\u205F",
    "\u3000",
    "\uFEFF",
]


def convert_spaces(string: str) -> str:
    for space in KNOWN_SPACES:
        string = string.replace(space, " ")
    return string
