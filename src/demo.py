"""Explicitly fictional, offline fixture for reviewing the complete output flow."""

from datetime import datetime, timedelta

from src.models import Analysis, Article, Scores
from src.utils import fingerprint


def demo_articles(now: datetime) -> list[Article]:
    records = [
        (
            "Operations",
            "Örnek havayolu aksaklık yönetimi pilotu başlattı",
            "Bu kurgusal örnekte bir havayolu, yeniden rezervasyon önerilerini çalışanlara "
            "sunan bir karar destek sistemi için pilot başlattığını duyurdu.",
            "Benzer bir yaklaşım, aksaklık sırasında seçeneklerin daha hızlı değerlendirilmesine "
            "yardımcı olabilir. Örnekte ölçülmüş bir tasarruf bildirilmemiştir.",
            "Operasyon ekipleriyle sınırlı bir pilot ve insan onayı gerektiren bir öneri akışı "
            "değerlendirilebilir.",
            ["Operasyon", "Dijital", "BT"],
        ),
        (
            "Customer Experience",
            "Örnek havalimanı dijital bagaj bildirimlerini deniyor",
            "Bu kurgusal örnekte bir havalimanı, bagaj durumunu mobil bildirimlerle paylaşan "
            "bir deneme programı açıkladı.",
            "Zamanında durum bilgisi, yolcu iletişimini iyileştirmek için değerlendirilebilir. "
            "Gerçek bir havalimanı uygulaması hakkında iddia içermez.",
            "Havalimanı veri erişimi uygun olduğunda mobil uygulamada bagaj bildirimleri için "
            "bir fizibilite çalışması yapılabilir.",
            ["Müşteri Deneyimi", "Dijital", "BT"],
        ),
        (
            "AI",
            "Örnek teknoloji şirketi destek talepleri sınıflandırma aracını tanıttı",
            "Bu kurgusal örnekte bir teknoloji şirketi, destek taleplerini konuya göre "
            "gruplandıran ve insan incelemesine yönlendiren bir araç tanıttı.",
            "Talep sınıflandırma, müşteri hizmetlerinde önceliklendirmeyi destekleyebilir. "
            "Performans ve Türkçe kalitesi ayrıca doğrulanmalıdır.",
            "Anonimleştirilmiş örnek talepler üzerinde doğruluk ve hata analizi yapılabilir.",
            ["Müşteri Hizmetleri", "Veri", "BT"],
        ),
    ]
    articles = []
    for index, (category, title, summary, why, use_case, teams) in enumerate(records):
        url = f"https://example.com/fictional-demo/{index}"
        identifier = fingerprint(url)
        articles.append(
            Article(
                id=identifier,
                hash=identifier,
                title=title,
                description=summary,
                url=url,
                source="Kurgusal örnek kaynak",
                feed_name="Offline demo",
                category="technology" if category == "AI" else "aviation",
                priority=2,
                published_at=now - timedelta(hours=index + 1),
                collected_at=now,
                analysis=Analysis(
                    article_id=identifier,
                    relevant=True,
                    category=category,
                    title_tr=title,
                    summary=summary,
                    why_it_matters_for_ajet=why,
                    possible_ajet_use_case=use_case,
                    affected_teams=teams,
                    scores=Scores(
                        ajet_relevance=9 - index,
                        business_impact=8,
                        novelty=7,
                        feasibility=7,
                        urgency=5,
                    ),
                ),
            )
        )
    return articles
