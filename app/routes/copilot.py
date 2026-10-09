"""Grounded, UI-independent Copilot API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.services.copilot_service import answer_copilot


router = APIRouter()


class CopilotCoordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)


class CopilotContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    view: str | None = Field(default=None, max_length=40)
    time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    selected_segment_id: str | None = Field(default=None, max_length=200)
    plan_id: str | None = Field(default=None, max_length=200)
    origin: CopilotCoordinate | None = None
    destination: CopilotCoordinate | None = None


class CopilotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=500)
    ui_language: Literal["en", "hi"] = "en"
    context: CopilotContext | None = None


class CopilotResponse(BaseModel):
    answer: str
    language: Literal["en", "hi"]
    intent: Literal[
        "platform_guide", "risk_explanation", "route_assistant", "safe_stop_assistant",
        "planner_assistant", "data_transparency", "heat_safety", "unknown",
    ]
    mode: Literal["template", "llm"]
    data_unavailable: bool
    sources: list[dict[str, str]]
    facts_used: dict
    assumptions: list[str]
    context_entity: dict | None


@router.post("/api/copilot", response_model=CopilotResponse)
def copilot(payload: CopilotRequest) -> dict:
    """Retrieve actual deterministic outputs and produce a grounded template answer."""
    return answer_copilot(
        payload.message,
        payload.ui_language,
        payload.context.model_dump(exclude_none=True) if payload.context else {},
    )
