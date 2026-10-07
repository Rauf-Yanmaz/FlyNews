"""Small, dependency-free normalization helpers."""

import hashlib
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utc_now() -> datetime:
    return datetime.now(UTC)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def plain_text(value: str, limit: int = 3000) -> str:
    parser = _TextExtractor()
    parser.feed(value[:100_000])
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:limit]


def normalize_url(value: str) -> str:
    """Strip tracking only; keep meaningful query parameters and path case."""
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        raise ValueError("Invalid URL")
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Expected an absolute HTTP(S) URL")
    if parts.username or parts.password or len(value) > 2000:
        raise ValueError("Invalid article URL")
    host = parts.hostname.lower().encode("idna").decode("ascii")
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    if (
        port
        and not (parts.scheme.lower() == "https" and port == 443)
        and not (parts.scheme.lower() == "http" and port == 80)
    ):
        host += f":{port}"
    query = sorted(
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
    )
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(query), ""))
