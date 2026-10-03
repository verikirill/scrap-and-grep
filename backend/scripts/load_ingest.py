"""Load on ingestion (plan Т6): 200 sources, 30 of them through the browser.

Run from the repository root, with Docker and the images built
(`docker compose build`); the stack under test is a project of its own,
`radar-load`, beside the usual one, and is removed at the end:

    uv run --project backend python backend/scripts/load_ingest.py --tabs 1,2,4

For each number of browser tabs it starts a fresh stack (postgres, valkey,
the ingest worker, the browser) with the sites of scripts/load_farm.py,
replaces the catalog with the farm's sources and polls them all: once from
cold, as on the first day, then `--cycles` times as every 15 minutes after,
the farm's clock moved on by 15 minutes before each. `docker stats` is read
every 2 s meanwhile. The table goes to docs/eval/ingest-load.md, the samples
to out/load/, a file per number of tabs, so they may be run one by one.

The same file runs inside the worker as `seed` and `cycle`: it adds the
sources, then starts `ingest_all` and waits until each source has a poll.
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT = "radar-load"
HERE = Path(__file__).resolve()
# The repository on the host; inside the worker the file sits at /farm alone.
ROOT = HERE.parents[2] if len(HERE.parents) > 2 else HERE.parent
OUT = ROOT / "out" / "load"
REPORT = ROOT / "docs" / "eval" / "ingest-load.md"
SERVICES = ("worker-ingest", "browser", "postgres", "pgbouncer", "valkey", "farm")


# --- inside the worker -------------------------------------------------------


async def seed() -> None:
    import httpx
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import Source

    async with httpx.AsyncClient(trust_env=False) as client:
        found = (await client.get("http://farm/_farm/sources")).json()
    async with session_scope() as session:
        await session.execute(update(Source).values(enabled=False))
        for item in found:
            session.add(
                Source(
                    slug=item["slug"],
                    name=item["name"],
                    kind=item["kind"],
                    feed_url=item["url"],
                    site_url=item["site"],
                    category="security",
                    language="ru",
                    fetch_full_text=item["full_text"],
                )
            )
    print(json.dumps({"sources": len(found)}))


async def cycle(limit: float) -> None:
    """Start ingest_all, wait for a poll of every farm source, say how it went."""
    from sqlalchemy import func, select, text

    from radar.db import session_scope
    from radar.db.models import Article, Source, SourcePoll
    from radar.worker.brokers import ingest_broker
    from radar.worker.tasks import ingest_all

    async with session_scope() as session:
        started = (await session.execute(text("select now()"))).scalar_one()
        farm = {
            row.id: row.kind
            for row in await session.execute(
                select(Source.id, Source.kind).where(Source.slug.like("load-%"))
            )
        }
    await ingest_broker.startup()
    await ingest_all.kiq()
    await ingest_broker.shutdown()
    clock = time.monotonic()
    marks: dict[str, float] = {}
    polled: dict[int, tuple[str, int]] = {}
    while time.monotonic() - clock < limit:
        await asyncio.sleep(2)
        async with session_scope() as session:
            rows = await session.execute(
                select(SourcePoll.source_id, SourcePoll.status, SourcePoll.new_articles).where(
                    SourcePoll.polled_at >= started, SourcePoll.source_id.in_(farm)
                )
            )
            polled = {row.source_id: (row.status, row.new_articles) for row in rows}
        share = len(polled) / len(farm)
        for name, threshold in (("p50", 0.5), ("p90", 0.9), ("all", 1.0)):
            if share >= threshold and name not in marks:
                marks[name] = round(time.monotonic() - clock, 1)
        if share >= 1.0:
            break
    async with session_scope() as session:
        methods = dict(
            (
                await session.execute(
                    select(Source.fetch_method, func.count())
                    .where(Source.id.in_(farm))
                    .group_by(Source.fetch_method)
                )
            ).all()
        )
        stored = (
            await session.execute(
                select(func.count()).where(
                    Article.source_id.in_(farm), Article.fetched_at >= started
                )
            )
        ).scalar_one()
    statuses: dict[str, int] = {}
    for status, _ in polled.values():
        statuses[status] = statuses.get(status, 0) + 1
    print(
        json.dumps(
            {
                "seconds": marks,
                "polled": len(polled),
                "sources": len(farm),
                "statuses": statuses,
                "new_articles": sum(new for _, new in polled.values()),
                "stored": stored,
                "methods": {str(key): value for key, value in methods.items()},
            }
        )
    )


# --- on the host -------------------------------------------------------------


def compose(*args: str, override: Path, capture: bool = False) -> str:
    command = [
        "docker",
        "compose",
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "docker-compose.yml"),
        "-f",
        str(override),
        *args,
    ]
    result = subprocess.run(  # noqa: S603
        command,
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=capture,
    )
    return result.stdout if capture else ""


def write_override(tabs: int, feeds: int, pages: int, scripted: int, memory: str) -> Path:
    hosts = [f"s{index + 1:03d}.farm" for index in range(feeds + pages + scripted)]
    aliases = "".join(f"          - {host}\n" for host in hosts)
    path = OUT / f"compose.tabs{tabs}.yml"
    path.write_text(
        f"""# Written by backend/scripts/load_ingest.py; not for any other use.
