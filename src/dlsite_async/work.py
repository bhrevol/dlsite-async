"""DLsite work classes."""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any


class AgeCategory(IntEnum):
    """Work age rating."""

    ALL_AGES = 1
    ALL = 1
    R15 = 2
    R18 = 3


class BookType(str, Enum):
    """Book type."""

    BOOK = "comic"
    MAGAZINE = "magazine"
    PUBLICATION = "publication"
    STANDALONE = "oneshot"


class WorkType(str, Enum):
    """Work type."""

    ACTION = "ACN"
    ADVENTURE = "ADV"
    QUIZ = "QIZ"
    CG_ILLUSTRATIONS = "ICG"
    DIGITAL_NOVEL = "DNV"
    GEKIGA = "SCM"
    ILLUST_MATERIALS = "IMT"
    MANGA = "MNG"
    MISCELLANEOUS = "ET3"
    MISCELLANEOUS_GAME = "ETC"
    MUSIC = "MUS"
    MUSIC_MATERIALS = "AMT"
    NOVEL = "NRE"
    PUBLICATION = "PBC"
    PUZZLE = "PZL"
    ROLE_PLAYING = "RPG"
    SHOOTING = "STG"
    SIMULATION = "SLN"
    TABLE = "TBL"
    TOOLS_ACCESSORIES = "TOL"
    TYPING = "TYP"
    VIDEO = "MOV"
    VOICE_ASMR = "SOU"
    VOICED_COMIC = "VCM"
    WEBTOON = "WBT"


class WorkOption(str, Enum):
    """Work options."""

    AI_GENERATED = "AIG"
    AI_PARTIAL = "AIP"
    APK_FILE = "WAP"
    BROWSER_COMPATIBLE = "DLP"
    BULGARIAN = "BUL"
    CHINESE_SIMPLIFIED = "CHI_HANS"
    CHINESE_TRADITIONAL = "CHI_HANT"
    CZECH = "CZE"
    DANISH = "DAN"
    DUTCH = "DUT"
    ENGLISH = "ENG"
    ESTONIAN = "EST"
    EVENT = "EVT"
    FINNISH = "FIN"
    FRENCH = "FRE"
    GERMAN = "GER"
    GREEK = "GRE"
    GROTESQUE = "GRO"
    HOMOSEXUALITY = "MEN"
    HUNGARIAN = "HUN"
    ICELANDIC = "ICE"
    INDONESIAN = "IND"
    ITALIAN = "ITA"
    JAPANESE = "JPN"
    KOREAN = "KO_KR"
    LATVIAN = "LAV"
    MUSIC = "MS2"
    PDF_FILE = "WPD"
    POLISH = "POL"
    PORTUGUESE = "POR"
    RECOMMENDED_TRANSLATION = "VET"
    REVIEWS = "REV"
    ROMANIAN = "RUM"
    RUSSIAN = "RUS"
    SAVE_BACKUP = "SBK"
    SLOVAK = "SLO"
    SLOVENIAN = "SLV"
    SPANISH = "SPA"
    SWEDISH = "SWE"
    THAI = "THA"
    TRIAL_VERSION = "TRI"
    UKRANIAN = "UKR"
    VIDEO = "MV2"
    VIETNAMESE = "VIE"
    VOICE = "SND"


@dataclass
class Work:
    """DLsite work (product) class."""

    product_id: str
    site_id: str
    maker_id: str
    work_name: str
    age_category: AgeCategory
    circle: str | None = None
    brand: str | None = None
    publisher: str | None = None
    work_image: str | None = None
    regist_date: datetime | None = None
    work_type: WorkType | None = None
    book_type: BookType | None = None
    announce_date: datetime | None = None
    modified_date: datetime | None = None
    scenario: list[str] | None = None
    illustration: list[str] | None = None
    voice_actor: list[str] | None = None
    author: list[str] | None = None
    music: list[str] | None = None
    writer: list[str] | None = None
    genre: list[str] | None = None
    label: str | None = None
    event: list[str] | None = None
    file_format: list[str] | None = None
    file_size: str | None = None
    language: list[str] | None = None
    page_count: int | None = None
    description: str | None = None
    sample_images: list[str] | None = None
    work_name_masked: str | None = None
    title_name: str | None = None
    title_name_masked: str | None = None
    options: list[WorkOption] | None = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Work":
        """Construct Work from a dictionary."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    @property
    def release_date(self) -> datetime | None:
        """Release date."""
        return self.regist_date

    @property
    def series(self) -> str | None:
        """Series name.

        Set for backwards compatibility.
        """
        if self.title_name_masked is not None:
            return self.title_name_masked
        return self.title_name
