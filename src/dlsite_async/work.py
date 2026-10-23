"""DLsite work classes."""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
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
    maker_name: str | None = None
    work_image: str | None = None
    regist_date: datetime | None = None
    work_type: WorkType | None = None
    book_type: BookType | None = None
    announce_date: datetime | None = None
    update_date: datetime | None = None
    creater: list[str] | None = None
    scenario: list[str] | None = None
    illustration: list[str] | None = None
    voice_actor: list[str] | None = None
    author: list[str] | None = None
    music: list[str] | None = None
    writer: list[str] | None = None
    genre: list[str] | None = None
    label_name: str | None = None
    event: list[str] | None = None
    file_format_legacy: list[str] | None = None
    file_type: str | None = None
    file_type_string: str | None = None
    file_type_special: str | None = None
    contents_file_size: int | None = None
    file_size: str | None = None
    language: list[str] | None = None
    page_count: int | None = None
    sample_images: list[str] | None = None
    work_name_masked: str | None = None
    title_name: str | None = None
    title_name_masked: str | None = None
    options: list[WorkOption] | None = None
    intro: str | None = None
    intro_masked: str | None = None
    intro_s: str | None = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Work":
        """Construct Work from a dictionary."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    @classmethod
    def from_json(
        cls, d: Mapping[str, Any], announce: bool = False, locale: str | None = None
    ) -> "Work":
        """Construct Work from DLsite API product info JSON."""
        info = dict(d)
        info["age_category"] = AgeCategory(info["age_category"])
        info["work_type"] = WorkType(info["work_type"])
        is_en = locale and locale.lower().startswith("en_")
        if info.get("book_type"):
            info["book_type"] = BookType(info["book_type"]["value"])
        if is_en and info.get("maker_name_en"):
            info["maker_name"] = info.get("maker_name_en")
        if announce:
            if info.get("regist_date"):
                info["announce_date"] = cls._datetime_from_timestamp(
                    info["regist_date"]
                )
        else:
            for k in ("regist_date", "update_date"):
                if info.get(k):
                    info[k] = cls._datetime_from_timestamp(info[k])
        if info.get("options"):
            options = []
            for option in info.get("options", "").split("#"):
                try:
                    options.append(WorkOption(option))
                except ValueError:
                    pass
            info["options"] = options
        cls._update_creaters_from_json(info)
        genres = info.get("genres_replaced") or info.get("genre")
        info.pop("genre", None)
        if genres:
            info["genre"] = [genre.get("name") for genre in genres if genre.get("name")]
        langs = [
            edition.get("label")
            for edition in info.get("language_editions", [])
            if edition.get("label")
        ]
        if langs:
            info["language"] = langs
        pages = info.get("pages") or info.get("page_number")
        if pages is not None:
            try:
                info["page_count"] = int(pages)
            except ValueError:
                pass
        name_field = "name_en" if is_en else "name"
        work_options = info.get("work_options")
        if work_options:
            events = [
                v.get(name_field)
                for _, v in work_options.items()
                if v.get("category_id") == "9" and v.get(name_field)
            ]
            if events:
                info["event"] = events
        image_main = info.get("image_main", {}).get("url")
        if image_main:
            info["work_image"] = image_main
        samples = info.get("image_samples", [])
        if samples:
            info["sample_images"] = [
                image.get("url") for image in samples if image.get("url")
            ]
        info.pop("file_size", None)
        contents = info.get("contents", [])
        if contents:
            for content in contents:
                size = content.get("file_size_unit")
                info["file_size"] = size
                break
        return cls.from_dict(info)

    @staticmethod
    def _datetime_from_timestamp(timestamp: str) -> datetime:
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return timestamp.replace(tzinfo=timezone(timedelta(hours=9)))

    @staticmethod
    def _update_creaters_from_json(info: dict[str, Any]) -> None:
        creaters = info.get("creaters", {})
        if creaters:
            for f, k in [
                ("creater", "created"),
                ("illustration", "illust"),
                ("music", "music"),
                ("scenario", "scenario"),
                ("voice_actor", "voice"),
            ]:
                values = [
                    entry.get("name")
                    for entry in creaters.get(f"{k}_by", [])
                    if entry.get("name")
                ]
                if values:
                    info[f] = values
        # in API authors is only set for commercial books, creaters is only set
        # for doujin books, web UI displays author for both
        authors = info.pop("author", None) or info.get("authors")
        if authors:
            values = [
                author.get("author_name")
                for author in authors
                if author.get("author_name")
            ]
            if values:
                info["author"] = values
        if (
            info["work_type"]
            in {WorkType.CG_ILLUSTRATIONS, WorkType.MANGA, WorkType.NOVEL}
            and not authors
            and info.get("creater")
        ):
            info["author"] = info["creater"]

    @property
    def circle(self) -> str | None:
        if self.product_id.startswith("RJ"):
            return self.maker_name
        return None

    @property
    def brand(self) -> str | None:
        if self.product_id.startswith("VJ"):
            return self.maker_name
        return None

    @property
    def publisher(self) -> str | None:
        if self.product_id.startswith("BJ"):
            return self.maker_name
        return None

    @property
    def description(self) -> str | None:
        """Work description."""
        return self.intro_masked or self.intro_s or self.intro

    @property
    def file_format(self) -> list[str]:
        """File formats."""
        if self.file_format_legacy:
            return self.file_format_legacy
        formats: str = []
        if self.file_type_string or self.file_type:
            formats.append(self.file_type_string or self.file_type)
        if self.file_type_special:
            formats.append(self.file_type_special)
        return formats

    @property
    def label(self) -> str | None:
        return self.label_name

    @property
    def modified_date(self) -> datetime | None:
        return self.update_date

    @property
    def release_date(self) -> datetime | None:
        """Release date."""
        return self.regist_date

    @property
    def series(self) -> str | None:
        """Series name."""
        return self.title_name_masked or self.title_name
