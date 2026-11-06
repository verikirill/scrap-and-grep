"""Grade a saved digest's candidates again on the model the environment names.

The expert graded the 60 candidates of a saved digest (docs/eval/second-human).
To compare models on that grading, every model has to judge the same 60
articles: retrieval is taken from the saved digest, only the grade is new.
Selection then follows the digest's own rules: the final score blends the
grade with retrieval and the interest weight, the profile's threshold and size
cap apply, and a story the digest merged stays merged into the same entry.

    docker cp docs/eval/human/ics-security-engineer.digest.json radar-api-1:/tmp/digest.json
    docker exec -i -e RADAR_LLM_MODEL=gpt://<folder>/aliceai-llm/latest radar-api-1 \
        python - /tmp/digest.json < backend/scripts/regrade.py > tmp/regrade/alice-ics.json
    uv run scripts/eval_selection.py score tmp/regrade/alice-ics.json \
        docs/eval/second-human/ics-security-engineer.csv

RADAR_LLM_PROVIDER=heuristic grades without a model. The output is a digest in
the shape eval_selection.py reads, with the model's name in `llm`.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from radar.ai.factory import get_intelligence
from radar.db import session_scope
from radar.db.models import Article
from radar.domain import Candidate, ProfileSpec
from radar.selection.scoring import final_score
from radar.store.articles import get_refs

DUPLICATE = "duplicate"


async def main(path: str) -> None:
    digest = json.loads(Path(path).read_text(encoding="utf-8"))
    profile = ProfileSpec.model_validate(digest["profile"])
    chosen = [item for topic in digest["topics"] for item in topic["items"]]
    rows = chosen + digest["rejected"]
    # A merged copy is judged with its story, not on its own.
    merged = {copy["url"] for item in chosen for copy in item.get("duplicates") or []}
    async with session_scope() as session:
        ids = dict(
            (
                await session.execute(
                    select(Article.url, Article.id).where(Article.url.in_([r["url"] for r in rows]))
                )
            ).all()
        )
        refs = await get_refs(session, list(ids.values()))
    intelligence = get_intelligence()

    async def judge(row: dict[str, Any]) -> dict[str, Any]:
        candidate = Candidate(
            article=refs[ids[row["url"]]],
            interest_id=row["interest_id"],
            retrieval_score=row["retrieval_score"],
        )
        grade = await intelligence.grade(candidate, profile)
        interest = profile.interest(grade.interest_id or candidate.interest_id)
        score = final_score(candidate, grade, interest.weight if interest else 1.0)
        return {
            **row,
            "relevance": grade.relevance,
            "interest_id": grade.interest_id,
            "reason": grade.reason,
            "kind": grade.kind,
            "by_model": grade.by_model,
            "score": round(score, 4),
            # The priority comes from the card, which this run does not write.
            "priority": None,
        }

    started = datetime.now()
    judged = await asyncio.gather(*(judge(row) for row in rows if row["url"] in ids))
    eligible = sorted(
        (
            row
            for row in judged
            if row["url"] not in merged
            and row.get("reject_reason") not in {DUPLICATE, "excluded", "hidden"}
            and row["score"] >= profile.min_score
        ),
        key=lambda row: (-row["score"], row["article_id"]),
    )
    selected = eligible[: profile.max_items]
    picked = {row["url"] for row in selected}
    out = {
        "title": digest.get("title"),
        "profile_name": digest["profile_name"],
        "profile": digest["profile"],
        "llm": getattr(intelligence, "name", type(intelligence).__name__),
        "seconds": round((datetime.now() - started).total_seconds(), 1),
        "by_model": sum(row["by_model"] for row in judged),
        "topics": [{"title": "", "items": selected}],
        "rejected": [row for row in judged if row["url"] not in picked],
    }
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(json.dumps(out, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
