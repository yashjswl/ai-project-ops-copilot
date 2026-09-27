import pandas as pd
import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="AI Project Operations Copilot", layout="wide")
st.title("AI Project Operations Copilot")
st.caption("Ingest project docs → structured action items, risks, decisions → cited Q&A → human-approved status updates")

if "project" not in st.session_state:
    st.session_state.project = "Project Alpha"

st.session_state.project = st.text_input("Project name", value=st.session_state.project)
project = st.session_state.project

tabs = st.tabs(["📤 Upload", "✅ Action Items", "⚠️ Risks", "🧭 Decisions & Dependencies",
                 "💬 Project Q&A", "📊 Weekly Report", "🔐 Approvals"])

# --- Upload -----------------------------------------------------------------
with tabs[0]:
    st.subheader("Upload a project document")
    st.caption("Meeting notes, status reports, emails, task lists (.txt, .pdf, .docx)")
    uploaded = st.file_uploader("Choose a file", type=["txt", "pdf", "docx", "md"])
    if uploaded and st.button("Ingest document"):
        with st.spinner("Parsing, chunking, embedding, and extracting structured data..."):
            files = {"file": (uploaded.name, uploaded.getvalue())}
            resp = requests.post(f"{API_BASE}/documents/upload", params={"project": project}, files=files)
        if resp.ok:
            data = resp.json()
            st.success(f"Indexed '{data['filename']}' — {data['chunks_indexed']} chunks embedded")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Action items", data["action_items_found"])
            c2.metric("Risks", data["risks_found"])
            c3.metric("Decisions", data["decisions_found"])
            c4.metric("Dependencies", data["dependencies_found"])
            c5.metric("Open issues", data["open_issues_found"])
        else:
            st.error(f"Upload failed: {resp.text}")

    st.divider()
    st.caption("No documents yet? Sample files for 'Project Alpha' are in `data/sample_documents/` — upload a few to see the full pipeline run.")

# --- Action Items -------------------------------------------------------------
with tabs[1]:
    st.subheader("Action items")
    col1, col2 = st.columns(2)
    status_filter = col1.selectbox("Filter by status", ["(all)", "open", "in_progress", "done", "blocked"])
    owner_filter = col2.text_input("Filter by owner (exact match)")

    params = {}
    if status_filter != "(all)":
        params["status"] = status_filter
    if owner_filter:
        params["owner"] = owner_filter

    resp = requests.get(f"{API_BASE}/projects/{project}/action-items", params=params)
    if resp.ok:
        items = resp.json()
        if items:
            df = pd.DataFrame(items)[["id", "task", "owner", "deadline", "priority", "status", "pending_status"]]
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("##### Propose a status change (requires human approval)")
            ac1, ac2, ac3, ac4 = st.columns([1, 2, 2, 1])
            item_id = ac1.number_input("Item ID", min_value=1, step=1)
            new_status = ac2.selectbox("New status", ["open", "in_progress", "done", "blocked"])
            requested_by = ac3.text_input("Requested by", value="you")
            if ac4.button("Submit request"):
                r = requests.post(
                    f"{API_BASE}/action-items/{int(item_id)}/request-status-change",
                    json={"new_status": new_status, "requested_by": requested_by},
                )
                if r.ok:
                    st.success("Change requested — waiting for approval in the Approvals tab.")
                else:
                    st.error(r.text)
        else:
            st.info("No action items yet for this project.")
    else:
        st.error(resp.text)

# --- Risks -----------------------------------------------------------------
with tabs[2]:
    st.subheader("Risks")
    resp = requests.get(f"{API_BASE}/projects/{project}/risks")
    if resp.ok:
        risks = resp.json()
        if risks:
            df = pd.DataFrame(risks)[["id", "description", "severity", "mitigation"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No risks detected yet for this project.")

# --- Decisions & Dependencies -------------------------------------------------
with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Decisions")
        resp = requests.get(f"{API_BASE}/projects/{project}/decisions")
        if resp.ok and resp.json():
            df = pd.DataFrame(resp.json())[["id", "description", "decided_by", "date"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No decisions recorded yet.")

        st.subheader("Open issues")
        resp = requests.get(f"{API_BASE}/projects/{project}/open-issues")
        if resp.ok and resp.json():
            df = pd.DataFrame(resp.json())[["id", "description", "raised_by", "status"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No open issues recorded yet.")

    with c2:
        st.subheader("Dependencies")
        resp = requests.get(f"{API_BASE}/projects/{project}/dependencies")
        if resp.ok and resp.json():
            df = pd.DataFrame(resp.json())[["id", "description", "depends_on"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No dependencies recorded yet.")

# --- Q&A -----------------------------------------------------------------
with tabs[4]:
    st.subheader("Ask about this project")
    question = st.text_input("e.g. What are the overdue action items for this project?")
    if st.button("Ask") and question:
        with st.spinner("Retrieving relevant context and generating an answer..."):
            resp = requests.post(f"{API_BASE}/qna", json={"project": project, "question": question})
        if resp.ok:
            data = resp.json()
            st.markdown(data["answer"])
            if data["sources"]:
                with st.expander(f"Sources ({len(data['sources'])})"):
                    for i, s in enumerate(data["sources"], start=1):
                        st.markdown(f"**[{i}] {s['document']}**")
                        st.caption(s["snippet"])
        else:
            st.error(resp.text)

# --- Weekly report -------------------------------------------------------
with tabs[5]:
    st.subheader("Weekly status report")
    if st.button("Generate report"):
        with st.spinner("Aggregating structured data and generating report..."):
            resp = requests.get(f"{API_BASE}/projects/{project}/weekly-report")
        if resp.ok:
            st.markdown(resp.json()["report_markdown"])
        else:
            st.error(resp.text)

# --- Approvals -------------------------------------------------------------
with tabs[6]:
    st.subheader("Pending status-change approvals")
    st.caption("The system never changes a task's status on its own — every proposed change waits here for a human to approve or reject.")
    resp = requests.get(f"{API_BASE}/approvals/pending")
    if resp.ok:
        pending = resp.json()
        if not pending:
            st.info("Nothing pending review.")
        for a in pending:
            with st.container(border=True):
                st.write(f"**Action item #{a['action_item_id']}**: {a['old_status']} → {a['proposed_status']}")
                st.caption(f"Requested by {a['requested_by']}" + (f" — {a['reason']}" if a.get("reason") else ""))
                bc1, bc2, reviewer_col = st.columns([1, 1, 2])
                reviewer = reviewer_col.text_input("Reviewer", value="you", key=f"rev_{a['id']}")
                if bc1.button("Approve", key=f"approve_{a['id']}"):
                    requests.post(f"{API_BASE}/approvals/{a['id']}/review",
                                  json={"approved": True, "reviewer": reviewer})
                    st.rerun()
                if bc2.button("Reject", key=f"reject_{a['id']}"):
                    requests.post(f"{API_BASE}/approvals/{a['id']}/review",
                                  json={"approved": False, "reviewer": reviewer})
                    st.rerun()
