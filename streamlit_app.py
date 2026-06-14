"""Simple Streamlit UI for the Job Agent MVP.

Run the FastAPI backend first:
    .venv/bin/uvicorn app.main:app --reload --port 8077

Then run this UI:
    .venv/bin/streamlit run streamlit_app.py
"""

import requests
import streamlit as st

st.set_page_config(page_title="Job Agent", layout="wide")

DEFAULT_API_URL = "http://127.0.0.1:8077"


def api_get(path, **kwargs):
    kwargs.setdefault("timeout", 60)
    return requests.get(f"{st.session_state.api_url}{path}", **kwargs)


def api_post(path, **kwargs):
    kwargs.setdefault("timeout", 60)
    return requests.post(f"{st.session_state.api_url}{path}", **kwargs)


def api_put(path, **kwargs):
    kwargs.setdefault("timeout", 60)
    return requests.put(f"{st.session_state.api_url}{path}", **kwargs)


if "api_url" not in st.session_state:
    st.session_state.api_url = DEFAULT_API_URL
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# ---------------------------------------------------------------------------
# Sidebar: connection + user
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Connection")
    st.session_state.api_url = st.text_input("API base URL", value=st.session_state.api_url)

    st.header("User")
    with st.expander("Create new user"):
        new_name = st.text_input("Name", key="new_name")
        new_email = st.text_input("Email", key="new_email")
        if st.button("Create user"):
            resp = api_post("/users", json={"name": new_name, "email": new_email})
            if resp.ok:
                st.session_state.user_id = resp.json()["id"]
                st.success(f"Created user id={st.session_state.user_id}")
            else:
                st.error(resp.json().get("detail", resp.text))

    user_id_input = st.number_input(
        "User ID", min_value=1, step=1, value=st.session_state.user_id or 1
    )
    st.session_state.user_id = int(user_id_input)

user_id = st.session_state.user_id

st.title("Job Agent")

tab_profile, tab_resume, tab_search, tab_jobs, tab_assistant, tab_tailor = st.tabs(
    ["Profile", "Resume", "Search", "Ranked Jobs", "AI Assistant", "Tailor Resume"]
)

