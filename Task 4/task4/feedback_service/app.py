"""HTTP layer: FastAPI routes over FeedbackService. Interactive API docs at /docs.

POST endpoints that start work take ?wait=true (default): the response comes when the job is done (200), or
after 600 s with the current state (202). ?wait=false returns 202 at once; poll GET /feedback/{fid}."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .bridge import load_instance_spec
from .schemas import ClarificationIn, CreateSession, FeedbackIn, ReplyIn
from .service import ApiError


def create_app(service):
    @asynccontextmanager
    async def lifespan(app):
        service.start()
        print(f"feedback service: engine thread started, {len(service.store.sessions)} sessions loaded, "
              f"recovered {service.recovered}", flush=True)
        yield
        service.stop()
        print("feedback service: engine thread stopped, shutdown complete", flush=True)

    app = FastAPI(title="TPO feedback pipeline", version="task4_v1", lifespan=lifespan,
                  description="Complaints in natural language are localized, turned into critiques and fed to "
                              "a TPO loop that edits the optimization model; Gurobi re-solves.")
    app.state.service = service

    @app.exception_handler(ApiError)
    def api_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": exc.code, "detail": exc.detail})

    def started(view_done):
        view, done = view_done
        return JSONResponse(status_code=200 if done else 202, content=view)

    @app.get("/health")
    def health():
        return service.health()

    @app.get("/instance")
    def instance():
        return load_instance_spec()

    @app.post("/sessions", status_code=201)
    def create_session(body: CreateSession):
        return service.create_session(body.model_dump())

    @app.get("/sessions")
    def list_sessions():
        return service.list_sessions()

    @app.get("/sessions/{sid}")
    def get_session(sid: str):
        return service.get_session(sid)

    @app.post("/sessions/{sid}/feedback")
    def submit_feedback(sid: str, body: FeedbackIn, wait: bool = True):
        return started(service.submit_feedback(sid, body.model_dump(), wait))

    @app.get("/sessions/{sid}/iterations")
    def iterations(sid: str, feedback_id: str | None = None):
        return service.iterations(sid, feedback_id)

    @app.get("/sessions/{sid}/events")
    def events(sid: str):
        return service.events(sid)

    @app.get("/feedback/{fid}")
    def get_feedback(fid: str):
        return service.get_feedback(fid)

    @app.post("/feedback/{fid}/clarification")
    def clarification(fid: str, body: ClarificationIn, wait: bool = True):
        return started(service.clarify(fid, body.answer, wait))

    @app.post("/feedback/{fid}/reply")
    def reply(fid: str, body: ReplyIn, wait: bool = True):
        return started(service.reply(fid, body.model_dump(), wait))

    return app
