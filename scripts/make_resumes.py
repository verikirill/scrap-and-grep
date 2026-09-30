"""Generate the sample resumes in examples/resumes.

    uv run --with reportlab --with python-docx --with pillow --with matplotlib \
        python scripts/make_resumes.py

The people are invented, the employers do not exist, the contacts point to
example.org. Each file exercises a different parser path:

    ics-security-engineer.pdf    two-column PDF with a text layer
    it-infrastructure-lead.docx  DOCX laid out with a table
    ml-engineer.md               plain Markdown
    soc-analyst-scan.png         a picture of a page: readable only with OCR
"""

from pathlib import Path

import matplotlib
from docx import Document
from docx.shared import Pt
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "examples" / "resumes"
# DejaVu ships with matplotlib, covers Cyrillic and may be embedded freely.
FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
REGULAR, BOLD = FONTS / "DejaVuSans.ttf", FONTS / "DejaVuSans-Bold.ttf"

ICS = {
    "name": "Иван Петров",
    "title": "Ведущий инженер по защите АСУ ТП",
    "contacts": [
        "Телефон: +7 (900) 000-00-00",
        "E-mail: ivan.petrov@example.org",
        "Город проживания: Екатеринбург",
        "Дата рождения: 12.03.1988",
    ],
    "skills": [
        "SCADA, ПЛК Siemens S7, РЗА,",
        "МЭК 61850, Modbus, OPC UA,",
        "IEC 62443, 187-ФЗ, ФСТЭК,",
        "KICS for Networks, PT ISIM,",
        "MaxPatrol VM, Nessus,",
        "сегментация сетей, NGFW,",
        "Python, Bash",
    ],
    "summary": (
        "Девять лет в информационной безопасности промышленных систем, последние пять "
        "в электросетевой компании. Отвечаю за защиту АСУ ТП подстанций 110-500 кВ: "
        "аудит, сегментацию технологических сетей, контроль уязвимостей и "
        "взаимодействие с регулятором."
    ),
    "jobs": [
        (
            "2021 - настоящее время",
            "АО «Энергосеть-Пример», ведущий инженер по защите АСУ ТП",
            [
                "Категорирование объектов КИИ и подготовка к проверкам по 187-ФЗ, приказ ФСТЭК № 239.",
                "Внедрение мониторинга технологических сетей на 14 подстанциях (KICS for Networks).",
                "Анализ бюллетеней об уязвимостях ПЛК и SCADA, планирование обновлений с эксплуатацией.",
                "Сегментация сетей телемеханики и РЗА, правила межсетевых экранов.",
            ],
        ),
        (
            "2017 - 2021",
            "ООО «Промзащита-Пример», инженер по информационной безопасности",
            [
                "Аудиты защищённости АСУ ТП на генерирующих объектах, моделирование угроз.",
                "Тестирование на проникновение технологических сегментов, отчёты для заказчика.",
                "Проектирование систем защиты по IEC 62443.",
            ],
        ),
    ],
    "education": "Уральский федеральный университет, информационная безопасность, 2011-2016",
}

INFRA = {
    "name": "Мария Соколова",
    "title": "Руководитель группы ИТ-инфраструктуры",
    "contacts": "Телефон: +7 (900) 000-00-01 | maria.sokolova@example.org | t.me/example_maria",
    "summary": (
        "Двенадцать лет в эксплуатации ИТ-инфраструктуры, шесть из них руковожу группой из "
        "восьми инженеров в генерирующей компании. Отвечаю за серверы, виртуализацию, сети "
        "и резервное копирование двух ЦОД, за бюджет группы и за переход на отечественное ПО."
    ),
    "rows": [
        (
            "2019 - настоящее время",
            "ПАО «Генерация-Пример», руководитель группы ИТ-инфраструктуры. Миграция с VMware "
            "vSphere на zVirt, перевод 600 рабочих мест и 120 серверов на Astra Linux и ALD Pro "
            "вместо Active Directory. Резервное копирование на Veeam, мониторинг Zabbix. Планирование "
            "бюджета, закупки серверов и СХД, работа с вендорами.",
        ),
        (
            "2014 - 2019",
            "ООО «Интегратор-Пример», старший системный администратор. Администрирование Linux и "
            "Windows Server, сети Cisco и MikroTik, VPN между площадками, Kubernetes для внутренних "
            "сервисов, PostgreSQL.",
        ),
    ],
    "skills": (
        "Linux, Astra Linux, Windows Server, Active Directory, ALD Pro, VMware vSphere, zVirt, "
        "Kubernetes, Docker, Ansible, Cisco, MikroTik, BGP, VPN, Veeam, Zabbix, PostgreSQL, "
        "СХД, ИБП, ITIL"
    ),
    "education": "МЭИ, вычислительные машины, комплексы, системы и сети, 2008-2013",
}

