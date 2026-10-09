"""FastAPI application entry point for Prompt 1."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_config
from app.logging_config import configure_logging
from app.routes.planner import router as planner_router
from app.services.routing_engine import warm_route_graph


configure_logging()
app = FastAPI(title="HeatShield X", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(planner_router)


@app.on_event("startup")
def warm_cached_routing_graph() -> None:
    """Prepare the cache-only route graph before the first citizen request."""
    warm_route_graph(get_config())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
