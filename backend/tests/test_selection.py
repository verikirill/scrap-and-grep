"""The rules that decide what a reader sees."""

from datetime import UTC, datetime

import numpy as np
import pytest

from radar.ai.embedder import HashingEmbedder, fit_dimension
from radar.domain import (
    Candidate,
    DuplicateRef,
    Grade,
    GradedCandidate,
    ItemSummary,
    ProfileSpec,
    SelectedItem,
    VulnerabilityCard,
    VulnerabilityReference,
)
from radar.selection.clustering import cluster_items
from radar.selection.retrieval import _excluded_by, exclusion_query, keyword_query
from radar.selection.scoring import (
    NO_KEYWORD_CEILING,
    REJECT_DUPLICATE,
    REJECT_EXCLUDED,
    REJECT_LOW_SCORE,
    REJECT_OVER_LIMIT,
    final_score,
    lexical_score,
    mentions,
    merge_written,
    rank_candidates,
    retrieval_score,
    same_vulnerability,
    select,
)
from tests.conftest import ArticleFactory, GradedFactory


def _cosine(a: list[float], b: list[float]) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def test_hashing_embedder_ranks_inflected_forms_above_unrelated_text() -> None:
    embedder = HashingEmbedder()

    query, inflected, unrelated = await embedder.embed(
        [
            "уязвимость промышленных контроллеров",
            "в промышленном контроллере найдены уязвимости",
            "квартальная отчётность банков выросла",
        ],
        "document",
    )

    assert _cosine(query, inflected) > _cosine(query, unrelated) + 0.2


def test_padding_a_short_vector_keeps_cosine_similarity() -> None:
    a, b = [0.6, 0.8, 0.0], [0.0, 0.6, 0.8]

    padded = _cosine(fit_dimension(a, 8), fit_dimension(b, 8))

    assert padded == pytest.approx(_cosine(a, b))


def test_truncating_a_long_vector_renormalises_it() -> None:
    truncated = fit_dimension([3.0, 4.0, 12.0, 5.0], 2)

    assert np.linalg.norm(truncated) == pytest.approx(1.0)
    assert truncated == pytest.approx([0.6, 0.8])


def test_keyword_query_quotes_phrases_and_joins_with_or() -> None:
    assert keyword_query(("АСУ ТП", "SCADA", "zero-day", "  ")) == '"асу тп" OR scada OR "zero day"'


def test_exclusion_query_requires_every_meaningful_word() -> None:
    # websearch syntax: words separated by spaces are ANDed; "и" is dropped.
    assert exclusion_query("Вакансии и карьера") == "вакансии карьера"


def test_exclusion_by_words_is_decisive_by_meaning_only_when_closer_than_the_interest() -> None:
    assert _excluded_by(("вакансии", 0.5, True), interest_z=4.0) == "вакансии"
    assert _excluded_by(("вакансии", 3.6, False), interest_z=4.0) is None
    assert _excluded_by(("вакансии", 4.2, False), interest_z=4.0) == "вакансии"
    assert _excluded_by(None, interest_z=1.0) is None


def test_semantic_score_grows_with_z_score_and_keyword_hit() -> None:
    assert retrieval_score(0.0, False) < retrieval_score(2.0, False) < retrieval_score(2.0, True)
    assert retrieval_score(10.0, True) == 1.0


def test_without_a_keyword_a_spelling_only_match_stays_below_threshold() -> None:
    assert lexical_score(0.0, z_score=9.0, lexical_hit=False) <= NO_KEYWORD_CEILING
    assert lexical_score(0.0, z_score=0.0, lexical_hit=True) >= 0.5


def test_model_verdict_outweighs_retrieval_evidence(make_article: ArticleFactory) -> None:
    candidate = Candidate(article=make_article("x"), interest_id="ics", retrieval_score=0.9)

    rejected_by_model = final_score(candidate, Grade(relevance=0, by_model=True), weight=1.0)
    approved_by_model = final_score(candidate, Grade(relevance=3, by_model=True), weight=1.0)
    heuristic = final_score(candidate, Grade(relevance=3, by_model=False), weight=1.0)

    assert rejected_by_model < 0.5 < approved_by_model
    assert heuristic == pytest.approx(0.9)


