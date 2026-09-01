from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.models import OutreachRequest
from app.service import OutreachWorkflow

app = FastAPI(title="ReachAI", version="0.1.0")
workflow = OutreachWorkflow()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/outreach/prepare")
def prepare_outreach(request: OutreachRequest):
    draft = workflow.prepare_outreach(request)
    return {
        "target_person": draft.target_person,
        "company": draft.company,
        "message": draft.message,
        "needs_approval": draft.needs_approval,
        "research_summary": draft.research_summary,
        "match_summary": draft.match_summary,
    }


@app.post("/outreach/send")
def send_outreach(payload: dict):
    try:
        draft = workflow.prepare_outreach(payload["request"])
        result = workflow.send_outreach(draft, approved=payload.get("approved", False))
        return JSONResponse(status_code=200, content=result)
    except ValueError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
