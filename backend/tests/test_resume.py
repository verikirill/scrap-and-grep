"""Resume handling: what is accepted, what is stripped, what is understood."""

import io
import time
import zipfile

import pytest
from docx import Document

from radar.ai.resilient import CircuitBreaker
from radar.resume import files
from radar.resume.extract import (
    Extraction,
    HeuristicResumeExtractor,
    ResilientResumeExtractor,
)
from radar.resume.files import detect_format
from radar.resume.model import ResumeError
from radar.resume.parse import PARSER_BUILTIN, parse_builtin, parse_document
from radar.resume.scrub import scrub

ICS_RESUME = """Иван Петров
Ведущий инженер по защите АСУ ТП
Телефон: +7 (900) 000-00-00
E-mail: ivan.petrov@example.org
Город проживания: Екатеринбург

Опыт работы
2021 - 2026. АО «Энергосеть-Пример», ведущий инженер по защите АСУ ТП.
Категорирование объектов КИИ по 187-ФЗ, приказ ФСТЭК № 239. Мониторинг технологических
сетей подстанций, анализ уязвимостей ПЛК и SCADA, сегментация сетей телемеханики и РЗА.
2017 - 2021. ООО «Промзащита-Пример», инженер по информационной безопасности.
Аудиты АСУ ТП, тестирование на проникновение, проектирование по IEC 62443.

Навыки: SCADA, ПЛК, Modbus, МЭК 61850, MaxPatrol VM, Nessus, Python
"""


def docx_bytes(build: object) -> bytes:
    document = Document()
    build(document)  # type: ignore[operator]
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_format_is_decided_by_content_not_by_the_file_name() -> None:
    docx = docx_bytes(lambda document: document.add_paragraph("Резюме"))

    assert detect_format(b"%PDF-1.7 ...", "resume.docx") == "pdf"
    assert detect_format(docx, "resume.pdf") == "docx"
    assert detect_format("# Резюме\nИнженер".encode(), "cv.md") == "md"
    assert detect_format("Резюме инженера".encode("cp1251"), "cv.txt") == "txt"


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"MZ\x90\x00" + b"\x00" * 64,  # a Windows executable named like a document
        b"\xd0\xcf\x11\xe0" + b"\x00" * 64,  # legacy .doc
        b"PK\x03\x04 not really a zip",
    ],
)
def test_files_that_are_not_documents_are_refused(data: bytes) -> None:
    with pytest.raises(ResumeError):
        detect_format(data, "resume.pdf")


def test_an_archive_that_unpacks_to_too_much_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * 200_000)
    # 200 KB of zeros packs into a few hundred bytes: the size on disk says
    # nothing, the declared unpacked size is what is checked.
    assert len(buffer.getvalue()) < 2_000
    monkeypatch.setattr(files, "_ZIP_MAX_UNPACKED", 100_000)

    with pytest.raises(ResumeError, match="распакованном"):
        detect_format(buffer.getvalue(), "resume.docx")


def test_scrub_removes_contacts_and_the_name_but_keeps_the_career() -> None:
    cleaned = scrub(ICS_RESUME + "\nTelegram: @ivan_petrov, https://t.me/ivan_petrov\n")

    for secret in ("Петров", "900", "example.org", "Екатеринбург", "ivan_petrov"):
        assert secret not in cleaned
    # Year ranges look like phone numbers, law numbers contain digits: both stay.
    for kept in ("2021 - 2026", "187-ФЗ", "№ 239", "IEC 62443", "Ведущий инженер"):
        assert kept in cleaned


async def test_offline_extractor_recognises_the_field_and_the_skills() -> None:
    result = await HeuristicResumeExtractor().extract(scrub(ICS_RESUME))

    assert result.facts.headline == "Ведущий инженер по защите АСУ ТП"
    assert result.facts.seniority == "senior"
    assert not result.facts.by_model
    assert {"SCADA", "ПЛК", "МЭК 61850", "187-ФЗ"} <= set(result.facts.skills)
    interests = [interest.id for interest in result.suggestion.interests]
    assert interests[0] == "ics-security"
    assert "kii-regulation" in interests
    assert result.suggestion.interests[0].weight > result.suggestion.interests[1].weight
    # Nothing personal is carried into the profile.
    assert "Петров" not in result.suggestion.model_dump_json()


async def test_a_resume_from_another_trade_gets_general_topics_not_an_error() -> None:
    text = "Повар горячего цеха. " + "Готовлю супы, соусы и вторые блюда для банкетов. " * 8

    result = await HeuristicResumeExtractor().extract(text)

    assert result.facts.domains == ()
    assert len(result.suggestion.interests) >= 1


async def test_too_little_text_is_reported_to_the_reader() -> None:
    with pytest.raises(ResumeError, match="мало текста"):
        await HeuristicResumeExtractor().extract("Инженер")


async def test_builtin_parser_reads_text_inside_docx_tables() -> None:
    def build(document: object) -> None:
        document.add_paragraph("Опыт работы")  # type: ignore[attr-defined]
        cells = document.add_table(rows=1, cols=2).rows[0].cells  # type: ignore[attr-defined]
        cells[0].text = "2019 - 2026"
        cells[1].text = "Администрирование Linux и VMware"

    parsed = await parse_builtin(docx_bytes(build), "docx", max_pages=5)

    assert "Администрирование Linux и VMware" in parsed.text
    assert "2019 - 2026" in parsed.text


async def test_parsing_falls_back_to_the_builtin_parser_when_docling_is_down() -> None:
    # Nothing listens on this port: the connection is refused at once.
    parsed = await parse_document(
        "Инженер по сетям".encode(),
        "txt",
        docparser_url="http://127.0.0.1:9",
        request_timeout=2.0,
        max_pages=5,
    )

    assert parsed.parser == PARSER_BUILTIN
    assert parsed.text == "Инженер по сетям"


class _FailingExtractor:
    name = "model"

    def __init__(self, error: Exception) -> None:
        self.calls = 0
        self._error = error

    async def extract(self, text: str) -> Extraction:
        self.calls += 1
        raise self._error


async def test_extraction_falls_back_to_the_taxonomy_when_the_model_fails() -> None:
    primary = _FailingExtractor(TimeoutError())
    extractor = ResilientResumeExtractor(
        primary, HeuristicResumeExtractor(), CircuitBreaker(failure_threshold=1)
    )

    first = await extractor.extract(scrub(ICS_RESUME))
    await extractor.extract(scrub(ICS_RESUME))

    assert not first.facts.by_model
    # The breaker opened after the first failure; the model was not asked again.
    assert primary.calls == 1


async def test_a_verdict_about_the_file_is_not_retried_with_another_extractor() -> None:
    primary = _FailingExtractor(ResumeError("В файле слишком мало текста."))
    extractor = ResilientResumeExtractor(primary, HeuristicResumeExtractor(), CircuitBreaker())

    with pytest.raises(ResumeError):
        await extractor.extract(scrub(ICS_RESUME))


@pytest.mark.parametrize("noise", ["\n", " \n\t", "a", "a@", "1 "])
def test_scrub_takes_linear_time_on_hostile_text(noise: str) -> None:
    # 20 000 blank lines took almost a minute with the first version of the
    # patterns (a quadratic regular expression); now a megabyte takes well
    # under a second.
    text = noise * (1_000_000 // len(noise))

    started = time.perf_counter()
    scrub(text)

    assert time.perf_counter() - started < 3.0