def test_interest_weight_scales_the_score_but_never_past_one(make_article: ArticleFactory) -> None:
    candidate = Candidate(article=make_article("x"), interest_id="ics", retrieval_score=0.8)
    grade = Grade(relevance=2, by_model=False)

    assert final_score(candidate, grade, weight=0.5) == pytest.approx(0.4)
    assert final_score(candidate, grade, weight=1.5) == 1.0


def test_article_matching_two_interests_is_kept_once_with_its_best_match(
    make_article: ArticleFactory,
) -> None:
    article = make_article("Уязвимость в SCADA")
    weak = Candidate(article=article, interest_id="vuln", retrieval_score=0.6)
    strong = Candidate(article=article, interest_id="ics", retrieval_score=0.9)

    ranked = rank_candidates([weak, strong], limit=10)

    assert [candidate.interest_id for candidate in ranked] == ["ics"]


def test_select_applies_exclusion_threshold_duplicates_and_limit(
    profile: ProfileSpec, make_graded: GradedFactory
) -> None:
    best = make_graded("Атака на подстанцию через SCADA", 0.95, source="A")
    retelling = make_graded("Атака на подстанцию через SCADA: подробности", 0.80, source="B")
    excluded = make_graded("Вакансия инженера SCADA", 0.90, excluded_by="вакансии")
    weak = make_graded("Обзор рынка мониторов", 0.20)
    unrelated = [
        "Шифровальщик остановил завод",
        "Вышел патч для Chrome",
        "Фишинговая рассылка от имени банка",
        "Утечка данных клиентов ритейлера",
        "Ботнет из роутеров вырос вдвое",
    ]
    others = [make_graded(title, 0.7 - n / 100) for n, title in enumerate(unrelated)]

    selected, rejected = select(
        [best, retelling, excluded, weak, *others], profile, vectors={}, duplicate_threshold=0.9
    )

    assert len(selected) == profile.max_items
    assert selected[0].article.id == best.article.id
    assert [dup.source_name for dup in selected[0].duplicates] == ["B"]
    assert rejected[retelling.article.id] == REJECT_DUPLICATE
    assert rejected[excluded.article.id] == REJECT_EXCLUDED
    assert rejected[weak.article.id] == REJECT_LOW_SCORE
    assert rejected[others[-1].article.id] == REJECT_OVER_LIMIT


def test_near_identical_embeddings_are_merged_even_with_different_titles(
    profile: ProfileSpec, make_graded: GradedFactory
) -> None:
    original = make_graded("Siemens закрыла брешь в контроллерах", 0.9)
    translation = make_graded("Siemens patches PLC flaw", 0.8)
    vectors = {
        original.article.id: np.array([1.0, 0.0], dtype=np.float32),
        translation.article.id: np.array([0.98, 0.199], dtype=np.float32),
    }

    selected, rejected = select([original, translation], profile, vectors, duplicate_threshold=0.9)

    assert [item.article.id for item in selected] == [original.article.id]
    assert rejected == {translation.article.id: REJECT_DUPLICATE}


def test_clustering_separates_topics_and_puts_the_strongest_first(
    profile: ProfileSpec, make_graded: GradedFactory
) -> None:
    rng = np.random.default_rng(7)
    centers = {"ics": np.array([1.0, 0.0, 0.0]), "vuln": np.array([0.0, 1.0, 0.0])}
    graded = [
        make_graded(
            f"Новость {topic} {n}",
            0.6 + (0.3 if topic == "vuln" and n == 0 else 0.0),
            interest_id=topic,
        )
        for topic in centers
        for n in range(4)
    ]
    selected, _ = select(graded, profile.model_copy(update={"max_items": 20}), {}, 0.99)
    vectors = {}
    for item in selected:
        noisy = centers[item.graded.interest_id] + rng.normal(0, 0.05, 3)
        vectors[item.article.id] = (noisy / np.linalg.norm(noisy)).astype(np.float32)

    groups = cluster_items(selected, vectors)

    assert [len(group) for group in groups] == [4, 4]
    assert {item.graded.interest_id for item in groups[0]} == {"vuln"}
    assert groups[0][0].graded.score == pytest.approx(0.9)


