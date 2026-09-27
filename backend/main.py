from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import ingestion, settings_store, vectorstore
from backend.config import settings
from backend.database import get_db, init_db
from backend.extraction import extract_and_persist
from backend.models import ActionItem, ApprovalRequest, Decision, Dependency, Document, OpenIssue, Risk
from backend.rag import answer_question
from backend.reports import generate_weekly_report
from backend.schemas import (
    ActionItemOut,
    ApprovalOut,
    ApprovalReviewRequest,
    DecisionOut,
    DependencyOut,
    OpenIssueOut,
    ProjectDeleteResponse,
    ProjectSummary,
    QnARequest,
    QnAResponse,
    RiskOut,
    SettingsIn,
    SettingsOut,
    StatusChangeRequest,
    UploadResponse,
    WeeklyReportResponse,
)

app = FastAPI(title="AI Project Operations Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RuntimeError)
@app.exception_handler(ValueError)
async def config_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Settings --------------------------------------------------------------

@app.get("/settings", response_model=SettingsOut)
def get_settings():
    return settings_store.build_effective_view(settings)


@app.put("/settings", response_model=SettingsOut)
def put_settings(payload: SettingsIn):
    overlay = settings_store.resolve_update(payload.model_dump(exclude_unset=True))
    settings.apply_overrides(overlay)
    return settings_store.build_effective_view(settings)


# --- Projects ------------------------------------------------------------

@app.get("/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    rows = (
        db.query(Document.project, func.count(Document.id), func.max(Document.uploaded_at))
        .group_by(Document.project)
        .order_by(func.max(Document.uploaded_at).desc())
        .all()
    )
    return [
        ProjectSummary(name=name, document_count=count, last_activity=last_activity)
        for name, count, last_activity in rows
    ]


# --- Ingestion ---------------------------------------------------------

@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(project: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw_bytes = await file.read()
    text = ingestion.parse_file(file.filename, raw_bytes)
    if not text.strip():
        raise HTTPException(400, "Could not extract any text from this file.")

    document = Document(
        project=project,
        filename=file.filename,
        source_type=ingestion.guess_source_type(file.filename),
        raw_text=text,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    chunks = ingestion.chunk_text(text)
    n_chunks = vectorstore.add_chunks(document.id, project, file.filename, chunks)

    counts = extract_and_persist(db, document)

    return UploadResponse(
        document_id=document.id,
        filename=file.filename,
        project=project,
        chunks_indexed=n_chunks,
        action_items_found=counts["action_items"],
        risks_found=counts["risks"],
        decisions_found=counts["decisions"],
        dependencies_found=counts["dependencies"],
        open_issues_found=counts["open_issues"],
    )


# --- Structured data -----------------------------------------------------

@app.get("/projects/{project}/action-items", response_model=list[ActionItemOut])
def list_action_items(
    project: str,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(ActionItem).filter(ActionItem.project == project)
    if status:
        q = q.filter(ActionItem.status == status)
    if owner:
        q = q.filter(ActionItem.owner == owner)
    return q.order_by(ActionItem.created_at.desc()).all()


@app.get("/projects/{project}/risks", response_model=list[RiskOut])
def list_risks(project: str, db: Session = Depends(get_db)):
    return db.query(Risk).filter(Risk.project == project).order_by(Risk.created_at.desc()).all()


@app.get("/projects/{project}/decisions", response_model=list[DecisionOut])
def list_decisions(project: str, db: Session = Depends(get_db)):
    return db.query(Decision).filter(Decision.project == project).order_by(Decision.created_at.desc()).all()


@app.get("/projects/{project}/dependencies", response_model=list[DependencyOut])
def list_dependencies(project: str, db: Session = Depends(get_db)):
    return db.query(Dependency).filter(Dependency.project == project).order_by(Dependency.created_at.desc()).all()


@app.get("/projects/{project}/open-issues", response_model=list[OpenIssueOut])
def list_open_issues(project: str, db: Session = Depends(get_db)):
    return db.query(OpenIssue).filter(OpenIssue.project == project).order_by(OpenIssue.created_at.desc()).all()


@app.delete("/projects/{project}", response_model=ProjectDeleteResponse)
def delete_project(project: str, db: Session = Depends(get_db)):
    """Permanently deletes all structured data and indexed document chunks
    for a project. Idempotent: a project with no data returns all-zero
    counts rather than a 404, since "project" is just a shared string field,
    not a stored entity."""
    action_item_ids = [r.id for r in db.query(ActionItem.id).filter(ActionItem.project == project)]

    counts = {
        "documents": db.query(Document).filter(Document.project == project).count(),
        "action_items": len(action_item_ids),
        "risks": db.query(Risk).filter(Risk.project == project).count(),
        "decisions": db.query(Decision).filter(Decision.project == project).count(),
        "dependencies": db.query(Dependency).filter(Dependency.project == project).count(),
        "open_issues": db.query(OpenIssue).filter(OpenIssue.project == project).count(),
        "approval_requests": (
            db.query(ApprovalRequest).filter(ApprovalRequest.action_item_id.in_(action_item_ids)).count()
            if action_item_ids
            else 0
        ),
    }

    if action_item_ids:
        db.query(ApprovalRequest).filter(ApprovalRequest.action_item_id.in_(action_item_ids)).delete(
            synchronize_session=False
        )
    for Model in (ActionItem, Risk, Decision, Dependency, OpenIssue):
        db.query(Model).filter(Model.project == project).delete(synchronize_session=False)
    db.query(Document).filter(Document.project == project).delete(synchronize_session=False)
    db.commit()

    vectorstore.delete_project(project)

    return ProjectDeleteResponse(project=project, deleted=counts)


# --- Q&A (RAG) -----------------------------------------------------------

@app.post("/qna", response_model=QnAResponse)
def qna(req: QnARequest):
    result = answer_question(req.project, req.question)
    return result


# --- Weekly report ---------------------------------------------------------

@app.get("/projects/{project}/weekly-report", response_model=WeeklyReportResponse)
def weekly_report(project: str, db: Session = Depends(get_db)):
    report = generate_weekly_report(db, project)
    return WeeklyReportResponse(project=project, report_markdown=report)


# --- Human-in-the-loop approvals --------------------------------------------

@app.post("/action-items/{item_id}/request-status-change", response_model=ApprovalOut)
def request_status_change(item_id: int, req: StatusChangeRequest, db: Session = Depends(get_db)):
    item = db.query(ActionItem).get(item_id)
    if not item:
        raise HTTPException(404, "Action item not found")

    approval = ApprovalRequest(
        action_item_id=item.id,
        old_status=item.status,
        proposed_status=req.new_status,
        requested_by=req.requested_by,
        reason=req.reason,
    )
    item.pending_status = req.new_status
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


@app.get("/approvals/pending", response_model=list[ApprovalOut])
def pending_approvals(db: Session = Depends(get_db)):
    return db.query(ApprovalRequest).filter(ApprovalRequest.reviewed == False).all()  # noqa: E712


@app.post("/approvals/{approval_id}/review", response_model=ApprovalOut)
def review_approval(approval_id: int, req: ApprovalReviewRequest, db: Session = Depends(get_db)):
    from datetime import datetime

    approval = db.query(ApprovalRequest).get(approval_id)
    if not approval:
        raise HTTPException(404, "Approval request not found")

    approval.reviewed = True
    approval.approved = req.approved
    approval.reviewer = req.reviewer
    approval.reviewed_at = datetime.utcnow()

    item = db.query(ActionItem).get(approval.action_item_id)
    if item:
        item.pending_status = None
        if req.approved:
            item.status = approval.proposed_status

    db.commit()
    db.refresh(approval)
    return approval
