from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from reachai.config import get_settings
from reachai.models.candidate import CandidateProfile
from reachai.service import ReachAIService, WorkflowError


class TargetInput(BaseModel):
    name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    email: str | None = None
    linkedin_url: str | None = None
    location: str | None = None
    headline: str | None = None
    source: str = "web"


class JobInput(BaseModel):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str | None = None
    url: str | None = None
    description: str | None = None
    source: str = "web"


class PrepareOutreachInput(BaseModel):
    target_id: str
    job_id: str | None = None
    send_approval_email: bool = False
    use_llm: bool = False


settings = get_settings()
service = ReachAIService(settings=settings)
app = FastAPI(
    title="ReachAI",
    description="Local-first, human-approved AI outreach workflow",
    version="0.2.0",
)


def _run(operation: Any) -> Any:
    try:
        return operation()
    except WorkflowError as exc:
        status_code = 404 if exc.code.endswith("not_found") else 409
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    index_path = Path(__file__).with_name("static") / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "reachai", "version": app.version}


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    return service.status()


@app.get("/api/profile")
def get_profile() -> dict[str, Any]:
    return service.get_profile().model_dump()


@app.put("/api/profile")
def update_profile(profile: CandidateProfile) -> dict[str, Any]:
    return service.save_profile(profile).model_dump()


@app.get("/api/targets")
def get_targets() -> list[dict[str, Any]]:
    return service.list_targets()


@app.post("/api/targets", status_code=201)
def add_target(target: TargetInput) -> dict[str, Any]:
    return service.create_target(target.model_dump())


@app.get("/api/jobs")
def get_jobs() -> list[dict[str, Any]]:
    return service.list_jobs()


@app.post("/api/jobs", status_code=201)
def add_job(job: JobInput) -> dict[str, Any]:
    return service.create_job(job.model_dump())


@app.get("/api/outreach")
def get_outreach() -> list[dict[str, Any]]:
    return service.list_outreach()


@app.post("/api/outreach/prepare", status_code=201)
def prepare_outreach(payload: PrepareOutreachInput) -> dict[str, Any]:
    return _run(lambda: service.prepare_outreach(
        target_id=payload.target_id,
        job_id=payload.job_id,
        send_approval_email=payload.send_approval_email,
        use_llm=payload.use_llm,
    ))


@app.get("/api/approvals/{token}/{action}", response_class=HTMLResponse, include_in_schema=False)
def confirm_outreach_decision(token: str, action: str) -> HTMLResponse:
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=404, detail="Unknown approval action")
    safe_token = escape(token, quote=True)
    safe_action = escape(action, quote=True)
    label = "Approve" if action == "approve" else "Reject"
    return HTMLResponse(f"""
        <!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
        <title>{label} ReachAI draft</title><style>
        body{{font:16px system-ui;background:#f4f1e9;color:#17231d;display:grid;place-items:center;min-height:100vh;margin:0}}
        main{{background:#fffdf7;border:1px solid #d8d3c7;border-radius:18px;padding:30px;max-width:440px;box-shadow:0 18px 50px #1d2e2517}}
        button{{border:0;border-radius:11px;padding:11px 17px;background:#155d3a;color:white;font:600 15px system-ui;cursor:pointer}}
        a{{color:#155d3a;margin-left:12px}}</style></head><body><main>
        <h1>{label} this draft?</h1><p>This confirmation prevents email link scanners from changing outreach state.</p>
        <form method="post" action="/api/approvals/{safe_token}/{safe_action}"><button type="submit">Confirm {safe_action}</button><a href="/">Cancel</a></form>
        </main></body></html>
    """)


@app.post("/api/approvals/{token}/{action}")
def decide_outreach(token: str, action: str, request: Request) -> Any:
    # The emailed confirmation page posts a plain HTML form; answer it with a page, not JSON.
    if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        try:
            decision = service.decide(token, action)
            heading, detail = f"Draft {escape(action)}d", "The decision was recorded. You can close this tab."
            delivery = decision.get("delivery") or {}
            if delivery.get("status") == "SENT":
                heading, detail = "Approved and sent", "The message was sent. You can close this tab."
            elif delivery:
                detail = "Approved, but not sent yet: " + escape(str(delivery.get("error") or delivery.get("status")))
        except WorkflowError as exc:
            heading, detail = "Nothing changed", escape(str(exc))
        return HTMLResponse(f"""
            <!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
            <title>ReachAI decision</title><style>
            body{{font:16px system-ui;background:#f4f1e9;color:#17231d;display:grid;place-items:center;min-height:100vh;margin:0}}
            main{{background:#fffdf7;border:1px solid #d8d3c7;border-radius:18px;padding:30px;max-width:440px}}
            a{{color:#155d3a}}</style></head><body><main>
            <h1>{heading}</h1><p>{detail}</p><p><a href="/">Open the dashboard</a></p>
            </main></body></html>
        """)
    return _run(lambda: service.decide(token, action))


@app.post("/api/find")
def find_people() -> dict[str, Any]:
    return _run(lambda: service.run_cycle(find=True))


@app.post("/api/outreach/{outreach_id}/send")
def send_outreach(outreach_id: str) -> dict[str, Any]:
    return _run(lambda: service.send(outreach_id))


def run() -> None:
    import uvicorn

    current = get_settings()
    uvicorn.run("reachai.api:app", host=current.host, port=current.port, reload=False)