def test_one_broad_theme_with_outliers_is_still_split_into_readable_topics(
    profile: ProfileSpec, make_graded: GradedFactory
) -> None:
    # The shape real digests have: three neighbouring sub-themes and two
    # unrelated articles. A split into "18 and 2" is what must not happen.
    rng = np.random.default_rng(11)
    subthemes = [np.array([1.0, 0.45, 0.0, 0.0]), np.array([1.0, 0.0, 0.45, 0.0]),
                 np.array([1.0, -0.45, -0.45, 0.0])]  # fmt: skip
    outlier = np.array([0.0, 0.0, 0.0, 1.0])
    centers = [center for center in subthemes for _ in range(6)] + [outlier, outlier]
    graded = [make_graded(f"Публикация {chr(1040 + n) * (n + 3)}", 0.7) for n in range(20)]
    selected, _ = select(graded, profile.model_copy(update={"max_items": 20}), {}, 0.99)
    vectors = {}
    for item, center in zip(selected, centers, strict=True):
        noisy = center + rng.normal(0, 0.03, 4)
        vectors[item.article.id] = (noisy / np.linalg.norm(noisy)).astype(np.float32)

    groups = cluster_items(selected, vectors)

    assert sorted(len(group) for group in groups) == [2, 6, 6, 6]


def test_spelling_only_vectors_are_not_clustered_but_grouped_by_interest(
    profile: ProfileSpec, make_graded: GradedFactory
) -> None:
    graded = [
        make_graded(f"Новость {n}", 0.7, interest_id="ics" if n % 2 else "vuln") for n in range(6)
    ]
    selected, _ = select(graded, profile.model_copy(update={"max_items": 20}), {}, 0.99)
    same_vector = {item.article.id: np.array([1.0, 0.0], dtype=np.float32) for item in selected}

    groups = cluster_items(selected, same_vector, semantic=False)

    assert sorted(len(group) for group in groups) == [3, 3]
    assert all(len({item.graded.interest_id for item in group}) == 1 for group in groups)


def _graded(
    make_article: ArticleFactory, title: str, summary: str, score: float
) -> GradedCandidate:
    candidate = Candidate(
        article=make_article(title, summary), interest_id="ics", retrieval_score=score
    )
    return GradedCandidate(
        candidate=candidate, grade=Grade(relevance=2, interest_id="ics"), score=score
    )


def test_retellings_of_one_cve_in_two_languages_are_one_entry(
    profile: ProfileSpec, make_article: ArticleFactory
) -> None:
    """From the snapshot of October 3: one FortiMail zero-day from BleepingComputer
    and from 1275; the headlines share no words and the vectors are not given."""
    english = _graded(
        make_article,
        "Fortinet warns of critical FortiMail flaw exploited in zero-day attacks",
        "Fortinet patched CVE-2026-104286, a path traversal in FortiMail.",
        0.9,
    )
    russian = _graded(
        make_article,
        "CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в FortiMail",
        "Уязвимость CVE-2026-104286 позволяет записывать файлы без аутентификации.",
        0.8,
    )
    other = _graded(
        make_article,
        "Cisco закрыла zero-day в Catalyst SD-WAN Manager",
        "CVE-2026-76504 используется в атаках.",
        0.7,
    )

    selected, rejected = select(
        [english, russian, other], profile, vectors={}, duplicate_threshold=0.9
    )

    assert [item.article.id for item in selected] == [english.article.id, other.article.id]
    assert rejected == {russian.article.id: REJECT_DUPLICATE}


