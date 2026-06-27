"""Source-neutral news types."""

import dataclasses


@dataclasses.dataclass
class NewsStory:
    title: str
    source: str
    published_at: str
    url: str
    description: str | None = None
