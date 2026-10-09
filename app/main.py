"""FastAPI application entry point for Prompt 1."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_config
from app.logging_config import configure_logging
from app.routes.planner import router as planner_router
from app.services.routing_engine import warm_route_graph


configure_logging()
app = FastAPI(title="HeatShield X", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(planner_router)


@app.exception_handler(RequestValidationError)
async def citizen_validation_message(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Attach a stable bilingual catalog id to public route/summary validation errors."""
    if request.url.path in {"/api/routes", "/api/public/summary"}:
        message_id = "route_error_422" if request.url.path == "/api/routes" else "summary_error_area"
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "message_id": message_id,
                "message_params": {},
            },
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.on_event("startup")
def warm_cached_routing_graph() -> None:
    """Prepare the cache-only route graph before the first citizen request."""
    warm_route_graph(get_config())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
