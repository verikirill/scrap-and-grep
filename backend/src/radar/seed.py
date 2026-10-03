"""Default sources and reader profiles, plus the sample-data importer."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.auth import DEMO_EMAIL
from radar.db.models import Article, Profile, Source, User
from radar.domain import Interest, ProfileSpec
from radar.text import content_hash

# (slug, name, feed, site, category, language, fetch_full_text)
# Every feed here answered with parseable entries on 2026-09-30. Full-text
# fetching is on only where the feed carries a one-line teaser. The BDU feeds
# and the PT page were added on 2026-10-02, with the national CA trusted for
# their hosts (radar.ingest.net).
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
    # Full text comes from the data in each vulnerability's page (radar.ingest.bdu).
    ("bdu-incident", "БДУ ФСТЭК: уязвимости, используемые в атаках", "https://bdu.fstec.ru/ubi/vul/incident/rss", "https://bdu.fstec.ru/vul", "regulator", "ru", True),
    ("bdu-danger", "БДУ ФСТЭК: наиболее опасные уязвимости", "https://bdu.fstec.ru/ubi/vul/danger/rss", "https://bdu.fstec.ru/vul/danger", "regulator", "ru", True),
    ("pt-trending", "Positive Technologies: трендовые уязвимости", "https://ptsecurity.com/research/trending-vulnerabilities/", "https://ptsecurity.com/research/trending-vulnerabilities/", "security", "ru", False),
    # From the source lists of the organizers' dataset (docs/task), each feed
    # fetched and parsed on 2026-10-02. Sites without a feed are left out:
    # BI.ZONE, PT ESC, Kaspersky press releases, Security Vision, Cybernews.
    # CISOCLUB answers 403 to a bot that names itself; it is left out too.
    ("solar-4rays", "Solar 4RAYS: исследования угроз", "https://rt-solar.ru/bitrix/rss.php?ID=40&TYPE=Solar4RAYS&LIMIT=20", "https://rt-solar.ru/solar-4rays/blog/", "security", "ru", False),
    ("habr-f6", "Хабр: F6", "https://habr.com/ru/rss/companies/f6/articles/?fl=ru", "https://www.f6.ru/blog/", "security", "ru", False),
    ("1275", "1275.ru: уязвимости и индикаторы", "https://1275.ru/feed", "https://1275.ru", "security", "ru", True),
    ("habr-infosec-news", "Хабр: новости ИБ", "https://habr.com/ru/rss/hubs/infosecurity/news/?fl=ru", "https://habr.com/ru/hubs/infosecurity/news/", "security", "ru", False),
    ("habr-infowatch", "Хабр: InfoWatch", "https://habr.com/ru/rss/companies/infowatch/articles/?fl=ru", "https://www.infowatch.ru/analytics/novosti-ib", "security", "ru", False),
    ("itsec", "ITSec.ru", "https://www.itsec.ru/news/rss.xml", "https://www.itsec.ru/news/all", "security", "ru", True),
    ("infobezopasnost", "Инфобезопасность", "https://infobezopasnost.ru/blog/news/feed/", "https://infobezopasnost.ru/blog/news/", "security", "ru", False),
    ("google-ti", "Google Cloud: Threat Intelligence", "https://feeds.feedburner.com/threatintelligence/pvexyqv7v0v", "https://cloud.google.com/blog/topics/threat-intelligence", "security", "en", False),
    ("microsoft-research", "Microsoft Security: исследования", "https://www.microsoft.com/en-us/security/blog/content-type/research/feed/", "https://www.microsoft.com/en-us/security/blog/content-type/research/", "security", "en", False),
    ("checkpoint-research", "Check Point Research", "https://research.checkpoint.com/feed/", "https://research.checkpoint.com", "security", "en", False),
    ("unit42", "Unit 42", "https://unit42.paloaltonetworks.com/category/threat-research/feed/", "https://unit42.paloaltonetworks.com/category/threat-research/", "security", "en", True),
    ("fortiguard", "FortiGuard Labs", "https://feeds.fortinet.com/fortinet/blog/threat-research&x=1", "https://www.fortinet.com/blog/threat-research", "security", "en", True),
    ("ahnlab-asec", "AhnLab ASEC", "https://asec.ahnlab.com/en/feed/", "https://asec.ahnlab.com/en/", "security", "en", True),
    # Telegram channels of the dataset whose web preview is open and alive.
    ("tg-true-secator", "SecAtor", "https://t.me/s/true_secator", "https://t.me/true_secator", "security", "ru", False),
    ("tg-bdufstecru", "БДУ ФСТЭК России", "https://t.me/s/bdufstecru", "https://t.me/bdufstecru", "regulator", "ru", False),
    ("tg-xakep-ru", "Хакер (Telegram)", "https://t.me/s/xakep_ru", "https://t.me/xakep_ru", "security", "ru", False),
    ("tg-ptescalator", "PT ESC Threat Intelligence", "https://t.me/s/ptescalator", "https://t.me/ptescalator", "security", "ru", False),
    ("tg-four-rays", "4RAYS", "https://t.me/s/four_rays", "https://t.me/four_rays", "security", "ru", False),
    ("tg-cyberok", "CyberOK", "https://t.me/s/cyberok_news", "https://t.me/cyberok_news", "security", "ru", False),
    ("tg-zerodayalert", "ZeroDay Alert", "https://t.me/s/ZerodayAlert", "https://t.me/ZerodayAlert", "security", "ru", False),
    ("tg-alukatsky", "Пост Лукацкого", "https://t.me/s/alukatsky", "https://t.me/alukatsky", "security", "ru", False),
    ("tg-purpleshift", "purple shift", "https://t.me/s/purpleshift", "https://t.me/purpleshift", "security", "ru", False),
    ("tg-knowyouradversary", "Know Your Adversary", "https://t.me/s/knowyouradversary", "https://t.me/knowyouradversary", "security", "ru", False),
    ("tg-cyberguerre", "Cyberguerre", "https://t.me/s/cyberguerre", "https://t.me/cyberguerre", "security", "ru", False),
    ("tg-bitrixkiberbez", "Битрикс: кибербезопасность", "https://t.me/s/bitrixkiberbez", "https://t.me/bitrixkiberbez", "security", "ru", False),
    ("tg-cybersquatting", "Cybersquatting", "https://t.me/s/CyberSquattingChannel", "https://t.me/CyberSquattingChannel", "security", "ru", False),
    ("tg-poxek", "poxek", "https://t.me/s/poxek", "https://t.me/poxek", "security", "ru", False),
    ("tg-proxy-bar", "proxy bar", "https://t.me/s/proxy_bar", "https://t.me/proxy_bar", "security", "ru", False),
    ("tg-threathuntingfather", "Threat Hunting Father", "https://t.me/s/ThreatHuntingFather", "https://t.me/ThreatHuntingFather", "security", "ru", False),
    # The rest of the organizers' lists, checked on 2026-10-03 with ingest/detect.py.
    # Sites without a feed are read as news pages (ingest/listing.py), CISOCLUB,
    # whose feed answers 403 to everyone, through its WordPress API. dbugs,
    # Forbes and the ICS BDU are drawn by script and need the browser step.
    ("dbugs-pt", "dbugs PT: уязвимости", "https://dbugs.ptsecurity.com/vulnerability", "https://dbugs.ptsecurity.com", "security", "en", False),
    ("ctfiot", "CTFIOT", "https://www.ctfiot.com/feed/", "https://www.ctfiot.com/blog", "security", "en", True),
    ("mcafee-labs", "McAfee Labs", "https://www.mcafee.com/blogs/other-blogs/mcafee-labs/", "https://www.mcafee.com/blogs/other-blogs/mcafee-labs/", "security", "en", False),
    ("xlab", "XLab Qianxin", "https://blog.xlab.qianxin.com/rss/", "https://blog.xlab.qianxin.com/", "security", "en", False),
    ("netskope", "Netskope Threat Labs", "https://www.netskope.com/feed", "https://www.netskope.com/the-lens/threat-research", "security", "en", True),
    ("nviso", "NVISO Labs", "https://blog.nviso.eu/feed/", "https://blog.nviso.eu/", "security", "en", False),
    ("tg-offensivetwitter", "OffensiveTwitter", "https://t.me/s/OffensiveTwitter", "https://t.me/OffensiveTwitter", "security", "ru", False),
    ("tg-detectioneasy", "detectioneasy", "https://t.me/s/detectioneasy", "https://t.me/detectioneasy", "security", "ru", False),
    ("tg-redteambro", "RedTeambro", "https://t.me/s/RedTeambro", "https://t.me/RedTeambro", "security", "ru", False),
    ("ria-infosec", "РИА Новости: информационная безопасность", "https://ria.ru/product_informatsionnaya-bezopasnost/", "https://ria.ru", "security", "ru", False),
    ("forbes-infosec", "Forbes: информационная безопасность", "https://www.forbes.ru/tegi/informacionnaya-bezopasnost", "https://www.forbes.ru", "security", "ru", False),
    ("kaspersky-press", "Лаборатория Касперского: пресс-релизы", "https://www.kaspersky.ru/about/press-releases", "https://www.kaspersky.ru", "security", "ru", False),
    ("securenews", "SecureNews", "https://securenews.ru/news/feed/", "https://securenews.ru/news/", "security", "ru", False),
    ("pt-news", "Positive Technologies: новости", "https://ptsecurity.com/ru-ru/about/news/", "https://ptsecurity.com", "security", "ru", False),
    ("security-vision", "Security Vision: новости", "https://www.securityvision.ru/news/", "https://www.securityvision.ru", "security", "ru", False),
    ("kommersant-infosec", "Коммерсантъ: информационная безопасность", "https://www.kommersant.ru/archive/theme/1267", "https://www.kommersant.ru", "security", "ru", False),
    ("cisoclub", "CISOCLUB", "https://cisoclub.ru/wp-json/wp/v2/posts?per_page=20&_fields=id%2Clink%2Ctitle%2Cdate_gmt%2Ccontent%2Cexcerpt&categories=2", "https://cisoclub.ru/category/news/", "security", "ru", False),
    ("securitymedia", "SecurityMedia", "https://securitymedia.org/news/", "https://securitymedia.org", "security", "ru", False),
    ("cybernews", "Cybernews", "https://cybernews.com/security/", "https://cybernews.com", "security", "en", False),
    ("bdu-asutp", "БДУ ФСТЭК: АСУ ТП", "https://bduasutp.fstec.ru/#/news", "https://bduasutp.fstec.ru", "ics", "ru", False),
    ("broadcom-bulletins", "Symantec: Protection Bulletins", "https://www.broadcom.com/api/nocache/mblogs?locale=en-us&limit=20", "https://www.broadcom.com/support/security-center/protection-bulletin", "security", "en", False),
)  # fmt: skip

# Sources that are not feeds; the rest are RSS or Atom.
SOURCE_KINDS = {
    "pt-trending": "pt_trending",
    "broadcom-bulletins": "broadcom",
    "cisoclub": "wordpress",
    **dict.fromkeys(
        (
            "dbugs-pt",
            "mcafee-labs",
            "ria-infosec",
            "forbes-infosec",
            "kaspersky-press",
            "pt-news",
            "security-vision",
            "kommersant-infosec",
            "securitymedia",
            "cybernews",
            "bdu-asutp",
        ),
        "page",
    ),
    **{slug: "telegram" for slug, *_ in DEFAULT_SOURCES if slug.startswith("tg-")},
}

# How the example profiles look in lists (see ProfileLook).
EXAMPLE_LOOKS = {
    "Специалист по ИБ АСУ ТП": ("shield", "red"),
    "Руководитель ИТ-инфраструктуры": ("servers", "blue"),
    "Директор по цифровой трансформации": ("network", "violet"),
    "Руководство и сотрудники: кибербезопасность": ("lock", "orange"),
}

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
        # What a grid company runs on its substations and its perimeter; all
        # of it turns up in the stand's digests.
        systems=("Siemens", "Schneider Electric", "ABB PCM600", "CODESYS", "Cisco", "Fortinet"),
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
        # The dataset's second kind of digest: short briefs with tags, no cards.
        audience="management",
    ),
    # The organizers' second dataset as a profile: what management and staff
    # of an energy company should know about security, without the jargon.
    ProfileSpec(
        name="Руководство и сотрудники: кибербезопасность",
        role=(
            "Руководители и сотрудники энергетической компании без подготовки в ИБ. Им нужно "
            "понимать громкие инциденты, утечки, штрафы и угрозы, которые касаются их лично."
        ),
        interests=(
            Interest(
                id="major-attacks",
                title="Крупные кибератаки и их последствия",
                description="Атаки на российские компании и госорганы: простои, ущерб, кто взял на себя ответственность.",
                keywords=("кибератака", "хакерская атака", "взлом", "шифровальщик", "простой", "ущерб", "DDoS"),
                weight=1.2,
            ),
            Interest(
                id="data-leaks",
                title="Утечки данных",
                description="Утечки персональных данных, коммерческой и государственной тайны, штрафы за них.",
                keywords=("утечка", "слив данных", "персональные данные", "база данных", "оборотный штраф"),
            ),
            Interest(
                id="energy-industry",
                title="Атаки на энергетику и промышленность",
                description="Инциденты в электроэнергетике, нефтегазе и на производстве, угрозы критической инфраструктуре.",
                keywords=("энергетика", "электросети", "КИИ", "промышленность", "SCADA", "АСУ ТП"),
                weight=1.3,
            ),
            Interest(
                id="security-law",
                title="Законы и требования по ИБ",
                description="Новые законы, требования к КИИ, штрафы и сроки импортозамещения.",
                keywords=("законопроект", "Минцифры", "ФСТЭК", "КИИ", "штраф", "импортозамещение", "152-ФЗ", "187-ФЗ"),
            ),
            Interest(
                id="everyday-threats",
                title="Угрозы для сотрудников",
                description="Фишинг, мошенничество, мобильные трояны и уязвимости сервисов, которыми пользуются все.",
                keywords=("фишинг", "мошенники", "троян", "Android", "WhatsApp", "мессенджер", "Госуслуги"),
            ),
        ),
        exclusions=("вакансии и карьера", "обзор смартфона", "игры и киберспорт"),
        min_score=0.5,
        max_items=15,
        audience="management",
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
            "kind": SOURCE_KINDS.get(slug, "rss"),
        }
        for slug, name, feed, site, category, language, full_text in DEFAULT_SOURCES
    ]
    inserted = await session.execute(
        insert(Source).values(rows).on_conflict_do_nothing().returning(Source.id)
    )
    # The example profiles belong to the demo account; a registered reader
    # starts with their own, built from the resume or by hand.
    profiles_added = 0
    demo_id = await session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
    if demo_id is not None:
        existing = set(
            await session.scalars(select(Profile.name).where(Profile.user_id == demo_id))
        )
        for spec in DEFAULT_PROFILES:
            if spec.name in existing:
                # The examples are a template the code owns: guests copy them,
                # nobody edits them. A change to a default reaches them on the
                # next start, and so does a new example.
                await session.execute(
                    update(Profile)
                    .where(Profile.user_id == demo_id, Profile.name == spec.name)
                    .values(spec=spec.model_dump(mode="json"))
                )
                continue
            icon, color = EXAMPLE_LOOKS.get(spec.name, (None, None))
            session.add(
                Profile(
                    user_id=demo_id,
                    name=spec.name,
                    spec=spec.model_dump(mode="json"),
                    icon=icon,
                    color=color,
                )
            )
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
