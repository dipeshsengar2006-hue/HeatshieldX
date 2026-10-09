from __future__ import annotations

from app import main
from app.config import get_config
from app.i18n import CITIZEN_EN, CITIZEN_REQUIRED_IDS, validate_citizen_i18n
from app.services.routing_engine import PathResult, _recommendation


def _path(route_type: str, heat: float, duration: float = 600) -> PathResult:
    return PathResult(
        route_type=route_type,
        nodes=(),
        segment_ids=(),
        length_m=1000,
        time_s=duration,
        heat_cost=heat,
        average_exposure=heat / 1000,
        weighted_shade=0.5,
        average_access_penalty=0.0,
        coordinates=(),
    )


def test_citizen_page_contains_route_controls_examples_and_dictionary_strings(client):
    response = client.get("/citizen")
    assert response.status_code == 200
    for element_id in ("origin-input", "destination-input", "departure-slider", "find-routes"):
        assert f'id="{element_id}"' in response.text
    assert response.text.count('data-preset="') == 3
    assert "No stop data available" in response.text
    validate_citizen_i18n()
    assert CITIZEN_REQUIRED_IDS <= CITIZEN_EN.keys()
    assert CITIZEN_EN["stops_unavailable"] == "No stop data available"
    assert CITIZEN_EN["stops_no_eligible"] == "No eligible stops recorded in OSM along this route"
    citizen_copy = " ".join(CITIZEN_EN.values()).casefold()
    assert all(term not in citizen_copy for term in ("heatstroke", "prevent", "safe route"))


def test_recommendation_respects_minimum_reduction_threshold_and_wording():
    config = get_config()
    fastest = _path("FASTEST", 100)
    just_below = _path("HEAT_AWARE", 95.1, 660)
    at_threshold = _path("HEAT_AWARE", 95, 660)

    small = _recommendation(fastest, just_below, config)
    recommended = _recommendation(fastest, at_threshold, config)

    assert "Differences are small (4.9% lower modelled heat exposure)" in small
    assert "reasonable choice" in small
    assert "Recommended heat-aware route" not in small
    assert "Recommended heat-aware route" in recommended
    assert "5.0% lower" in recommended
    assert not any(word in (small + recommended).casefold() for word in ("safe", "prevents", "medical", "heatstroke"))


def test_startup_invokes_graph_warmup(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "warm_route_graph", lambda config: calls.append(config))
    main.warm_cached_routing_graph()
    assert calls == [get_config()]


def test_citizen_copy_has_no_missing_required_ids_and_forbidden_terms():
    validate_citizen_i18n()
    assert CITIZEN_REQUIRED_IDS - CITIZEN_EN.keys() == set()
    copy = " ".join(CITIZEN_EN.values()).casefold()
    assert "heatstroke" not in copy
    assert "prevent" not in copy
    assert "safe route" not in copy
