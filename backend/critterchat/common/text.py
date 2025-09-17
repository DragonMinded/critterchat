from typing import List


KNOWN_SPACES: List[str] = [
    "\u0020",
    "\u00A0",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200A",
    "\u200B",
    "\u202F",
    "\u205F",
    "\u3000",
]


KNOWN_WHITE_SPACE: List[str] = [
    "\u115F",
    "\u1160",
    "\u0009",
    "\u000A",
    "\u000B",
    "\u000C",
    "\u000D",
    "\u0085",
    "\u1680",
    "\u17B4",
    "\u17B5",
    "\u2028",
    "\u2029",
    "\u2062",
    "\u2063",
    "\u2064",
    "\u2800",
    "\uFFA0",
]


KNOWN_CONTROL: List[str] = [
    "\u0000",
    "\u0001",
    "\u0002",
    "\u0003",
    "\u0004",
    "\u0005",
    "\u0006",
    "\u0007",
    "\u0008",
    "\u000E",
    "\u0010",
    "\u0011",
    "\u0012",
    "\u0013",
    "\u0014",
    "\u0015",
    "\u0016",
    "\u0017",
    "\u0018",
    "\u0019",
    "\u001A",
    "\u001B",
    "\u001C",
    "\u001D",
    "\u001E",
    "\u001F",
    "\u0080",
    "\u0081",
    "\u0082",
    "\u0083",
    "\u0084",
    "\u0085",
    "\u0086",
    "\u0087",
    "\u0088",
    "\u0089",
    "\u008A",
    "\u008B",
    "\u008C",
    "\u008D",
    "\u008E",
    "\u008F",
    "\u0090",
    "\u0091",
    "\u0092",
    "\u0093",
    "\u0094",
    "\u0095",
    "\u0096",
    "\u0097",
    "\u0098",
    "\u0099",
    "\u009A",
    "\u009B",
    "\u009C",
    "\u009D",
    "\u009E",
    "\u009F",
    "\u00AD",
    "\u061C",
    "\u180B",
    "\u180C",
    "\u180D",
    "\u180E",
    "\u200C",
    "\u200D",
    "\u200E",
    "\u200F",
    "\u202A",
    "\u202B",
    "\u202C",
    "\u202D",
    "\u202E",
    "\u2060",
    "\u2061",
    "\u2065",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\u206A",
    "\u206B",
    "\u206C",
    "\u206D",
    "\u206E",
    "\u206F",
    "\u3164",
    "\uFEFF",
    "\uFFF9",
    "\uFFFA",
    "\uFFFB",
    "\uFFFC",
]


KNOWN_MUSICAL_SYMBOLS = [
    "\U0001D150",
    "\U0001D159",
    "\U0001D173",
    "\U0001D174",
    "\U0001D175",
    "\U0001D176",
    "\U0001D177",
    "\U0001D178",
    "\U0001D179",
    "\U0001D17A",
]


def convert_spaces(string: str) -> str:
    for space in KNOWN_SPACES:
        string = string.replace(space, " ")
    return string


def represents_real_text(string: str) -> bool:
    # Equivalent to space but different widths and such.
    for char in KNOWN_SPACES:
        string = string.replace(char, "")
    # Rendered as whitespace but often has different semantic meaning.
    for char in KNOWN_WHITE_SPACE:
        string = string.replace(char, "")
    # Control characters that aren't rendered directly.
    for char in KNOWN_CONTROL:
        string = string.replace(char, "")
    # Musical symbols that on their own don't represent anything.
    for char in KNOWN_MUSICAL_SYMBOLS:
        string = string.replace(char, "")
    # Language tags, deprecated but somebody could still use one.
    for val in range(0xE0001, 0xE0080):
        string = string.replace(chr(val), "")
    # Variation selectors.
    for val in range(0xFE00, 0xFE10):
        string = string.replace(chr(val), "")
    for val in range(0xE0100, 0xE01F0):
        string = string.replace(chr(val), "")

    return bool(string.strip())
