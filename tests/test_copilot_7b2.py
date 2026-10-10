"""Prompt 7B-2 Copilot UI contracts and compatible API context coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from app.i18n import CITIZEN_EN, CITIZEN_HI, validate_citizen_i18n
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(app)


def test_both_pages_include_the_copilot_button_and_accessible_panel():
    for path in ("/", "/citizen"):
        response = CLIENT.get(path)
        assert response.status_code == 200
        for expected in (
            'id="copilot-open"', 'id="copilot-panel"', 'id="copilot-conversation"',
            'aria-modal="false"', 'aria-live="polite"', 'id="copilot-clear"',
        ):
            assert expected in response.text


def test_copilot_catalog_has_parity_safe_word_choice_and_required_examples():
    validate_citizen_i18n()
    copilot_ids = {key for key in CITIZEN_EN if key.startswith("copilot_")}
    assert copilot_ids <= CITIZEN_HI.keys()
    assert "Mujhe route mein heat se bachne ke liye kya karna chahiye?" == CITIZEN_EN["copilot_example_heat"]
    new_copy = " ".join(CITIZEN_EN[key] for key in copilot_ids).casefold()
    assert not any(term in new_copy for term in ("heatstroke", "prevent", "safe route"))


def test_agni_ui_copy_and_panel_state_contracts_are_present():
    template = (ROOT / "app" / "templates" / "_copilot_panel.html").read_text(encoding="utf-8")
    javascript = (ROOT / "app" / "static" / "js" / "copilot.js").read_text(encoding="utf-8")

    stylesheet = (ROOT / "app" / "static" / "css" / "base.css").read_text(encoding="utf-8")
    assert 'aria-hidden="true" hidden inert' in template
    assert 'data-copilot-i18n="copilot_subtitle"' in template
    assert 'data-copilot-i18n-aria-label="copilot_open"' in template
    assert "agni-wave-ring" in template
    assert "[hidden] { display: none !important; }" in stylesheet
    assert ".copilot-panel.is-open" in stylesheet
    assert "pointer-events: none" in stylesheet
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet
    for catalog in (CITIZEN_EN, CITIZEN_HI):
        assert "copilot" not in catalog["copilot_button"].casefold()
        assert "copilot" not in catalog["copilot_panel_title"].casefold()
        assert "copilot" not in catalog["copilot_close"].casefold()
        assert "copilot" not in catalog["copilot_input_label"].casefold()
        assert "copilot" not in catalog["copilot_footer"].casefold()
        assert "copilot_empty_greeting" in catalog
    assert any("\u0900" <= char <= "\u097f" for char in CITIZEN_HI["copilot_subtitle"])
    assert any("\u0900" <= char <= "\u097f" for char in CITIZEN_HI["copilot_open"])
    for expected in (
        "root.dataset.copilotInitialized",
        "const setOpen",
        'panel.setAttribute("aria-hidden", String(!nextOpen))',
        'openButton.setAttribute("aria-expanded", String(nextOpen))',
        "activeElement !== document.body",
        "window.matchMedia(\"(max-width: 760px)\")",
        'event.key === "Escape"',
    ):
        assert expected in javascript
    assert javascript.count("const setOpen") == 1
    set_open_body = javascript.split("const setOpen", 1)[1].split("const closePanel", 1)[0]
    assert set_open_body.count("panel.hidden") == 2


def test_copilot_accepts_the_ui_context_shape_and_returns_rendering_fields():
    risk = CLIENT.get("/api/risk", params={"time": "09:00"})
    assert risk.status_code == 200
    segment_id = risk.json()["features"][0]["properties"]["canonical_street_key"]
    plan = CLIENT.post("/api/optimize", json={"water_points": 2, "cooling_centres": 1, "shade_structures": 2})
    assert plan.status_code == 200
    response = CLIENT.post("/api/copilot", json={
        "message": "Why is this street high risk?", "ui_language": "en",
        "context": {
            "view": "planner", "time": "09:00", "selected_segment_id": segment_id,
            "plan_id": plan.json()["plan_id"],
            "origin": {"lat": 22.7146202, "lon": 75.8542367},
            "destination": {"lat": 22.7188165, "lon": 75.8553691},
        },
    })
    assert response.status_code == 200
    body = response.json()
    assert {"answer", "mode", "data_unavailable", "sources", "facts_used", "assumptions", "context_entity"} <= body.keys()
    assert body["facts_used"]["street"]["canonical_street_key"] == segment_id


def test_copilot_static_javascript_is_valid_and_keeps_conversation_out_of_storage():
    for filename in ("copilot.js", "citizen.js", "planner.js"):
        result = subprocess.run(
            ["node", "--check", str(ROOT / "app" / "static" / "js" / filename)],
            check=False, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    copilot_js = (ROOT / "app" / "static" / "js" / "copilot.js").read_text(encoding="utf-8")
    assert "conversation: []" in copilot_js
    assert "localStorage" not in copilot_js
    assert "sessionStorage" not in copilot_js
