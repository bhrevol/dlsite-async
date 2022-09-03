"""DLsite work classes."""
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, List, Mapping, Optional


class AgeCategory(IntEnum):
    """Work age rating."""

    ALL_AGES = 1
    R15 = 2
    R18 = 3


class BookType(str, Enum):
    """Book type."""

    BOOK = "comic"
    MAGAZINE = "magazine"
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
    PUZZLE = "PZL"
    ROLE_PLAYING = "RPG"
    SHOOTING = "SHT"
    SIMULATION = "SLN"
    TABLE = "TBL"
    TOOLS_ACCESSORIES = "TOL"
    TYPING = "TYP"
    VIDEO = "MOV"
    VOICE_ASMR = "SOU"
    VOICED_COMIC = "VCM"
    WEBTOON = "WBT"


@dataclass
class Work:
    """DLsite work (product) class."""

    product_id: str
    site_id: str
    maker_id: str
    work_name: str
    age_category: AgeCategory
    circle: Optional[str] = None
    brand: Optional[str] = None
    publisher: Optional[str] = None
    work_image: Optional[str] = None
    regist_date: Optional[datetime] = None
    work_type: Optional[WorkType] = None
    book_type: Optional[BookType] = None
    announce_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    series: Optional[str] = None
    scenario: Optional[List[str]] = None
    illustration: Optional[List[str]] = None
    voice_actor: Optional[List[str]] = None
    author: Optional[List[str]] = None
    music: Optional[List[str]] = None
    writer: Optional[List[str]] = None
    genre: Optional[List[str]] = None
    label: Optional[str] = None
    event: Optional[List[str]] = None
    file_format: Optional[List[str]] = None
    file_size: Optional[str] = None
    language: Optional[List[str]] = None
    page_count: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Work":
        """Construct Work from a dictionary."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    @property
    def release_date(self) -> Optional[datetime]:
        """Release date."""
        return self.regist_date
