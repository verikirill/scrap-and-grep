"""scripts/make_examples.py: an example issue is saved with its own JSON.

The committed examples go stale when a rule of the digest changes. With the
issue's JSON beside its Markdown and DOCX, it can be rendered again and
checked without the model that wrote it."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from radar.render.markdown import render_markdown
from radar.views import DigestView

ROOT = Path(__file__).resolve().parents[2]
# What GET /digests/{id} returned for a real issue of the example week.
DIGEST = ROOT / "docs" / "eval" / "human" / "ics-security-engineer.digest.json"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "make_examples", ROOT / "scripts" / "make_examples.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


examples = _script()


def test_an_example_issue_can_be_rendered_again_from_the_json_saved_beside_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = json.loads(DIGEST.read_text(encoding="utf-8"))

    def stand(request: httpx.Request) -> httpx.Response:
        # The API renders its exports from the same view it returns as JSON.
        if request.url.path.endswith("/export.md"):
            return httpx.Response(200, text=render_markdown(DigestView.model_validate(digest)))
        return httpx.Response(200, content=b"PK\x03\x04")

    monkeypatch.setattr(examples, "API", "http://stand/api/v1")
    stem = tmp_path / "ics-security-engineer"
    with httpx.Client(transport=httpx.MockTransport(stand)) as client:
        examples.export(client, digest, stem)

    saved = DigestView.model_validate_json(stem.with_suffix(".json").read_bytes())
    assert render_markdown(saved) == stem.with_suffix(".md").read_text(encoding="utf-8")
