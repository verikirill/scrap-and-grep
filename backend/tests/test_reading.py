"""Reading time: from the full text only, rounded up, by the language's pace."""

from radar.reading import MIN_WORDS, reading_minutes, word_count


def test_a_teaser_has_no_reading_time() -> None:
    teaser = "Siemens закрыла уязвимость в контроллерах SIMATIC S7-1500."

    assert word_count(teaser) is None
    assert reading_minutes(word_count(teaser), "ru") is None


def test_minutes_are_rounded_up_at_the_pace_of_the_language() -> None:
    article = " ".join(["слово"] * 400)

    words = word_count(article)

    assert words == 400
    # 400 words: 2.2 minutes in Russian at 180 a minute, 1.8 in English at 220.
    assert reading_minutes(words, "ru") == 3
    assert reading_minutes(words, "en") == 2
    assert reading_minutes(MIN_WORDS, "ru") == 1


def test_hyphenated_and_apostrophe_words_count_once() -> None:
    text = "SCADA-система не fail-safe, it's simple. " * 20

    # SCADA-система, не, fail-safe, it's, simple: five words a sentence.
    assert word_count(text) == 100