def test_a_roundup_joins_a_story_only_when_it_names_all_its_ids_and_its_name() -> None:
    story = mentions(
        "Kiteworks EPG получил 10 из 10 по CVSS", "Kiteworks раскрыла CVE-2026-54154.", None
    )
    roundup_ids = " ".join(f"CVE-2026-1021{n}" for n in range(7))
    roundup = mentions(
        "Более сотни уязвимостей в четырёх продуктах Kiteworks",
        f"CVE-2026-54154 {roundup_ids}",
        None,
    )
    weekly = mentions("Трендовые уязвимости недели", f"CVE-2026-54154 {roundup_ids}", None)
    huge = mentions(
        "Kiteworks и ещё сорок вендоров",
        "CVE-2026-54154 " + " ".join(f"CVE-2026-3{n:04d}" for n in range(30)),
        None,
    )

    assert same_vulnerability(story, roundup)
    # The same ids without the product's name: a weekly roundup is not the story.
    assert not same_vulnerability(story, weekly)
    assert not same_vulnerability(story, huge)


def test_names_leave_the_ids_out_and_come_from_the_text_when_the_title_has_none() -> None:
    printed = mentions("CVE-2026-88772 в Citrix NetScaler", "", None)
    untitled = mentions("Ирония судьбы", "DIVD взломали через Zammad: CVE-2026-102489.", None)

    assert printed.names == {"citrix", "netscaler"}
    assert printed.ids == {"CVE-2026-88772"}
    assert untitled.names == {"divd", "zammad"}


def _written(
    make_article: ArticleFactory,
    title: str,
    score: float,
    ids: tuple[str, ...],
    references: tuple[VulnerabilityReference, ...] = (),
) -> SelectedItem:
    graded = _graded(make_article, title, "", score)
    return SelectedItem(
        graded=graded.model_copy(
            update={"grade": graded.grade.model_copy(update={"kind": "vulnerability"})}
        ),
        text=ItemSummary(
            summary="",
            vulnerability=VulnerabilityCard(ids=ids),
            references=references,
        ),
    )


def test_entries_the_bases_tie_to_one_vulnerability_become_one_after_the_cards(
    make_article: ArticleFactory,
) -> None:
    """A Russian post names only BDU:2026-15790, an English one only
    CVE-2026-104286: selection cannot tie them, the BDU entry of the CVE can."""
    english = _written(
        make_article,
        "Fortinet warns of critical FortiMail flaw",
        0.9,
        ("CVE-2026-104286",),
        (VulnerabilityReference(id="CVE-2026-104286", bdu_id="BDU:2026-15790"),),
    )
    russian = _written(make_article, "Уязвимость графического интерфейса", 0.7, ("BDU:2026-15790",))
    other = _written(make_article, "Cisco SD-WAN Manager", 0.8, ("CVE-2026-76504",))

    merged, absorbed = merge_written([russian, other, english])

    assert [item.article.id for item in merged] == [other.article.id, english.article.id]
    assert [dup.url for dup in merged[1].duplicates] == [russian.article.url]
    assert absorbed == [russian]


def test_the_bdu_ids_of_a_card_do_not_make_it_a_roundup(
    make_article: ArticleFactory,
) -> None:
    """Rapid7 on three Citrix CVEs, each with its BDU id from the bases, and a
    SecAtor post on one of them whose title names other products: the card is
    about three vulnerabilities, not six, and the post is its retelling."""
    citrix = ("CVE-2026-88771", "CVE-2026-88772", "CVE-2026-88779")
    rapid7 = _written(
        make_article,
        "Zero-Day Exploitation of Citrix NetScaler ADC and Gateway",
        0.72,
        citrix,
        tuple(
            VulnerabilityReference(id=cve, bdu_id=f"BDU:2026-1549{index}")
            for index, cve in enumerate(citrix)
        ),
    )
    secator = _written(
        make_article,
        "В продолжение к предыдущему: Mandiant приводит подробности",
        0.70,
        ("CVE-2026-88772",),
        (VulnerabilityReference(id="CVE-2026-88772", bdu_id="BDU:2026-15491"),),
    )

    merged, absorbed = merge_written([rapid7, secator])

    assert [item.article.id for item in merged] == [rapid7.article.id]
    assert absorbed == [secator]


def test_entries_without_ids_are_never_merged_after_the_cards(
    make_article: ArticleFactory,
) -> None:
    first = _written(make_article, "Citrix NetScaler: две 0-day", 0.9, ())
    second = _written(make_article, "Citrix NetScaler ADC и Gateway", 0.8, ())

    merged, absorbed = merge_written([first, second])

    assert merged == [first, second]
    assert absorbed == []