services:
  farm:
    image: radar-backend:local
    command: ["uvicorn", "load_farm:app", "--app-dir", "/farm", "--host", "0.0.0.0",
              "--port", "80", "--log-level", "warning"]
    environment:
      FARM_FEEDS: "{feeds}"
      FARM_PAGES: "{pages}"
      FARM_JS: "{scripted}"
    volumes:
      - ./backend/scripts:/farm:ro
    networks:
      default:
        aliases:
          - farm
{aliases}      solving:
        aliases:
          - farm
{aliases}
  worker-ingest:
    environment:
      RADAR_ALLOW_PRIVATE_FEED_HOSTS: "true"
      RADAR_BROWSER_TABS: "{tabs}"
      RADAR_FLARESOLVERR_URL: ""
      RADAR_HTTP_PROXY: ""
      RADAR_HTTP_PROXIES: ""
    volumes:
      - ./backend/scripts:/farm:ro
    depends_on:
      farm:
        condition: service_started
  browser:
    mem_limit: {memory}
    environment:
      BROWSER_TABS: "{tabs}"
      BROWSER_PRIVATE_HOSTS: farm
""",
        encoding="utf-8",
    )
    return path


@dataclass
class Sampler:
    """`docker stats` of the project's containers, every 2 s, in a thread."""

    samples: list[dict[str, Any]] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    label: str = ""

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                output = subprocess.run(
                    ["docker", "stats", "--no-stream", "--format", "{{json .}}"],  # noqa: S607
                    check=True,
                    text=True,
                    capture_output=True,
                    timeout=20,
                ).stdout
            except subprocess.SubprocessError, OSError:
                continue
            moment = time.time()
            for line in output.splitlines():
                row = json.loads(line)
                name = row.get("Name", "")
                if not name.startswith(f"{PROJECT}-"):
                    continue
                service = re.sub(r"-\d+$", "", name[len(PROJECT) + 1 :])
                self.samples.append(
                    {
                        "t": moment,
                        "label": self.label,
                        "service": service,
                        "cpu": float(row["CPUPerc"].rstrip("%") or 0),
                        "mem_mib": _mib(row["MemUsage"].split("/")[0]),
                    }
                )
            self._stop.wait(max(0.0, 2.0 - (time.monotonic() - started)))


def _mib(value: str) -> float:
    number = float(re.sub(r"[^0-9.]", "", value) or 0)
    unit = re.sub(r"[0-9.\s]", "", value).lower()
    factor = {
        "b": 1 / 2**20,
        "kib": 1 / 1024,
        "kb": 1 / 1024,
        "mib": 1.0,
        "mb": 1.0,
        "gib": 1024.0,
        "gb": 1024.0,
    }
    return number * factor.get(unit, 1.0)


