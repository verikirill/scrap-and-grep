"""The reader: an article's page as blocks the app draws itself."""

from pathlib import Path

import trafilatura
from lxml import etree

from radar.reader.blocks import from_text, from_tree, image_id

FIXTURES = Path(__file__).parent / "fixtures" / "reader"
PAGE = (FIXTURES / "article.html").read_text(encoding="utf-8")
URL = "https://news.example/story"
TITLE = "Атака на подстанцию: как это было"
LEAD = "https://news.example/pics/lead.jpg"


def tree(page: str) -> etree._Element:
    document = trafilatura.bare_extraction(
        page,
        url=URL,
        include_comments=False,
        include_tables=True,
        include_images=True,
        include_formatting=True,
        include_links=True,
    )
    return document.body


def test_a_page_becomes_blocks_without_its_markup() -> None:
    body = from_tree(tree(PAGE), title=TITLE, lead=LEAD)

    # The headline is shown above the text, the empty "Содержание" heading
    # is dropped, and the page's logo is not the story's picture.
    assert [block["type"] for block in body.blocks] == [
        "image",
        "p",
        "p",
        "h",
        "list",
        "quote",
        "p",
        "code",
        "table",
        "p",
    ]
    scheme = "https://news.example/pics/scheme.png"
    assert body.blocks[0] == {
        "type": "image",
        "id": image_id(scheme),
        "alt": "Схема сети подстанции с точкой входа злоумышленника",
    }
    # Only the addresses found in the article may be fetched for it.
    assert body.images == {image_id(scheme): scheme}
    assert body.blocks[1]["spans"] == [
        {"text": "Злоумышленники проникли в сеть "},
        {"text": "подстанции 110 кВ", "b": True},
        {"text": " через VPN-шлюз подрядчика. Подробности - в "},
        {"text": "бюллетене CERT", "href": "https://cert.example/advisory/42"},
        # A javascript: link is left as words.
        {"text": ", а эта ссылка никуда не ведёт."},
    ]
    assert {"text": "legacy_auth", "code": True} in body.blocks[2]["spans"]
    assert body.blocks[3] == {"type": "h", "level": 2, "text": "Что сделали атакующие"}
    assert body.blocks[4]["ordered"] is True
    assert len(body.blocks[4]["items"]) == 3
    assert body.blocks[7] == {"type": "code", "text": "set legacy_auth off\ncommit"}
    assert body.blocks[8] == {
        "type": "table",
        "head": ["Версия", "Исправлена"],
        "rows": [["4.2", "4.2.7"], ["5.0", "5.0.3"]],
    }


def test_the_feeds_picture_leads_only_a_text_that_opens_without_one() -> None:
    without_pictures = PAGE.replace('<img src="/pics/scheme.png"', '<img src=""')

    body = from_tree(tree(without_pictures), title=TITLE, lead=LEAD)

    assert body.blocks[0] == {"type": "image", "id": image_id(LEAD)}
    assert body.images == {image_id(LEAD): LEAD}


def test_a_listing_with_its_line_numbers_is_read_as_code() -> None:
    listing = etree.fromstring(
        "<body><p>Фрагмент журнала с событием входа администратора в консоль кластера:</p>"
        "<table><row><cell><p>1</p></cell><cell><p>45:32.97-0,ADMIN,3,Func=regAuthenticate</p></cell></row>"
        "<row><cell><p>2</p></cell><cell><p>45:33.01-0,CONN,2,client=10.0.0.5</p></cell></row>"
        "</table></body>"
    )

    body = from_tree(listing, title=TITLE, lead=None)

    assert body.blocks[1] == {
        "type": "code",
        "text": "45:32.97-0,ADMIN,3,Func=regAuthenticate\n45:33.01-0,CONN,2,client=10.0.0.5",
    }


def test_plain_text_keeps_its_links_and_the_names_of_its_fields() -> None:
    text = (
        "Уязвимость модуля авторизации позволяет войти без пароля.\n"
        "Уязвимое ПО: Шлюз 4.2 (https://vendor.example/gw), Шлюз 5.0.\n"
        "Подробнее: https://bdu.example/vul/2026-1."
    )

    body = from_text(text, title="Уязвимость шлюза", lead=None, labelled=True)

    assert [block["spans"] for block in body.blocks] == [
        [{"text": "Уязвимость модуля авторизации позволяет войти без пароля."}],
        [
            {"text": "Уязвимое ПО:", "b": True},
            {"text": " Шлюз 4.2 ("},
            {"text": "https://vendor.example/gw", "href": "https://vendor.example/gw"},
            {"text": "), Шлюз 5.0."},
        ],
        [
            {"text": "Подробнее:", "b": True},
            {"text": " "},
            {"text": "https://bdu.example/vul/2026-1", "href": "https://bdu.example/vul/2026-1"},
            {"text": "."},
        ],
    ]


def test_a_table_inside_a_list_item_follows_the_list() -> None:
    page = etree.fromstring(
        "<body><p>Затронуты версии шлюза, перечисленные ниже, и их сборки для АСУ ТП.</p>"
        "<list rend='ul'><item>Шлюз 4.2"
        "<table><row><cell role='head'>Сборка</cell><cell role='head'>Исправлена</cell></row>"
        "<row><cell>4.2.1</cell><cell>4.2.7</cell></row></table></item>"
        "<item>Шлюз 5.0</item></list></body>"
    )

    body = from_tree(page, title=TITLE, lead=None)

    assert [block["type"] for block in body.blocks] == ["p", "list", "table"]
    assert body.blocks[1]["items"] == [[{"text": "Шлюз 4.2"}], [{"text": "Шлюз 5.0"}]]
    assert body.blocks[2]["rows"] == [["4.2.1", "4.2.7"]]


def test_an_address_keeps_the_bracket_it_opened() -> None:
    body = from_text(
        "Протокол: https://en.wikipedia.org/wiki/Modbus_(protocol) (раздел о безопасности).",
        title=TITLE,
        lead=None,
    )

    links = [span["href"] for span in body.blocks[0]["spans"] if "href" in span]
    assert links == ["https://en.wikipedia.org/wiki/Modbus_(protocol)"]