def test_a_retelling_merged_after_the_cards_brings_its_own_retellings_along(
    make_article: ArticleFactory,
) -> None:
    kept = _written(make_article, "FortiMail CVE-2026-104286", 0.9, ("CVE-2026-104286",))
    twin = _written(make_article, "FortiMail ещё раз", 0.7, ("CVE-2026-104286",))
    twin = twin.model_copy(
        update={
            "duplicates": (
                DuplicateRef(title="Пересказ", url="https://example.org/r", source_name="1275"),
            )
        }
    )

    [merged], _ = merge_written([kept, twin])

    assert [dup.url for dup in merged.duplicates] == [twin.article.url, "https://example.org/r"]


def _exploited(
    make_article: ArticleFactory,
    name: str,
    score: float,
    ids: tuple[str, ...],
    day: int,
    exploit: str = "in_the_wild",
) -> SelectedItem:
    item = _written(make_article, name, score, ids)
    article = item.graded.candidate.article.model_copy(
        update={"published_at": datetime(2026, 9, day, 8, 0, tzinfo=UTC)}
    )
    graded = item.graded.model_copy(
        update={"candidate": item.graded.candidate.model_copy(update={"article": article})}
    )
    card = VulnerabilityCard(name=name, ids=ids, exploit=exploit)  # type: ignore[arg-type]
    return item.model_copy(
        update={"graded": graded, "text": ItemSummary(summary="", vulnerability=card)}
    )


def test_an_exploited_zero_day_retold_without_ids_joins_the_entry_that_has_them(
    make_article: ArticleFactory,
) -> None:
    """examples/vs-analyst/assistant-ics-security-engineer.md:117 and :196:
    SecAtor names CVE-2026-88771 and CVE-2026-88772, The Hacker News in the
    snapshot names none."""
    secator = _exploited(
        make_article,
        "уязвимость в Citrix NetScaler",
        0.73,
        ("CVE-2026-88771", "CVE-2026-88772"),
        day=30,
    )
    hacker_news = _exploited(
        make_article, "уязвимость в Citrix NetScaler ADC и NetScaler Gateway", 0.71, (), day=27
    )

    merged, absorbed = merge_written([secator, hacker_news])

    assert [item.article.id for item in merged] == [secator.article.id]
    assert absorbed == [hacker_news]


@pytest.mark.parametrize(
    ("other_name", "other_ids", "day", "exploit"),
    [
        # Two zero-days of one product, each with its own ids: the ids decide.
        ("уязвимость в Citrix NetScaler", ("CVE-2026-90001",), 29, "in_the_wild"),
        # Not exploited: a product name alone is no story.
        ("уязвимость в Citrix NetScaler", (), 29, "unknown"),
        # More than a week apart.
        ("уязвимость в Citrix NetScaler", (), 20, "in_the_wild"),
        # One shared name is not enough, and a platform is no product.
        ("уязвимость в Citrix ShareFile", (), 29, "in_the_wild"),
    ],
)
def test_a_product_name_merges_only_an_exploited_retelling_without_ids_within_a_week(
    make_article: ArticleFactory,
    other_name: str,
    other_ids: tuple[str, ...],
    day: int,
    exploit: str,
) -> None:
    secator = _exploited(
        make_article, "уязвимость в Citrix NetScaler", 0.73, ("CVE-2026-88771",), day=30
    )
    other = _exploited(make_article, other_name, 0.7, other_ids, day=day, exploit=exploit)

    _, absorbed = merge_written([secator, other])

    assert absorbed == []


def test_two_zero_days_of_a_broad_platform_without_ids_stay_apart(
    make_article: ArticleFactory,
) -> None:
    first = _exploited(make_article, "уязвимость в Microsoft Windows", 0.9, (), day=29)
    second = _exploited(make_article, "уязвимость в Microsoft Windows", 0.8, (), day=30)

    _, absorbed = merge_written([first, second])

    assert absorbed == []