def summary(samples: list[dict[str, Any]], label: str) -> dict[str, dict[str, float]]:
    found: dict[str, dict[str, float]] = {}
    for service in SERVICES:
        rows = [s for s in samples if s["label"] == label and s["service"] == service]
        if not rows:
            continue
        cpu = [row["cpu"] for row in rows]
        mem = [row["mem_mib"] for row in rows]
        found[service] = {
            "cpu_mean": sum(cpu) / len(cpu),
            "cpu_peak": max(cpu),
            "mem_mean": sum(mem) / len(mem),
            "mem_peak": max(mem),
        }
    return found


def farm(override: Path, path: str, method: str = "GET") -> Any:
    code = (
        "import json, urllib.request as u;"
        f"r = u.urlopen(u.Request('http://localhost{path}', method='{method}'));"
        "print(r.read().decode())"
    )
    output = compose("exec", "-T", "farm", "python", "-c", code, override=override, capture=True)
    return json.loads(output)


def inside(override: Path, *args: str) -> dict[str, Any]:
    output = compose(
        "exec",
        "-T",
        "worker-ingest",
        "python",
        "/farm/load_ingest.py",
        *args,
        override=override,
        capture=True,
    )
    return dict(json.loads(output.strip().splitlines()[-1]))


def run_one(tabs: int, args: argparse.Namespace) -> dict[str, Any]:
    override = write_override(tabs, args.feeds, args.pages, args.js, args.browser_memory)
    compose("down", "-v", "--remove-orphans", override=override)
    compose("up", "-d", "--wait", *SERVICES, override=override)
    inside(override, "seed")
    sampler = Sampler(label="idle")
    sampler.start()
    time.sleep(20)
    runs: list[dict[str, Any]] = []
    try:
        for number in range(args.cycles + 1):
            label = "cold" if number == 0 else f"warm{number}"
            if number:
                farm(override, "/_farm/tick?minutes=15", "POST")
            before = farm(override, "/_farm/stats")
            sampler.label = label
            print(f"tabs={tabs} {label} ...", flush=True)
            result = inside(override, "cycle", "--limit", str(args.limit))
            sampler.label = f"after-{label}"
            after = farm(override, "/_farm/stats")
            result["label"] = label
            result["requests"] = {
                key: after.get(key, 0) - before.get(key, 0)
                for key in sorted(set(after) | set(before))
                if after.get(key, 0) != before.get(key, 0)
            }
            result["containers"] = summary(sampler.samples, label)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            runs.append(result)
    finally:
        sampler.stop()
        if not args.keep:
            compose("down", "-v", "--remove-orphans", override=override)
    idle = summary(sampler.samples, "idle")
    (OUT / f"samples.tabs{tabs}.json").write_text(json.dumps(sampler.samples), encoding="utf-8")
    return {"tabs": tabs, "idle": idle, "runs": runs}


def host() -> dict[str, Any]:
    info = json.loads(
        subprocess.run(
            ["docker", "info", "--format", "{{json .}}"],  # noqa: S607
            check=True,
            text=True,
            capture_output=True,
        ).stdout
    )
    return {
        "cpus": info.get("NCPU"),
        "memory_gib": round(int(info.get("MemTotal", 0)) / 2**30, 1),
        "os": info.get("OperatingSystem"),
    }