# ---------------------------------------------------------------------------
# Profile tab
# ---------------------------------------------------------------------------
with tab_profile:
    st.subheader("Career profile")

    resp = api_get(f"/users/{user_id}/profile")
    if not resp.ok:
        st.warning("Profile not found yet. Create the user in the sidebar first.")
        profile = {}
    else:
        profile = resp.json()

    def list_to_text(items):
        return ", ".join(items or [])

    def text_to_list(text):
        return [s.strip() for s in text.split(",") if s.strip()]

    with st.form("profile_form"):
        target_roles = st.text_input(
            "Target roles (comma-separated)",
            value=list_to_text(profile.get("target_roles")),
            help='e.g. "Generative AI Engineer, AI/ML Architect"',
        )
        core_skills = st.text_input(
            "Core skills (comma-separated)", value=list_to_text(profile.get("core_skills"))
        )
        domains = st.text_input(
            "Preferred domains (comma-separated)", value=list_to_text(profile.get("domains"))
        )
        avoid_skills = st.text_input(
            "Skills/keywords to avoid (comma-separated)",
            value=list_to_text(profile.get("avoid_skills")),
        )
        preferred_locations = st.text_input(
            "Preferred locations (comma-separated)",
            value=list_to_text(profile.get("preferred_locations")),
        )
        preferred_companies = st.text_input(
            "Preferred companies (comma-separated)",
            value=list_to_text(profile.get("preferred_companies")),
        )
        excluded_companies = st.text_input(
            "Excluded companies (comma-separated)",
            value=list_to_text(profile.get("excluded_companies")),
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            min_salary = st.number_input(
                "Minimum salary", min_value=0, value=int(profile.get("min_salary") or 0), step=1000
            )
        with col2:
            work_mode = st.selectbox(
                "Work mode",
                ["remote", "hybrid", "onsite", "any"],
                index=["remote", "hybrid", "onsite", "any"].index(profile.get("work_mode") or "remote"),
            )
        with col3:
            seniority = st.text_input("Seniority", value=profile.get("seniority") or "")

        submitted = st.form_submit_button("Save profile")

    if submitted:
        payload = {
            "target_roles": text_to_list(target_roles),
            "core_skills": text_to_list(core_skills),
            "domains": text_to_list(domains),
            "avoid_skills": text_to_list(avoid_skills),
            "preferred_locations": text_to_list(preferred_locations),
            "preferred_companies": text_to_list(preferred_companies),
            "excluded_companies": text_to_list(excluded_companies),
            "min_salary": float(min_salary),
            "work_mode": work_mode,
            "seniority": seniority,
        }
        resp = api_put(f"/users/{user_id}/profile", json=payload)
        if resp.ok:
            st.success("Profile saved.")
        else:
            st.error(resp.json().get("detail", resp.text))

    if profile.get("skill_weights"):
        st.subheader("Learned skill weights (from feedback)")
        st.json(profile["skill_weights"])

# ---------------------------------------------------------------------------
# Resume tab
# ---------------------------------------------------------------------------
with tab_resume:
    st.subheader("Upload resume (PDF)")
    st.caption("Extracted skills are merged into your core skills automatically.")

    uploaded = st.file_uploader("Resume PDF", type=["pdf"])
    if uploaded is not None and st.button("Upload & parse resume"):
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
        resp = api_post(f"/users/{user_id}/resume", files=files)
        if resp.ok:
            updated_profile = resp.json()
            st.success("Resume parsed. Core skills updated:")
            st.write(updated_profile.get("core_skills"))
        else:
            st.error(resp.json().get("detail", resp.text))

# ---------------------------------------------------------------------------
# Search tab
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Run job discovery")
    st.caption("Searches RemoteOK and the Swedish JobTech (Arbetsformedlingen) feeds based on your profile.")

    if st.button("Run search now", type="primary"):
        with st.spinner("Searching and scoring jobs..."):
            resp = api_post(f"/users/{user_id}/search")
        if resp.ok:
            jobs = resp.json()
            st.success(f"Found {len(jobs)} jobs. See the 'Ranked Jobs' tab.")
        else:
            st.error(resp.json().get("detail", resp.text))

# ---------------------------------------------------------------------------
# Ranked jobs tab
# ---------------------------------------------------------------------------
with tab_jobs:
    st.subheader("Ranked jobs")

    min_score = st.slider("Minimum score", 0, 100, 0)
    resp = api_get(f"/users/{user_id}/jobs", params={"min_score": min_score})

    if not resp.ok:
        st.warning("Could not load jobs. Create a profile and run a search first.")
    else:
        jobs = resp.json()
        if not jobs:
            st.info("No jobs yet. Go to the 'Search' tab and run a search.")

        feedback_options = [
            "(no feedback)", "applied", "shortlisted", "skip", "rejected_salary", "rejected_location",
        ]

        for job in jobs:
            title = job["title"]
            company = job.get("company") or "Unknown company"
            location = job.get("location") or "-"
            score = job["score"]
            status = job.get("feedback_status")

            header = f"**{score:.1f}** — {title} @ {company} ({location})"
            if status:
                header += f"  ·  _feedback: {status}_"

            with st.expander(header):
                st.write(f"Source: `{job['source']}`")
                if job.get("url"):
                    st.write(f"[Open job posting]({job['url']})")
                if job.get("posted_at"):
                    st.write(f"Posted: {job['posted_at']}")

                st.write("Score breakdown:")
                st.json(job["score_breakdown"])

                current_index = (
                    feedback_options.index(status) if status in feedback_options else 0
                )
                choice = st.selectbox(
                    "Feedback",
                    feedback_options,
                    index=current_index,
                    key=f"feedback_{job['id']}",
                )
                if st.button("Save feedback", key=f"save_{job['id']}"):
                    if choice == "(no feedback)":
                        st.warning("Pick a feedback status first.")
                    else:
                        resp = api_post(
                            f"/users/{user_id}/jobs/{job['id']}/feedback",
                            json={"status": choice},
                        )
                        if resp.ok:
                            st.success("Feedback saved.")
                        else:
                            st.error(resp.json().get("detail", resp.text))

# ---------------------------------------------------------------------------
# AI Assistant tab
# ---------------------------------------------------------------------------
with tab_assistant:
    st.subheader("AI job search assistant")
    st.caption(
        "Ask the assistant to find new jobs, explain matches, tailor a resume, "
        "or record feedback. It can call the discovery, scoring, resume, and "
        "feedback agents on your behalf."
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = None

    for role, content in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(content)

    if st.button("Reset conversation"):
        st.session_state.chat_history = []
        st.session_state.chat_session_id = None
        st.rerun()

    prompt = st.chat_input("e.g. Find new jobs for me and explain the top 3")
    if prompt:
        st.session_state.chat_history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                resp = api_post(
                    "/agents/chat",
                    json={
                        "user_id": user_id,
                        "message": prompt,
                        "session_id": st.session_state.chat_session_id,
                    },
                    timeout=180,
                )
            if resp.ok:
                data = resp.json()
                st.markdown(data["reply"])
                st.caption(f"cost: ${data.get('cost_usd', 0):.4f}")
                st.session_state.chat_session_id = data.get("session_id")
                st.session_state.chat_history.append(("assistant", data["reply"]))
            else:
                error = resp.json().get("detail", resp.text)
                st.error(error)
                st.session_state.chat_history.append(("assistant", f"Error: {error}"))

# ---------------------------------------------------------------------------
# Tailor Resume tab
# ---------------------------------------------------------------------------
with tab_tailor:
    st.subheader("Tailor your resume to a job")
    st.caption("Generates a .docx resume rewritten to emphasize the parts relevant to the selected job.")

    min_score_tailor = st.slider("Minimum score", 0, 100, 0, key="tailor_min_score")
    resp = api_get(f"/users/{user_id}/jobs", params={"min_score": min_score_tailor})

    if not resp.ok:
        st.warning("Could not load jobs. Create a profile and run a search first.")
    else:
        jobs = resp.json()
        if not jobs:
            st.info("No jobs yet. Go to the 'Search' tab and run a search.")
        else:
            options = {
                f"{job['score']:.1f} — {job['title']} @ {job.get('company') or 'Unknown'}": job["id"]
                for job in jobs
            }
            label = st.selectbox("Select a job", list(options.keys()))
            job_id = options[label]

            instructions = st.text_area(
                "What would you like to change or emphasize? (optional)",
                placeholder=(
                    "e.g. Put my AWS experience first, make the summary shorter, "
                    "emphasize leadership, drop the 2018 internship..."
                ),
            )

            if st.button("Generate tailored resume", type="primary"):
                with st.spinner("Tailoring resume..."):
                    resp = api_post(
                        f"/agents/tailor-resume/{user_id}/{job_id}",
                        json={"instructions": instructions},
                        timeout=180,
                    )
                if resp.ok:
                    data = resp.json()
                    if "tailored_resume_path" in data:
                        st.session_state.tailored_resume = data
                        st.session_state.tailored_resume_job_id = job_id
                    else:
                        st.error(f"Agent did not return a resume: {data}")
                else:
                    st.error(resp.json().get("detail", resp.text))

            data = st.session_state.get("tailored_resume")
            if data and st.session_state.get("tailored_resume_job_id") == job_id:
                st.success("Tailored resume generated.")
                if data.get("summary_of_changes"):
                    st.write("**Summary of changes:**")
                    st.write(data["summary_of_changes"])
                st.caption(f"cost: ${data.get('_cost_usd', 0):.4f}")

                download_resp = api_get(f"/agents/tailored-resume/{user_id}/{job_id}")
                if download_resp.ok:
                    st.download_button(
                        "Download .docx",
                        data=download_resp.content,
                        file_name=f"resume_{user_id}_{job_id}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )

                preview = data.get("preview")
                if preview:
                    st.markdown("---")
                    st.markdown("### Preview")
                    if preview.get("contact_name"):
                        st.markdown(f"## {preview['contact_name']}")
                    if preview.get("summary"):
                        st.markdown("**Summary**")
                        st.write(preview["summary"])
                    if preview.get("skills"):
                        st.markdown("**Skills**")
                        st.write(", ".join(preview["skills"]))
                    if preview.get("experience"):
                        st.markdown("**Experience**")
                        for job in preview["experience"]:
                            title = job.get("title", "")
                            company = job.get("company", "")
                            dates = job.get("dates", "")
                            header = f"**{title} — {company}**" if company else f"**{title}**"
                            if dates:
                                header += f"  _{dates}_"
                            st.markdown(header)
                            for bullet in job.get("bullets") or []:
                                st.markdown(f"- {bullet}")
                    if preview.get("education"):
                        st.markdown("**Education**")
                        for entry in preview["education"]:
                            st.markdown(f"- {entry}")
