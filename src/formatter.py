"""Safe Turkish Telegram HTML, split exclusively between complete news items."""

from dataclasses import dataclass
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from src.models import Article
from src.utils import _TextExtractor

MONTHS = (
    "",
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)
ICONS = {
    "Aviation": "✈️",
    "AI": "🤖",
    "Customer Experience": "👥",
    "Operations": "⚙️",
    "Commercial": "📈",
    "Airport / Infrastructure": "🏗️",
    "Regulation / Sustainability": "🌿",
    "Cybersecurity / Data": "🔐",
}
SEPARATOR = "\n\n━━━━━━━━━━━━━━\n\n"


@dataclass(frozen=True)
class DigestMessage:
    text: str
    article_ids: tuple[str, ...]


def telegram_length(text: str) -> int:
    # Conservative UTF-16 count after parsing entities (astral emoji consume 2 units).
    parser = _TextExtractor()
    parser.feed(text)
    return len("".join(parser.parts).encode("utf-16-le")) // 2


def format_item(article: Article, index: int) -> str:
    analysis = article.analysis
    if analysis is None:
        raise ValueError("Cannot format an unanalyzed article")
    teams = " • ".join(escape(team) for team in analysis.affected_teams)
    return (
        f"{ICONS[analysis.category]} <b>{index}. {escape(analysis.title_tr)}</b>\n\n"
        f"<b>Ne oldu?</b>\n{escape(analysis.summary)}\n\n"
        f"<b>AJet için neden önemli?</b>\n{escape(analysis.why_it_matters_for_ajet)}\n\n"
        f"💡 <b>Olası AJet uygulaması</b>\n{escape(analysis.possible_ajet_use_case)}\n\n"
        f"🏢 {teams}\n"
        f"📊 AJet ilgisi: {analysis.scores.ajet_relevance}/10 • "
        f"İş etkisi: {analysis.scores.business_impact}/10\n\n"
        f"Kaynak: {escape(article.source)}\n"
        f'<a href="{escape(article.url, quote=True)}">Haberi oku</a>'
    )


def format_digest(
    articles: list[Article],
    now: datetime,
    *,
    demo: bool = False,
    max_length: int = 4096,
) -> list[DigestMessage]:
    if not articles:
        return []
    local_date = now.astimezone(ZoneInfo("Europe/Istanbul"))
    header = (
        "📰 <b>AJet Teknoloji ve Havacılık Bülteni</b>\n"
        f"📅 {local_date.day} {MONTHS[local_date.month]} {local_date.year}"
    )
    if demo:
        header += "\n<b>ÖRNEK • Gerçek haber değildir</b>"
    messages = []
    text = header
    ids: list[str] = []
    for index, article in enumerate(articles, 1):
        item = format_item(article, index)
        if telegram_length(header + SEPARATOR + item) > max_length:
            raise ValueError("A complete news item exceeds Telegram's message limit")
        candidate = text + SEPARATOR + item
        if telegram_length(candidate) > max_length:
            messages.append(DigestMessage(text, tuple(ids)))
            text, ids = header + SEPARATOR + item, [article.id]
        else:
            text = candidate
            ids.append(article.id)
    messages.append(DigestMessage(text, tuple(ids)))
    return messages
