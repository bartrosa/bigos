from __future__ import annotations

from typing import Protocol, runtime_checkable

from bigos.schema import Document, Source


@runtime_checkable
class Backend(Protocol):
    name: str
    version: str

    async def run(self, source: Source) -> Document: ...