ML = """# Дмитрий Кузнецов

**Инженер по машинному обучению**

Почта: dmitry.kuznetsov@example.org
Телефон: +7 (900) 000-00-02
Гражданство: РФ

## О себе

Шесть лет занимаюсь прикладным машинным обучением, последние три года в ИТ-дочке
энергосбытовой компании. Делаю модели прогноза потребления электроэнергии и
внутренние инструменты на языковых моделях: поиск по нормативным документам и
ассистента для диспетчеров.

## Опыт

### 2023 - настоящее время. ООО «Энергосбыт-Цифра-Пример», ведущий ML-инженер

- Прогноз почасового потребления по 40 тысячам точек учёта АИИС КУЭ, градиентный бустинг и
  нейросети на PyTorch.
- RAG-система по технической документации: LangChain, локальные LLM, векторный поиск в
  PostgreSQL.
- Конвейеры данных на Airflow и Kafka, витрины в ClickHouse.
- MLOps: обучение и выкладка моделей в Kubernetes, мониторинг качества.

### 2020 - 2023. АО «Аналитика-Пример», Data Scientist

- Модели оттока и скоринга, scikit-learn, SQL, Spark.
- Отчётность в Power BI.

## Навыки

Python, PyTorch, scikit-learn, LLM, RAG, LangChain, NLP, MLOps, SQL, PostgreSQL, ClickHouse,
Kafka, Airflow, Spark, Docker, Kubernetes, Git

## Образование

НИТУ МИСИС, прикладная математика, 2015-2019
"""

SOC = [
    ("Ольга Васильева", True, 40),
    ("Аналитик SOC второй линии", True, 30),
    ("", False, 22),
    ("Телефон: +7 (900) 000-00-03", False, 22),
    ("E-mail: olga.vasilieva@example.org", False, 22),
    ("", False, 22),
    ("Опыт работы", True, 28),
    ("2022 - настоящее время. АО «Кибермониторинг-Пример», аналитик SOC.", False, 22),
    ("Расследование инцидентов, разбор срабатываний SIEM и EDR,", False, 22),
    ("threat hunting по техникам MITRE ATT&CK, правила корреляции", False, 22),
    ("для KUMA и MaxPatrol SIEM, взаимодействие с ГосСОПКА.", False, 22),
    ("", False, 22),
    ("2019 - 2022. ООО «Сети-Пример», инженер мониторинга.", False, 22),
    ("Суточный мониторинг событий безопасности, анализ фишинга", False, 22),
    ("и вредоносного ПО, Suricata, Wazuh.", False, 22),
    ("", False, 22),
    ("Навыки", True, 28),
    ("SIEM, EDR, SOAR, MITRE ATT&CK, YARA, Suricata, Zeek, Wazuh,", False, 22),
    ("KUMA, MaxPatrol SIEM, реагирование на инциденты, форензика", False, 22),
    ("", False, 22),
    ("Образование", True, 28),
    ("МГТУ им. Н. Э. Баумана, информационная безопасность, 2014-2019", False, 22),
]


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    return [*lines, current] if current else lines


