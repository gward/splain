"""Source-neutral news types."""

import dataclasses
import datetime
import typing


@dataclasses.dataclass
class NewsStory:
    title: str
    source: str
    published_at: str
    url: str
    description: str | None = None


FetchFunction = typing.Callable[[str, datetime.date, int, str], list[NewsStory]]
