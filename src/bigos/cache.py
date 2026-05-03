from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from bigos.schema import Document

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "bigos"


class Cache(Protocol):
    def get(self, key: str) -> Document | None: ...
    def set(self, key: str, doc: Document) -> None: ...
    def clear(self) -> None: ...


@dataclass
class DiskCache:
    cache_dir: Path = field(default_factory=lambda: DEFAULT_CACHE_DIR)
    _cache: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        import diskcache as dc

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = dc.Cache(str(self.cache_dir))

    def get(self, key: str) -> Document | None:
        data = self._cache.get(key)
        if data is None:
            return None
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return Document.model_validate_json(data)

    def set(self, key: str, doc: Document) -> None:
        self._cache.set(key, doc.model_dump_json(exclude={"raw"}))

    def clear(self) -> None:
        self._cache.clear()


def make_cache_key(file_sha256: str, backend_name: str, backend_version: str) -> str:
    return f"{file_sha256}:{backend_name}:{backend_version}"