def make_pdf(path: Path) -> None:
    """A narrow left column with contacts and skills, the career on the right.

    Read line by line across the page, the columns interleave; a parser has to
    understand the layout to keep the text in order.
    """
    pdfmetrics.registerFont(TTFont("Body", str(REGULAR)))
    pdfmetrics.registerFont(TTFont("Bold", str(BOLD)))
    page = canvas.Canvas(str(path), pagesize=A4)
    page.setTitle("Резюме")
    width, height = A4
    left_x, left_w = 15 * mm, 55 * mm
    right_x, right_w = 80 * mm, width - 95 * mm

    page.setFillColorRGB(0.95, 0.96, 0.98)
    page.rect(0, 0, 75 * mm, height, stroke=0, fill=1)
    page.setFillColorRGB(0.1, 0.12, 0.16)

    y = height - 25 * mm
    page.setFont("Bold", 15)
    page.drawString(left_x, y, ICS["name"])
    y -= 12 * mm
    page.setFont("Bold", 10)
    page.drawString(left_x, y, "Контакты")
    y -= 6 * mm
    page.setFont("Body", 8.5)
    for line in ICS["contacts"]:
        page.drawString(left_x, y, line)
        y -= 5 * mm
    y -= 6 * mm
    page.setFont("Bold", 10)
    page.drawString(left_x, y, "Навыки")
    y -= 6 * mm
    page.setFont("Body", 8.5)
    for skill in ICS["skills"]:
        for line in _wrap(skill, "Body", 8.5, left_w):
            page.drawString(left_x, y, line)
            y -= 5 * mm

    y = height - 25 * mm
    page.setFont("Bold", 14)
    page.drawString(right_x, y, ICS["title"])
    y -= 9 * mm
    page.setFont("Body", 9.5)
    for line in _wrap(ICS["summary"], "Body", 9.5, right_w):
        page.drawString(right_x, y, line)
        y -= 5 * mm
    y -= 5 * mm
    page.setFont("Bold", 11)
    page.drawString(right_x, y, "Опыт работы")
    y -= 7 * mm
    for period, place, duties in ICS["jobs"]:
        page.setFont("Bold", 9.5)
        page.drawString(right_x, y, period)
        y -= 5 * mm
        for line in _wrap(place, "Bold", 9.5, right_w):
            page.drawString(right_x, y, line)
            y -= 5 * mm
        page.setFont("Body", 9.5)
        for duty in duties:
            for index, line in enumerate(_wrap(duty, "Body", 9.5, right_w - 4 * mm)):
                page.drawString(right_x + (0 if index == 0 else 4 * mm), y, ("- " if index == 0 else "") + line)
                y -= 5 * mm
        y -= 4 * mm
    page.setFont("Bold", 11)
    page.drawString(right_x, y, "Образование")
    y -= 7 * mm
    page.setFont("Body", 9.5)
    for line in _wrap(ICS["education"], "Body", 9.5, right_w):
        page.drawString(right_x, y, line)
        y -= 5 * mm
    page.save()


def make_docx(path: Path) -> None:
    """The career sits in a table, which a paragraph-only reader would miss."""
    document = Document()
    document.styles["Normal"].font.name = "Arial"
    document.styles["Normal"].font.size = Pt(10.5)
    document.add_heading(INFRA["name"], level=1)
    document.add_paragraph(INFRA["title"]).runs[0].bold = True
    document.add_paragraph(INFRA["contacts"])
    document.add_heading("О себе", level=2)
    document.add_paragraph(INFRA["summary"])
    document.add_heading("Опыт работы", level=2)
    table = document.add_table(rows=0, cols=2)
    for period, description in INFRA["rows"]:
        cells = table.add_row().cells
        cells[0].text = period
        cells[1].text = description
    document.add_heading("Навыки", level=2)
    document.add_paragraph(INFRA["skills"])
    document.add_heading("Образование", level=2)
    document.add_paragraph(INFRA["education"])
    document.save(str(path))


def make_scan(path: Path) -> None:
    """A page as a picture, slightly grey, the way a phone photo of a printout looks."""
    image = Image.new("L", (1240, 1754), color=244)
    draw = ImageDraw.Draw(image)
    y = 110
    for text, bold, size in SOC:
        font = ImageFont.truetype(str(BOLD if bold else REGULAR), size)
        draw.text((110, y), text, font=font, fill=28)
        y += int(size * 1.75)
    image.save(path, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_pdf(OUT / "ics-security-engineer.pdf")
    make_docx(OUT / "it-infrastructure-lead.docx")
    (OUT / "ml-engineer.md").write_text(ML, encoding="utf-8", newline="\n")
    make_scan(OUT / "soc-analyst-scan.png")
    for file in sorted(OUT.iterdir()):
        print(f"{file.name}  {file.stat().st_size} bytes")


if __name__ == "__main__":
    main()
