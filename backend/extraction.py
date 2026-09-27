"""Runs a single LLM pass over a document's raw text and extracts structured
project-management entities as JSON, then persists them as ORM rows.
"""
from sqlalchemy.orm import Session

from backend.llm_client import get_llm_client, safe_json_parse
from backend.models import ActionItem, Decision, Dependency, Document, OpenIssue, Risk

SYSTEM_PROMPT = """You are a meticulous project operations analyst. You read raw project
documents (meeting notes, status reports, emails, task lists) and extract structured,
factual information. Never invent information that is not in the text. If a field is not
stated, use null. Always respond with a single valid JSON object and nothing else."""

EXTRACTION_INSTRUCTIONS = """Extract the following from the document below and return ONLY
a JSON object with exactly these keys:

{
  "action_items": [
    {"task": str, "owner": str|null, "deadline": str|null,
     "priority": "low"|"medium"|"high", "status": "open"|"in_progress"|"done"|"blocked",
     "source_snippet": str}
  ],
  "risks": [
    {"description": str, "severity": "low"|"medium"|"high",
     "mitigation": str|null, "source_snippet": str}
  ],
  "decisions": [
    {"description": str, "decided_by": str|null, "date": str|null, "source_snippet": str}
  ],
  "dependencies": [
    {"description": str, "depends_on": str|null, "source_snippet": str}
  ],
  "open_issues": [
    {"description": str, "raised_by": str|null, "status": "open"|"resolved", "source_snippet": str}
  ]
}

Rules:
- "source_snippet" must be a short (<200 char) verbatim excerpt from the document that
  supports the extracted item, so it can be cited back to the source.
- If a category has no items, return an empty list for it — do not omit the key.
- Default status to "open" and priority to "medium" when not stated.
- Only extract what is explicitly present; do not infer owners or deadlines that aren't there.

DOCUMENT:
---
{document_text}
---
"""


def extract_and_persist(db: Session, document: Document) -> dict:
    llm = get_llm_client()
    prompt = EXTRACTION_INSTRUCTIONS.replace("{document_text}", document.raw_text[:12000])
    raw = llm.generate(SYSTEM_PROMPT, prompt, json_mode=True)
    data = safe_json_parse(raw)

    counts = {"action_items": 0, "risks": 0, "decisions": 0, "dependencies": 0, "open_issues": 0}

    for item in data.get("action_items", []):
        db.add(ActionItem(
            document_id=document.id,
            project=document.project,
            task=item.get("task", "").strip(),
            owner=item.get("owner"),
            deadline=item.get("deadline"),
            priority=item.get("priority") or "medium",
            status=item.get("status") or "open",
            source_snippet=item.get("source_snippet"),
        ))
        counts["action_items"] += 1

    for item in data.get("risks", []):
        db.add(Risk(
            document_id=document.id,
            project=document.project,
            description=item.get("description", "").strip(),
            severity=item.get("severity") or "medium",
            mitigation=item.get("mitigation"),
            source_snippet=item.get("source_snippet"),
        ))
        counts["risks"] += 1

    for item in data.get("decisions", []):
        db.add(Decision(
            document_id=document.id,
            project=document.project,
            description=item.get("description", "").strip(),
            decided_by=item.get("decided_by"),
            date=item.get("date"),
            source_snippet=item.get("source_snippet"),
        ))
        counts["decisions"] += 1

    for item in data.get("dependencies", []):
        db.add(Dependency(
            document_id=document.id,
            project=document.project,
            description=item.get("description", "").strip(),
            depends_on=item.get("depends_on"),
            source_snippet=item.get("source_snippet"),
        ))
        counts["dependencies"] += 1

    for item in data.get("open_issues", []):
        db.add(OpenIssue(
            document_id=document.id,
            project=document.project,
            description=item.get("description", "").strip(),
            raised_by=item.get("raised_by"),
            status=item.get("status") or "open",
            source_snippet=item.get("source_snippet"),
        ))
        counts["open_issues"] += 1

    db.commit()
    return counts
