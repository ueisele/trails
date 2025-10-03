"""Language support for the trails package."""

from enum import Enum


class Language(Enum):
    """Supported languages for data and translations."""

    NO = "no"  # Norwegian (Bokmål/Nynorsk)
    EN = "en"  # English
