"""Play API response models."""
from abc import ABC
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from functools import cached_property
from typing import Any, Iterable, Iterator, Optional, Type, TypeVar, Union, cast

from ..exceptions import DlsiteError


_PM = TypeVar("_PM", bound="_PlayModel")


@dataclass(frozen=True)
class _PlayModel(ABC):  # noqa: B024
    """Play API model."""

    @classmethod
    def from_json(cls: Type[_PM], data: dict[str, Any]) -> _PM:
        """Construct a model from JSON response.

        Args:
            data: ``download_token`` JSON data.

        Returns:
            A new model.
        """
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass(frozen=True)
class DownloadToken(_PlayModel):
    """Play API download token."""

    token: str
    expires_at: datetime
    url: str
    workno: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DownloadToken":
        """Construct a DownloadToken from JSON response.

        Args:
            data: ``download_token`` JSON data.

        Returns:
            A new download token.

        Raises:
            DlsiteError: An error occured.
        """
        try:
            params = data["params"]
            data["token"] = params["token"]
            data["expires_at"] = datetime.fromtimestamp(
                params["expiration"], tz=timezone.utc
            )
            return super().from_json(data)
        except KeyError as e:  # pragma: no cover
            raise DlsiteError("Got unexpected download_token data.") from e

    @property
    def expiration(self) -> int:
        """Return expiration as POSIX timestamp."""
        return int(self.expires_at.timestamp())

    @property
    def params(self) -> dict[str, Any]:
        """Return query params dictionary."""
        return {
            "expiration": self.expiration,
            "token": self.token,
        }


@dataclass(frozen=True)
class PlayFile(_PlayModel):
    """DLsite Play play-able file."""

    length: int
    type: str
    files: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, self.type, self.files)

    @property
    def size(self) -> str:
        """Return length as human readable size."""
        length = float(self.length)
        for prefix in ("", "K", "M"):
            if abs(length) < 1024.0:
                return f"{length:3.1f}{prefix}B"
            length /= 1024.0
        return f"{length:.1f}GB"

    @property
    def optimized_name(self) -> str:
        """Return optimized file name."""
        return cast(str, self.files["optimized"]["name"])

    @property
    def optimized_length(self) -> int:
        """Return optimized file length in bytes."""
        return cast(int, self.files["optimized"]["length"])

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "PlayFile":
        """Construct a PlayFile from JSON response.

        Args:
            data: ``ziptree`` JSON playfile data.

        Returns:
            A new PlayFile.
        """
        type_ = data["type"]
        files = data[type_]
        return cls(data["length"], data["type"], files)


@dataclass(frozen=True)
class _TreeFile(_PlayModel):
    """ZipTree tree file entry."""

    hashname: str
    name: str


@dataclass(frozen=True)
class _TreeFolder(_PlayModel):
    """ZipTree tree folder entry."""

    children: list["_TreeEntry"]
    name: str
    path: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "_TreeFolder":
        """Construct a ZipTree from JSON response.

        Args:
            data: ``ziptree`` JSON data.

        Returns:
            A new tree entry.
        """
        children = [_tree_entry(entry) for entry in data.get("children", [])]
        return cls(children, data["name"], data["path"])


_TreeEntry = Union[_TreeFile, _TreeFolder]


def _tree_entry(data: dict[str, Any]) -> _TreeEntry:
    if data["type"] == "file":
        return _TreeFile.from_json(data)
    if data["type"] == "folder":
        return _TreeFolder.from_json(data)
    raise DlsiteError(  # pragma: no cover
        f"Unsupported ziptree entry type: {data['type']}"
    )


@dataclass(frozen=True)
class ZipTree(_PlayModel, Mapping[str, PlayFile]):
    """Play API zip tree.

    Provides an additional dict-like interface to access PlayFiles in the tree
    by relative path.

    Note:
        Paths are separated by the POSIX path separator ``/``.
    """

    hash: str
    playfile: dict[str, PlayFile]
    tree: list[_TreeEntry]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ZipTree":
        """Construct a ZipTree from JSON response.

        Args:
            data: ``ziptree`` JSON data.

        Returns:
            A new download token.

        Raises:
            DlsiteError: An error occured.
        """
        try:
            hash = data["hash"]
            playfile = {
                key: PlayFile.from_json(value)
                for key, value in data.get("playfile", {}).items()
            }
            tree = [_tree_entry(entry) for entry in data.get("tree", [])]
        except KeyError as e:  # pragma: no cover
            raise DlsiteError("Got unexpected ZipTree data.") from e
        return cls(hash=hash, playfile=playfile, tree=tree)

    @cached_property
    def _dict(self) -> dict[str, PlayFile]:
        return {path: playfile for path, playfile in self._walk(self.tree)}

    def _walk(
        self, entries: Iterable[_TreeEntry], parent: Optional[str] = None
    ) -> Iterator[tuple[str, PlayFile]]:
        for entry in entries:
            if isinstance(entry, _TreeFile):
                path = "/".join([parent, entry.name]) if parent else entry.name
                playfile = self.playfile.get(entry.hashname)
                if playfile is not None:  # pragma: no cover
                    yield path, playfile
            elif isinstance(entry, _TreeFolder):
                yield from self._walk(entry.children, entry.path)

    def __getitem__(self, key: Any) -> PlayFile:
        return self._dict.__getitem__(key)

    def __len__(self) -> int:
        return len(self._dict)

    def __iter__(self) -> Iterator[str]:
        return iter(self._dict)
