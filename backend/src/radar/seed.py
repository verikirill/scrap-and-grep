"""Default sources and reader profiles, plus the sample-data importer."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import Article, Profile, Source
from radar.domain import Interest, ProfileSpec
from radar.text import content_hash

# (slug, name, feed, site, category, language, fetch_full_text)
# Every feed here answered with parseable entries on 2026-09-30. Full-text
# fetching is on only where the feed carries a one-line teaser.
DEFAULT_SOURCES: tuple[tuple[str, str, str, str, str, str, bool], ...] = (
    ("habr-infosec", "Хабр: Информационная безопасность", "https://habr.com/ru/rss/hubs/infosecurity/articles/all/?fl=ru", "https://habr.com/ru/hubs/infosecurity/", "security", "ru", False),
    ("securitylab", "SecurityLab.ru", "https://www.securitylab.ru/_services/export/rss/", "https://www.securitylab.ru", "security", "ru", True),
    ("anti-malware", "Anti-Malware.ru", "https://www.anti-malware.ru/news/feed", "https://www.anti-malware.ru", "security", "ru", False),
    ("xakep", "Хакер", "https://xakep.ru/feed/", "https://xakep.ru", "security", "ru", False),
    ("securelist-ru", "Securelist (Лаборатория Касперского)", "https://securelist.ru/feed/", "https://securelist.ru", "security", "ru", False),
    ("cnews-safe", "CNews: Безопасность", "https://safe.cnews.ru/inc/rss/safe.xml", "https://safe.cnews.ru", "security", "ru", True),
    ("habr-pt", "Хабр: Positive Technologies", "https://habr.com/ru/rss/companies/pt/articles/?fl=ru", "https://habr.com/ru/companies/pt/", "security", "ru", False),
    ("habr-kaspersky", "Хабр: Лаборатория Касперского", "https://habr.com/ru/rss/companies/kaspersky/articles/?fl=ru", "https://habr.com/ru/companies/kaspersky/", "security", "ru", False),
    ("habr-solar", "Хабр: Солар", "https://habr.com/ru/rss/companies/solarsecurity/articles/?fl=ru", "https://habr.com/ru/companies/solarsecurity/", "security", "ru", False),
    ("habr-bizone", "Хабр: BI.ZONE", "https://habr.com/ru/rss/companies/bizone/articles/?fl=ru", "https://habr.com/ru/companies/bizone/", "security", "ru", False),
    ("thehackernews", "The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "https://thehackernews.com", "security", "en", False),
    ("bleepingcomputer", "BleepingComputer", "https://www.bleepingcomputer.com/feed/", "https://www.bleepingcomputer.com", "security", "en", True),
    ("securityweek", "SecurityWeek", "https://www.securityweek.com/feed/", "https://www.securityweek.com", "security", "en", False),
    ("darkreading", "Dark Reading", "https://www.darkreading.com/rss.xml", "https://www.darkreading.com", "security", "en", False),
    ("krebs", "Krebs on Security", "https://krebsonsecurity.com/feed/", "https://krebsonsecurity.com", "security", "en", False),
    ("theregister-security", "The Register: Security", "https://www.theregister.com/security/headlines.atom", "https://www.theregister.com/security/", "security", "en", False),
    ("sans-isc", "SANS Internet Storm Center", "https://isc.sans.edu/rssfeed_full.xml", "https://isc.sans.edu", "security", "en", False),
    ("kaspersky-ics-cert", "Kaspersky ICS CERT", "https://ics-cert.kaspersky.ru/feed/", "https://ics-cert.kaspersky.ru", "ics", "ru", False),
    ("cisa-ics", "CISA ICS Advisories", "https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml", "https://www.cisa.gov/news-events/cybersecurity-advisories", "ics", "en", False),
    ("industrialcyber", "Industrial Cyber", "https://industrialcyber.co/feed/", "https://industrialcyber.co", "ics", "en", False),
    ("habr-scada", "Хабр: SCADA", "https://habr.com/ru/rss/hubs/scada/articles/all/?fl=ru", "https://habr.com/ru/hubs/scada/", "ics", "ru", False),
    ("habr-sysadmin", "Хабр: Системное администрирование", "https://habr.com/ru/rss/hubs/sys_admin/articles/all/?fl=ru", "https://habr.com/ru/hubs/sys_admin/", "it", "ru", False),
    ("habr-devops", "Хабр: DevOps", "https://habr.com/ru/rss/hubs/devops/articles/all/?fl=ru", "https://habr.com/ru/hubs/devops/", "it", "ru", False),
    ("habr-ai", "Хабр: Искусственный интеллект", "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/all/?fl=ru", "https://habr.com/ru/hubs/artificial_intelligence/", "it", "ru", False),
    ("habr-network", "Хабр: Сетевые технологии", "https://habr.com/ru/rss/hubs/network_technologies/articles/all/?fl=ru", "https://habr.com/ru/hubs/network_technologies/", "it", "ru", False),
    ("opennet", "OpenNET", "https://www.opennet.ru/opennews/opennews_all_utf.rss", "https://www.opennet.ru", "it", "ru", False),
    ("cnews", "CNews", "https://www.cnews.ru/inc/rss/news.xml", "https://www.cnews.ru", "it", "ru", False),
    ("tadviser", "TAdviser", "https://www.tadviser.ru/xml/tadviser.xml", "https://www.tadviser.ru", "it", "ru", True),
    ("servernews", "ServerNews", "https://servernews.ru/rss", "https://servernews.ru", "it", "ru", False),
    ("comnews", "ComNews", "https://www.comnews.ru/rss", "https://www.comnews.ru", "it", "ru", False),
    ("minenergo", "Минэнерго России", "https://minenergo.gov.ru/rss", "https://minenergo.gov.ru", "energy", "ru", False),
    ("renen", "RenEn: возобновляемая энергетика", "https://renen.ru/feed/", "https://renen.ru", "energy", "ru", False),
    ("utilitydive", "Utility Dive", "https://www.utilitydive.com/feeds/news/", "https://www.utilitydive.com", "energy", "en", False),
    ("power-technology", "Power Technology", "https://www.power-technology.com/feed/", "https://www.power-technology.com", "energy", "en", False),
    ("nkcki", "НКЦКИ (safe-surf.ru)", "https://safe-surf.ru/rss/", "https://safe-surf.ru", "regulator", "ru", True),
)  # fmt: skip

DEFAULT_PROFILES: tuple[ProfileSpec, ...] = (
    ProfileSpec(
        name="Специалист по ИБ АСУ ТП",
        role=(
            "Инженер по информационной безопасности в электросетевой компании. Отвечает за "
            "защиту АСУ ТП подстанций и диспетчерских центров, управление уязвимостями и "
            "выполнение требований к объектам КИИ."
        ),
        interests=(
            Interest(
                id="ics-security",
                title="Безопасность АСУ ТП и промышленных систем",
                description="Уязвимости и атаки на SCADA, ПЛК, РЗА и промышленные протоколы.",
                keywords=("АСУ ТП", "SCADA", "ПЛК", "ICS", "OT", "Modbus", "МЭК 61850", "IEC 61850", "промышленная автоматизация", "Siemens", "Schneider Electric", "PLC"),
                weight=1.3,
            ),
            Interest(
                id="vulnerabilities",
                title="Уязвимости и обновления безопасности",
                description="Критические уязвимости, эксплойты и патчи для корпоративного ПО и сетевого оборудования.",
                keywords=("уязвимость", "CVE", "эксплойт", "патч", "zero-day", "0-day", "RCE", "vulnerability", "exploit"),
            ),
            Interest(
                id="energy-attacks",
                title="Атаки на энергетику и критическую инфраструктуру",
                description="Инциденты, APT-группировки и шифровальщики, нацеленные на энергокомпании и объекты КИИ.",
                keywords=("энергетика", "электросети", "критическая инфраструктура", "КИИ", "power grid", "critical infrastructure", "utility", "шифровальщик", "ransomware", "APT"),
                weight=1.2,
            ),
            Interest(
                id="regulation",
                title="Требования регуляторов по ИБ",
                description="Приказы и методические документы ФСТЭК, ФСБ и НКЦКИ, изменения в 187-ФЗ, импортозамещение средств защиты.",
                keywords=("ФСТЭК", "ФСБ", "НКЦКИ", "187-ФЗ", "ГосСОПКА", "категорирование", "импортозамещение", "сертификация"),
            ),
        ),
        exclusions=("вакансии и карьера", "обзор смартфона", "игры и киберспорт"),
        min_score=0.5,
        max_items=20,
    ),
    ProfileSpec(
        name="Руководитель ИТ-инфраструктуры",
        role=(
            "Начальник отдела эксплуатации ИТ-инфраструктуры генерирующей компании. Отвечает "
            "за ЦОД, сети, платформы виртуализации и переход на отечественное ПО."
        ),
        interests=(
            Interest(
                id="infrastructure",
                title="Инфраструктура и эксплуатация",
                description="Kubernetes, Linux, виртуализация, сети, мониторинг, практика DevOps и SRE.",
                keywords=("Kubernetes", "Linux", "виртуализация", "DevOps", "мониторинг", "контейнеры", "сеть", "SRE", "PostgreSQL"),
                weight=1.2,
            ),
            Interest(
                id="import-substitution",
                title="Импортозамещение и отечественное ПО",
                description="Российские ОС, СУБД, платформы виртуализации, требования реестра и опыт миграции.",
                keywords=("импортозамещение", "реестр российского ПО", "Astra Linux", "РЕД ОС", "Postgres Pro", "отечественное ПО", "миграция"),
            ),
            Interest(
                id="datacenter",
                title="ЦОД, серверы и системы хранения",
                description="Серверное оборудование, СХД, процессоры, энергопотребление и строительство дата-центров.",
                keywords=("ЦОД", "дата-центр", "сервер", "СХД", "процессор", "GPU", "data center"),
            ),
            Interest(
                id="ai-ops",
                title="ИИ в разработке и эксплуатации",
                description="Языковые модели и ИИ-агенты в инженерной работе: внедрение, риски, инфраструктура.",
                keywords=("LLM", "ИИ-агент", "нейросеть", "машинное обучение", "языковая модель", "AI agent"),
                weight=0.9,
            ),
            Interest(
                id="infra-vulnerabilities",
                title="Уязвимости в инфраструктурном ПО",
                description="Критические уязвимости в ОС, гипервизорах, сетевом оборудовании и средствах администрирования.",
                keywords=("уязвимость", "CVE", "патч", "обновление безопасности", "vulnerability"),
                weight=0.9,
            ),
        ),
        exclusions=("вакансии и карьера", "обзор смартфона", "игры и киберспорт"),
        min_score=0.5,
        max_items=20,
    ),
    ProfileSpec(
        name="Директор по цифровой трансформации",
        role=(
            "Директор по цифровой трансформации энергетического холдинга. Принимает решения "
            "о цифровых проектах, бюджете на ИТ и ИБ и отвечает перед советом директоров за "
            "киберриски."
        ),
        interests=(
            Interest(
                id="digital-energy",
                title="Цифровизация энергетики",
                description="Цифровые подстанции, умные сети, интеллектуальный учёт, накопители, ВИЭ и цифровые двойники.",
                keywords=("цифровая подстанция", "умные сети", "smart grid", "интеллектуальный учёт", "цифровой двойник", "накопитель энергии", "ВИЭ", "электроэнергетика", "energy storage"),
                weight=1.3,
            ),
            Interest(
                id="major-incidents",
                title="Крупные киберинциденты и их последствия",
                description="Резонансные атаки, утечки и простои с оценкой ущерба, особенно в энергетике и промышленности.",
                keywords=("кибератака", "утечка данных", "ущерб", "простой", "шифровальщик", "cyberattack", "breach", "outage"),
            ),
            Interest(
                id="it-regulation",
                title="Госрегулирование ИТ и ИБ",
                description="Законы, постановления и инициативы Минцифры, Минэнерго и ФСТЭК, меры поддержки и штрафы.",
                keywords=("Минцифры", "Минэнерго", "законопроект", "постановление", "штраф", "регулирование", "ФСТЭК"),
            ),
            Interest(
                id="it-market",
                title="ИТ-рынок: сделки, бюджеты, импортозамещение",
                description="Крупные контракты, слияния, уход и приход вендоров, переход на отечественные решения.",
                keywords=("импортозамещение", "контракт", "сделка", "вендор", "тендер", "инвестиции"),
                weight=0.9,
            ),
            Interest(
                id="ai-energy",
                title="ИИ и энергопотребление дата-центров",
                description="Спрос ИИ на электроэнергию, строительство ЦОД, применение ИИ в энергетике.",
                keywords=("дата-центр", "энергопотребление", "ИИ", "data center", "power demand", "искусственный интеллект"),
            ),
        ),
        exclusions=("вакансии и карьера", "обзор смартфона", "игры и киберспорт"),
        min_score=0.5,
        max_items=15,
    ),
)  # fmt: skip


async def seed_defaults(session: AsyncSession) -> dict[str, int]:
    """Insert default sources and profiles that are missing. Safe to repeat."""
    rows = [
        {
            "slug": slug,
            "name": name,
            "feed_url": feed,
            "site_url": site,
            "category": category,
            "language": language,
            "fetch_full_text": full_text,
        }
        for slug, name, feed, site, category, language, full_text in DEFAULT_SOURCES
    ]
    inserted = await session.execute(
        insert(Source).values(rows).on_conflict_do_nothing().returning(Source.id)
    )
    profiles_added = 0
    if not await session.scalar(select(func.count()).select_from(Profile)):
        for spec in DEFAULT_PROFILES:
            session.add(Profile(name=spec.name, spec=spec.model_dump(mode="json")))
            profiles_added += 1
    return {"sources": len(inserted.all()), "profiles": profiles_added}


async def import_articles(session: AsyncSession, path: Path) -> int:
    """Load a JSONL snapshot of articles (see `radar export-articles`).

    Sources are matched by slug; lines that reference an unknown source are
    skipped.
    """
    found = await session.execute(select(Source.slug, Source.id))
    slugs: dict[str, int] = {row.slug: row.id for row in found.all()}
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            source_id = slugs.get(record["source"])
            if source_id is None:
                continue
            body = record.get("content") or record.get("summary") or ""
            rows.append(
                {
                    "source_id": source_id,
                    "url": record["url"],
                    "title": record["title"],
                    "summary": record.get("summary", ""),
                    "content": record.get("content"),
                    "author": record.get("author"),
                    "tags": record.get("tags", []),
                    "language": record.get("language", "ru"),
                    "published_at": datetime.fromisoformat(record["published_at"]),
                    "content_hash": content_hash(record["title"], body),
                }
            )
    inserted = 0
    for start in range(0, len(rows), 500):
        result = await session.execute(
            insert(Article)
            .values(rows[start : start + 500])
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(Article.id)
        )
        inserted += len(result.all())
    return inserted


async def export_articles(
    session: AsyncSession, path: Path, since: datetime | None, content_limit: int | None = None
) -> int:
    """Write articles as JSONL, newest first. `content_limit` trims the full text."""
    statement = select(Article).order_by(Article.published_at.desc())
    if since is not None:
        statement = statement.where(Article.published_at >= since)
    articles = (await session.execute(statement)).scalars().all()
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for article in articles:
            record = {
                "source": article.source.slug,
                "url": article.url,
                "title": article.title,
                "summary": article.summary,
                "content": article.content[:content_limit] if article.content else None,
                "author": article.author,
                "tags": article.tags,
                "language": article.language,
                "published_at": article.published_at.isoformat(),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(articles)
