from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    project = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # meeting_notes | status_report | email | task_list | pdf | other
    raw_text = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    action_items = relationship("ActionItem", back_populates="document", cascade="all, delete-orphan")
    risks = relationship("Risk", back_populates="document", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="document", cascade="all, delete-orphan")
    dependencies = relationship("Dependency", back_populates="document", cascade="all, delete-orphan")
    open_issues = relationship("OpenIssue", back_populates="document", cascade="all, delete-orphan")


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    project = Column(String, index=True, nullable=False)

    task = Column(Text, nullable=False)
    owner = Column(String, nullable=True)
    deadline = Column(String, nullable=True)  # kept as string: source text is rarely ISO-clean
    priority = Column(String, default="medium")  # low | medium | high
    status = Column(String, default="open")  # open | in_progress | done | blocked
    source_snippet = Column(Text, nullable=True)

    pending_status = Column(String, nullable=True)  # proposed new status awaiting approval
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="action_items")
    approvals = relationship("ApprovalRequest", back_populates="action_item", cascade="all, delete-orphan")


class Risk(Base):
    __tablename__ = "risks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    project = Column(String, index=True, nullable=False)

    description = Column(Text, nullable=False)
    severity = Column(String, default="medium")  # low | medium | high
    mitigation = Column(Text, nullable=True)
    source_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="risks")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    project = Column(String, index=True, nullable=False)

    description = Column(Text, nullable=False)
    decided_by = Column(String, nullable=True)
    date = Column(String, nullable=True)
    source_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="decisions")


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    project = Column(String, index=True, nullable=False)

    description = Column(Text, nullable=False)
    depends_on = Column(String, nullable=True)
    source_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="dependencies")


class OpenIssue(Base):
    __tablename__ = "open_issues"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    project = Column(String, index=True, nullable=False)

    description = Column(Text, nullable=False)
    raised_by = Column(String, nullable=True)
    status = Column(String, default="open")
    source_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="open_issues")


class ApprovalRequest(Base):
    """Human-in-the-loop gate: an LLM/user can propose a status change,
    but it only takes effect once a human reviews it here."""

    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True)
    action_item_id = Column(Integer, ForeignKey("action_items.id"))

    old_status = Column(String, nullable=False)
    proposed_status = Column(String, nullable=False)
    requested_by = Column(String, nullable=True)
    reason = Column(Text, nullable=True)

    reviewed = Column(Boolean, default=False)
    approved = Column(Boolean, nullable=True)
    reviewer = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    action_item = relationship("ActionItem", back_populates="approvals")