def render(results: list[dict[str, Any]], machine: dict[str, Any], args: argparse.Namespace) -> str:
    total = args.feeds + args.pages + args.js
    lines = [
        "# Нагрузка на сбор (Т6)",
        "",
        f"Замер {datetime.now(UTC):%d.%m.%Y}: `backend/scripts/load_ingest.py`, ферма сайтов "
        f"`backend/scripts/load_farm.py`. {total} источников: {args.feeds} лент RSS "
        f"(половина с полным текстом в ленте, половина - анонс, и статья читается "
        f"со страницы), {args.pages} разделов новостей без ленты, {args.js} сайтов, "
        "которые рисует скрипт (раздел и статьи - только через браузер). Темп публикаций "
        "как у источников снимка 3 октября: 3,4 в сутки на источник в среднем. "
        "Каждый ответ сайта ждёт 50-400 мс, страница со скриптом рисуется 3-6 с.",
        "",
        f"Машина: {machine['cpus']} ядер, {machine['memory_gib']} ГБ памяти Docker "
        f"({machine['os']}). Воркер сбора один, 16 задач одновременно, как в стеке по "
        f"умолчанию; память браузера ограничена {args.browser_memory}.",
        "",
        "«Холодный» опрос - первый после подключения: из каждого раздела берётся до 20 "
        "статей. «Обычный» - каждые 15 минут после: часы фермы сдвигаются на 15 минут, "
        "приходят только новые статьи.",
        "",
        "| Вкладок | Опрос | Все источники опрошены, с | 90%, с | Новых статей "
        "| Страниц через браузер | Воркер: ЦП ср/пик, % | Воркер: память пик, МБ "
        "| Браузер: ЦП ср/пик, % | Браузер: память пик, МБ | Postgres: память пик, МБ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        for run in result["runs"]:
            box = run["containers"]
            worker = box.get("worker-ingest", {})
            browser = box.get("browser", {})
            postgres = box.get("postgres", {})
            renders = sum(
                v
                for k, v in run["requests"].items()
                if k.endswith(":browser") and k.split(":")[0] in {"section", "article"}
            )
            done = run["seconds"].get("all")
            lines.append(
                f"| {result['tabs']} | {'холодный' if run['label'] == 'cold' else 'обычный'} "
                f"| {done if done is not None else f'не все за {args.limit:.0f}'} "
                f"| {run['seconds'].get('p90', '-')} | {run['new_articles']} | {renders} "
                f"| {worker.get('cpu_mean', 0):.0f} / {worker.get('cpu_peak', 0):.0f} "
                f"| {worker.get('mem_peak', 0):.0f} "
                f"| {browser.get('cpu_mean', 0):.0f} / {browser.get('cpu_peak', 0):.0f} "
                f"| {browser.get('mem_peak', 0):.0f} | {postgres.get('mem_peak', 0):.0f} |"
            )
    lines += [
        "",
        "ЦП - в процентах одного ядра, как считает `docker stats`. Покой, до опросов:",
        "",
        "| Вкладок | Воркер, МБ | Браузер, МБ | Postgres, МБ | Valkey, МБ |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        idle = result["idle"]
        lines.append(
            f"| {result['tabs']} | {idle.get('worker-ingest', {}).get('mem_mean', 0):.0f} "
            f"| {idle.get('browser', {}).get('mem_mean', 0):.0f} "
            f"| {idle.get('postgres', {}).get('mem_mean', 0):.0f} "
            f"| {idle.get('valkey', {}).get('mem_mean', 0):.0f} |"
        )
    lines += [
        "",
        "Сырые данные: `out/load/result.tabs*.json`, выборки `docker stats` - "
        "`out/load/samples.tabs*.json`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="run", choices=["run", "seed", "cycle"])
    parser.add_argument("--tabs", default="2", help="browser tabs to try, comma-separated")
    parser.add_argument("--cycles", type=int, default=3, help="polls after the cold one")
    parser.add_argument("--feeds", type=int, default=140)
    parser.add_argument("--pages", type=int, default=30)
    parser.add_argument("--js", type=int, default=30)
    parser.add_argument("--limit", type=float, default=3600, help="seconds a poll may take")
    parser.add_argument("--browser-memory", default="1g")
    parser.add_argument("--keep", action="store_true", help="leave the stack running")
    args = parser.parse_args()
    if args.command == "seed":
        asyncio.run(seed())
        return
    if args.command == "cycle":
        asyncio.run(cycle(args.limit))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    machine = host()
    # Kept per number of tabs, so runs of one setting each add up to the table.
    for tabs in args.tabs.split(","):
        result = run_one(int(tabs), args)
        (OUT / f"result.tabs{tabs}.json").write_text(
            json.dumps({"host": machine, "args": vars(args), **result}, ensure_ascii=False),
            encoding="utf-8",
        )
    results = sorted(
        (json.loads(path.read_text(encoding="utf-8")) for path in OUT.glob("result.tabs*.json")),
        key=lambda found: int(found["tabs"]),
    )
    REPORT.write_text(render(results, machine, args), encoding="utf-8", newline="\n")
    print(REPORT)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    sys.exit(main())
