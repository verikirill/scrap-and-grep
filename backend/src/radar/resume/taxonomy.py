"""Professional areas the product knows about, and how to spot them in a resume.

The offline extractor works from this table alone: a resume that mentions
enough of an area's terms gets the matching news interest. With a language
model the table is not consulted, the model writes the interests itself.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Area:
    id: str
    # What the interest is called in a profile, and the description the
    # grader reads.
    title: str
    description: str
    # Search terms for publications on the topic.
    keywords: tuple[str, ...]
    # Names as written in a resume. Shown to the reader as recognised skills.
    # Latin names match as whole words, Cyrillic ones by word prefix.
    skills: tuple[str, ...]
    # Word stems that count as evidence but are not worth showing.
    stems: tuple[str, ...] = ()


AREAS: tuple[Area, ...] = (
    Area(
        id="ics-security",
        title="Безопасность АСУ ТП и промышленных сетей",
        description="Уязвимости и атаки на SCADA, ПЛК, РЗА и телемеханику, бюллетени вендоров промышленной автоматизации.",
        keywords=("АСУ ТП", "SCADA", "ПЛК", "ICS", "OT security", "промышленная автоматизация", "Modbus", "МЭК 61850", "Siemens", "Schneider Electric"),
        skills=("АСУ ТП", "SCADA", "ПЛК", "PLC", "Modbus", "МЭК 61850", "IEC 61850", "IEC 62443", "OPC UA", "РЗА", "Siemens", "Schneider Electric", "KICS", "PT ISIM"),
        stems=("телемеханик", "промышленн", "технологическ", "подстанц"),
    ),
    Area(
        id="kii-regulation",
        title="Регулирование КИИ и требования ФСТЭК",
        description="Изменения в 187-ФЗ, приказы ФСТЭК и ФСБ, категорирование объектов, требования к значимым объектам КИИ.",
        keywords=("КИИ", "187-ФЗ", "ФСТЭК", "ГосСОПКА", "НКЦКИ", "категорирование", "значимый объект", "приказ ФСТЭК"),
        skills=("КИИ", "187-ФЗ", "152-ФЗ", "ФСТЭК", "ГосСОПКА", "НКЦКИ", "ISO 27001", "PCI DSS", "ГОСТ 57580"),
        stems=("категорирован", "аттестац", "комплаенс", "compliance", "регулятор", "нормативн"),
    ),
    Area(
        id="vulnerability-management",
        title="Уязвимости и обновления безопасности",
        description="Критические уязвимости в ОС, сетевом оборудовании и прикладном ПО, выход исправлений, признаки эксплуатации.",
        keywords=("уязвимость", "CVE", "патч", "обновление безопасности", "эксплойт", "zero-day", "vulnerability"),
        skills=("CVE", "CVSS", "MaxPatrol VM", "Nessus", "OpenVAS", "Qualys", "RedCheck", "Burp Suite", "Metasploit", "OWASP"),
        stems=("уязвимост", "пентест", "pentest", "патч", "сканер", "тестирован на проникновен"),
    ),
    Area(
        id="soc-monitoring",
        title="Мониторинг и реагирование на инциденты",
        description="Практика SOC: обнаружение атак, правила корреляции, расследования, инструменты SIEM, EDR и NTA.",
        keywords=("SOC", "SIEM", "реагирование на инциденты", "EDR", "threat hunting", "расследование", "incident response"),
        skills=("SOC", "SIEM", "EDR", "XDR", "NTA", "IDS", "IPS", "SOAR", "MaxPatrol SIEM", "KUMA", "Splunk", "ArcSight", "QRadar", "Wazuh", "Suricata", "Zeek"),
        stems=("реагирован", "расследован", "инцидент", "форензик", "forensic", "корреляц"),
    ),
    Area(
        id="threat-landscape",
        title="Атаки, группировки и вредоносное ПО",
        description="Кампании APT-групп, шифровальщики, фишинг, техники по MITRE ATT&CK, разборы вредоносного ПО.",
        keywords=("APT", "шифровальщик", "ransomware", "вредоносное ПО", "фишинг", "кибератака", "MITRE ATT&CK", "malware"),
        skills=("MITRE ATT&CK", "APT", "YARA", "IDA Pro", "Ghidra", "Threat Intelligence", "OSINT"),
        stems=("вредонос", "malware", "фишинг", "шифровальщик", "реверс", "киберразведк"),
    ),
    Area(
        id="network-infrastructure",
        title="Сетевая инфраструктура и её защита",
        description="Маршрутизация, межсетевые экраны, VPN и сегментация, уязвимости и обновления сетевого оборудования.",
        keywords=("сетевое оборудование", "межсетевой экран", "маршрутизатор", "VPN", "Cisco", "NGFW", "SD-WAN", "firewall"),
        skills=("Cisco", "Juniper", "Huawei", "MikroTik", "Eltex", "BGP", "OSPF", "MPLS", "VPN", "NGFW", "SD-WAN", "UserGate", "Check Point", "FortiGate", "Континент", "ViPNet", "CCNA", "CCNP"),
        stems=("маршрутиз", "коммутатор", "сетев", "межсетев"),
    ),
    Area(
        id="server-infrastructure",
        title="Серверы, виртуализация и операционные системы",
        description="Гипервизоры, серверные ОС, службы каталогов, резервное копирование и системы хранения.",
        keywords=("виртуализация", "гипервизор", "VMware", "Linux", "Windows Server", "Active Directory", "резервное копирование", "СХД"),
        skills=("Linux", "Windows Server", "Active Directory", "VMware", "vSphere", "Hyper-V", "KVM", "Proxmox", "zVirt", "Astra Linux", "РЕД ОС", "ALD Pro", "Veeam", "Zabbix", "PowerShell", "Bash"),
        stems=("виртуализац", "администрирован", "резервн", "сервер"),
    ),
    Area(
        id="devops-cloud",
        title="DevOps, контейнеры и облака",
        description="Kubernetes и контейнеры, конвейеры доставки, инфраструктура как код, наблюдаемость, облачные платформы.",
        keywords=("Kubernetes", "Docker", "DevOps", "CI/CD", "облако", "Terraform", "контейнер", "cloud"),
        skills=("Kubernetes", "Docker", "Helm", "Terraform", "Ansible", "GitLab CI", "Jenkins", "ArgoCD", "Prometheus", "Grafana", "AWS", "Azure", "Yandex Cloud", "OpenShift", "SRE"),
        stems=("контейнер", "облачн", "devops", "микросервис"),
    ),
    Area(
        id="import-substitution",
        title="Импортозамещение ПО и оборудования",
        description="Переход на отечественные ОС, СУБД, офисные пакеты и оборудование, требования к КИИ, опыт миграций.",
        keywords=("импортозамещение", "отечественное ПО", "реестр российского ПО", "Astra Linux", "миграция", "Postgres Pro"),
        skills=("Astra Linux", "РЕД ОС", "Альт", "Postgres Pro", "МойОфис", "Р7-Офис", "1С"),
        stems=("импортозамещ", "отечественн", "миграц"),
    ),
    Area(
        id="ai-ml",
        title="ИИ и машинное обучение в инженерной работе",
        description="Языковые модели и ИИ-агенты, их внедрение, инфраструктура и риски, прикладное машинное обучение.",
        keywords=("LLM", "ИИ-агент", "нейросеть", "машинное обучение", "языковая модель", "искусственный интеллект", "AI agent"),
        skills=("LLM", "PyTorch", "TensorFlow", "scikit-learn", "MLOps", "NLP", "RAG", "LangChain", "Hugging Face", "Computer Vision", "Data Science"),
        stems=("машинн обучен", "нейросет", "нейронн", "искусственн интеллект"),
    ),
    Area(
        id="data-platforms",
        title="Данные, СУБД и аналитика",
        description="Хранилища и потоковая обработка данных, СУБД, инструменты аналитики и отчётности.",
        keywords=("СУБД", "PostgreSQL", "ClickHouse", "хранилище данных", "Kafka", "аналитика данных", "big data"),
        skills=("SQL", "PostgreSQL", "ClickHouse", "Oracle", "MS SQL", "Kafka", "Spark", "Airflow", "Hadoop", "Greenplum", "Power BI", "Tableau", "ETL", "DWH"),
        stems=("аналитик данн", "хранилищ данн", "базы данн", "баз данн"),
    ),
    Area(
        id="secure-development",
        title="Разработка и безопасность приложений",
        description="Практики безопасной разработки, анализ кода, уязвимости в библиотеках и цепочке поставки.",
        keywords=("безопасная разработка", "DevSecOps", "SAST", "цепочка поставки", "open source", "supply chain", "AppSec"),
        skills=("Python", "Java", "Go", "C#", "C++", "JavaScript", "TypeScript", "DevSecOps", "SAST", "DAST", "AppSec", "Git", "REST API"),
        stems=("разработчик", "разработк", "программист", "developer"),
    ),
    Area(
        id="energy-digital",
        title="Цифровизация энергетики",
        description="Цифровые подстанции, умные сети, интеллектуальный учёт, накопители и цифровые двойники энергообъектов.",
        keywords=("цифровая подстанция", "умные сети", "smart grid", "интеллектуальный учёт", "цифровой двойник", "накопитель энергии", "электроэнергетика", "ВИЭ"),
        skills=("АИИС КУЭ", "АСКУЭ", "АСДУ", "СОТИ АССО", "Smart Grid", "ВИЭ", "цифровая подстанция"),
        stems=("энергетик", "энергосистем", "электросет", "генерац", "диспетчер", "энергосбыт", "подстанц"),
    ),
    Area(
        id="it-management",
        title="Управление ИТ: бюджеты, рынок, регулирование",
        description="Крупные контракты и сделки на ИТ-рынке, меры господдержки, стратегии цифровой трансформации.",
        keywords=("цифровая трансформация", "ИТ-бюджет", "Минцифры", "импортозамещение", "контракт", "вендор", "тендер"),
        skills=("ITIL", "ITSM", "PMBOK", "Agile", "Scrum", "COBIT", "CIO", "PMO"),
        stems=("руководител", "бюджет", "стратег", "трансформац", "закупк", "тендер", "портфел проект"),
    ),
    Area(
        id="risk-and-incidents",
        title="Крупные киберинциденты и киберриски",
        description="Резонансные атаки, утечки и простои с оценкой ущерба, выводы для управления рисками и непрерывностью.",
        keywords=("кибератака", "утечка данных", "ущерб", "простой", "шифровальщик", "cyberattack", "breach", "outage"),
        skills=("CISO", "BCP", "DRP", "управление рисками", "непрерывность бизнеса"),
        stems=("риск", "непрерывност", "утечк", "аудит"),
    ),
    Area(
        id="identity-crypto",
        title="Криптография и управление доступом",
        description="СКЗИ и электронная подпись, инфраструктура ключей, многофакторная аутентификация, привилегированный доступ.",
        keywords=("СКЗИ", "электронная подпись", "PKI", "аутентификация", "MFA", "КриптоПро", "PAM", "управление доступом"),
        skills=("СКЗИ", "PKI", "КриптоПро", "ViPNet", "IAM", "IdM", "PAM", "MFA", "SSO", "Kerberos", "LDAP"),
        stems=("криптограф", "шифрован", "аутентификац", "электронн подпис"),
    ),
    Area(
        id="datacenter",
        title="ЦОД и вычислительное оборудование",
        description="Серверное оборудование, системы хранения, процессоры, энергопотребление и строительство дата-центров.",
        keywords=("ЦОД", "дата-центр", "сервер", "СХД", "процессор", "GPU", "data center"),
        skills=("ЦОД", "СХД", "ИБП", "Dell", "HPE", "Lenovo", "YADRO", "NVIDIA", "SAN", "NAS"),
        stems=("дата-центр", "датацентр", "инженерн инфраструктур"),
    ),
)  # fmt: skip

# Offered when the resume says nothing the table recognises.
FALLBACK_AREA_IDS: tuple[str, ...] = ("risk-and-incidents", "energy-digital")

DEFAULT_EXCLUSIONS: tuple[str, ...] = ("вакансии и карьера", "обзор смартфона", "игры и киберспорт")
