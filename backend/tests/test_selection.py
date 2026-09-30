"""The rules that decide what a reader sees."""

import numpy as np
import pytest

from radar.ai.embedder import HashingEmbedder, fit_dimension
from radar.domain import Candidate, Grade, ProfileSpec
from radar.selection.clustering import cluster_items
from radar.selection.retrieval import exclusion_query, keyword_query
from radar.selection.scoring import (
    NO_KEYWORD_CEILING,
    REJECT_DUPLICATE,
    REJECT_EXCLUDED,
    REJECT_LOW_SCORE,
    REJECT_OVER_LIMIT,
    final_score,
    lexical_score,
    rank_candidates,
    retrieval_score,
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
