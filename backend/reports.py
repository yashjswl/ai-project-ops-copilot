from datetime import datetime

from sqlalchemy.orm import Session

from backend.llm_client import get_llm_client
from backend.models import ActionItem, Decision, Dependency, OpenIssue, Risk

SYSTEM_PROMPT = """You are a project operations analyst writing a concise weekly status
report for stakeholders. Use only the structured data provided. Be specific — name owners,
deadlines, and counts. Write in clear markdown with short sections. Do not invent facts."""


def _fmt_action_items(items: list[ActionItem]) -> str:
    if not items:
        return "None."
    lines = []
    for a in items:
        lines.append(f"- [{a.status}] {a.task} (owner: {a.owner or 'unassigned'}, "
                      f"deadline: {a.deadline or 'none'}, priority: {a.priority})")
    return "\n".join(lines)


def _fmt_risks(items: list[Risk]) -> str:
    if not items:
        return "None."
    return "\n".join(f"- [{r.severity}] {r.description}" for r in items)


def _fmt_decisions(items: list[Decision]) -> str:
    if not items:
        return "None."
    return "\n".join(f"- {d.description} (by {d.decided_by or 'unspecified'})" for d in items)


def _fmt_dependencies(items: list[Dependency]) -> str:
    if not items:
        return "None."
    return "\n".join(f"- {d.description} (depends on: {d.depends_on or 'unspecified'})" for d in items)


def _fmt_open_issues(items: list[OpenIssue]) -> str:
    if not items:
        return "None."
    return "\n".join(f"- [{i.status}] {i.description}" for i in items)


def generate_weekly_report(db: Session, project: str) -> str:
    action_items = db.query(ActionItem).filter(ActionItem.project == project).all()
    risks = db.query(Risk).filter(Risk.project == project).all()
    decisions = db.query(Decision).filter(Decision.project == project).all()
    dependencies = db.query(Dependency).filter(Dependency.project == project).all()
    open_issues = db.query(OpenIssue).filter(OpenIssue.project == project).all()

    overdue = [a for a in action_items if a.status not in ("done",) and a.deadline]
    done = [a for a in action_items if a.status == "done"]

    data_summary = f"""
Project: {project}
Report generated: {datetime.utcnow().strftime('%Y-%m-%d')}

Action items ({len(action_items)} total, {len(done)} done):
{_fmt_action_items(action_items)}

Risks ({len(risks)}):
{_fmt_risks(risks)}

Decisions made ({len(decisions)}):
{_fmt_decisions(decisions)}

Dependencies ({len(dependencies)}):
{_fmt_dependencies(dependencies)}

Open issues ({len(open_issues)}):
{_fmt_open_issues(open_issues)}
"""

    user_prompt = f"""Using the structured project data below, write a weekly status report
with these markdown sections: ## Summary, ## Progress This Week, ## Risks & Blockers,
## Decisions, ## Action Items Needing Attention, ## Next Steps.

{data_summary}
"""

    llm = get_llm_client()
    return llm.generate(SYSTEM_PROMPT, user_prompt)
