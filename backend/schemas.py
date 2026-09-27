from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ActionItemOut(BaseModel):
    id: int
    project: str
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    priority: str
    status: str
    pending_status: Optional[str] = None
    source_snippet: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RiskOut(BaseModel):
    id: int
    project: str
    description: str
    severity: str
    mitigation: Optional[str] = None
    source_snippet: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DecisionOut(BaseModel):
    id: int
    project: str
    description: str
    decided_by: Optional[str] = None
    date: Optional[str] = None
    source_snippet: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DependencyOut(BaseModel):
    id: int
    project: str
    description: str
    depends_on: Optional[str] = None
    source_snippet: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OpenIssueOut(BaseModel):
    id: int
    project: str
    description: str
    raised_by: Optional[str] = None
    status: str
    source_snippet: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    project: str
    chunks_indexed: int
    action_items_found: int
    risks_found: int
    decisions_found: int
    dependencies_found: int
    open_issues_found: int


class QnARequest(BaseModel):
    project: str
    question: str


class SourceRef(BaseModel):
    document: str
    snippet: str


class QnAResponse(BaseModel):
    answer: str
    sources: List[SourceRef]


class StatusChangeRequest(BaseModel):
    new_status: str
    requested_by: str = "unassigned"
    reason: Optional[str] = None


class ApprovalReviewRequest(BaseModel):
    approved: bool
    reviewer: str = "unassigned"


class ApprovalOut(BaseModel):
    id: int
    action_item_id: int
    old_status: str
    proposed_status: str
    requested_by: Optional[str] = None
    reason: Optional[str] = None
    reviewed: bool
    approved: Optional[bool] = None
    reviewer: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WeeklyReportResponse(BaseModel):
    project: str
    report_markdown: str


class SettingsIn(BaseModel):
    llm_provider: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)

    @field_validator("llm_provider")
    @classmethod
    def _validate_provider(cls, v):
        if v is not None and v != "" and v not in {"groq", "gemini", "ollama"}:
            raise ValueError("llm_provider must be one of: groq, gemini, ollama")
        return v


class SettingsOut(BaseModel):
    llm_provider: str
    groq_api_key: str
    groq_model: str
    gemini_api_key: str
    gemini_model: str
    ollama_model: str
    ollama_base_url: str
    top_k: int


class ProjectDeleteResponse(BaseModel):
    project: str
    deleted: dict[str, int]


class ProjectSummary(BaseModel):
    name: str
    document_count: int
    last_activity: Optional[datetime] = None
