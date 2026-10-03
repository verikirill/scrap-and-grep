"""A closed network: outside names resolve at the proxy, and nothing of the
stack has a way out but the egress proxy."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from radar.ingest.net import UnresolvableHostError, UnsafeUrlError, resolve_public

ROOT = Path(__file__).resolve().parents[2]
# The .invalid domain never resolves (RFC 2606).
NOWHERE = "https://news.invalid/feed"


@pytest.fixture
def dns_via_proxy(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from radar.config import get_settings

    monkeypatch.setenv("RADAR_FETCH_DNS_VIA_PROXY", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_a_name_that_does_not_resolve_is_no_site_by_default() -> None:
    with pytest.raises(UnresolvableHostError):
        await resolve_public(NOWHERE)


async def test_through_a_resolving_proxy_it_goes_out_by_name(dns_via_proxy: None) -> None:
    assert await resolve_public(NOWHERE) is None
    # What resolves here is checked as before: the proxy is never asked inside.
    for inside in ("http://127.0.0.1/", "http://localhost/", "http://10.0.0.1/"):
        with pytest.raises(UnsafeUrlError):
            await resolve_public(inside)


def _airgap() -> dict[str, Any]:
    base = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    overlay = yaml.safe_load((ROOT / "docker-compose.airgap.yml").read_text(encoding="utf-8"))
    networks = {**base["networks"], **overlay["networks"]}
    services = {}
    for name, service in base["services"].items():
        services[name] = {**service, **overlay["services"].get(name, {})}
    services["egress"] = overlay["services"]["egress"]
    return {"networks": networks, "services": services}


def test_only_the_egress_proxy_and_the_published_port_leave_the_stack() -> None:
    stack = _airgap()
    open_networks = {
        name for name, network in stack["networks"].items() if not (network or {}).get("internal")
    }
    assert open_networks == {"outside", "edge"}
    reaching_out = {
        name
        for name, service in stack["services"].items()
        if set(service.get("networks") or ["default"]) & open_networks
    }
    assert reaching_out == {"egress", "web"}
    for name in ("api", "worker-ingest", "worker-digest", "worker-media", "cli"):
        environment = stack["services"][name]["environment"]
        assert environment["RADAR_HTTP_PROXY"] == "http://egress:3128", name
        assert environment["RADAR_FETCH_DNS_VIA_PROXY"] == "true", name
