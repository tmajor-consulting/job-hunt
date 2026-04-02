import json
import sqlite3
from datetime import date, datetime, timezone
from html import escape

import pandas as pd
import streamlit as st

from db import (
    add_application,
    add_event,
    apply_to_job,
    delete_application,
    delete_event,
    dismiss_job,
    fetch_applications,
    fetch_new_jobs,
    get_connection,
    get_events,
    init_db,
    update_event,
)

# ── Constants ────────────────────────────────────────────────────────────────

STAGES = [
    ("cv_sent",        "📤 CV Sent"),
    ("phone_screen",   "📞 Phone Screen"),
    ("round_1",        "🔵 Round 1"),
    ("round_2",        "🔵 Round 2"),
    ("round_3",        "🔵 Round 3"),
    ("offer",          "🎉 Offer"),
    ("offer_accepted", "✅ Accepted"),
    ("offer_declined", "🚫 Declined Offer"),
    ("rejected_cv",    "❌ Rejected (CV)"),
    ("rejected_later", "❌ Rejected (Later)"),
    ("withdrawn",      "↩️ Withdrawn"),
]
STAGE_MAP = {k: v for k, v in STAGES}
STAGE_KEYS = [k for k, _ in STAGES]
ACTIVE_STAGES = {"cv_sent", "phone_screen", "round_1", "round_2", "round_3", "offer"}

STAGE_COLORS = {
    "cv_sent":        "#3b82f6",
    "phone_screen":   "#8b5cf6",
    "round_1":        "#06b6d4",
    "round_2":        "#0891b2",
    "round_3":        "#0e7490",
    "offer":          "#10b981",
    "offer_accepted": "#059669",
    "offer_declined": "#6b7280",
    "rejected_cv":    "#ef4444",
    "rejected_later": "#f97316",
    "withdrawn":      "#9ca3af",
}

CSS = """
<style>
/* Page background */
[data-testid="stAppViewContainer"] { background: #0f172a; }
[data-testid="stSidebar"] { background: #1e293b; }
[data-testid="stHeader"] { background: transparent; }

/* Hide default streamlit footer/menu */
#MainMenu, footer { visibility: hidden; }

/* Typography */
h1 { color: #f1f5f9 !important; font-weight: 700 !important; letter-spacing: -0.5px; }
h2, h3 { color: #e2e8f0 !important; font-weight: 600 !important; }
p, label, div { color: #cbd5e1; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="metric-container"] label { color: #94a3b8 !important; font-size: 13px !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f1f5f9 !important;
    font-size: 28px !important;
    font-weight: 700 !important;
}

/* Tabs */
[data-testid="stTabs"] button {
    color: #94a3b8 !important;
    font-weight: 500;
    font-size: 14px;
    border-radius: 8px 8px 0 0;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #f1f5f9 !important;
    border-bottom: 2px solid #3b82f6 !important;
}

/* Containers / cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 12px !important;
}

/* Buttons */
[data-testid="stButton"] button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    transition: all 0.15s ease;
}
[data-testid="stButton"] button[kind="primary"] {
    background: #3b82f6 !important;
    border: none !important;
    color: white !important;
}
[data-testid="stButton"] button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid #475569 !important;
    color: #94a3b8 !important;
}

/* Selectbox / inputs */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: #0f172a !important;
    border: 1px solid #334155 !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}

/* Dataframe */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
iframe { border-radius: 10px !important; }

/* Expander */
[data-testid="stExpander"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
}

/* Divider */
hr { border-color: #334155 !important; }

/* Compact icon buttons (edit/delete in timeline) */
[data-testid="stButton"] button[title="Edit step"],
[data-testid="stButton"] button[title="Delete step"],
[data-testid="stButton"] button[title="Confirm delete"],
[data-testid="stButton"] button[title="Cancel"] {
    padding: 2px 4px !important;
    font-size: 11px !important;
    min-height: 0 !important;
    height: 26px !important;
    line-height: 1 !important;
}

/* Sidebar nav radio */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    color: #94a3b8 !important;
    padding: 6px 0;
    font-size: 14px;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { color: #f1f5f9 !important; }

/* Info / success / error boxes */
[data-testid="stAlert"] { border-radius: 10px !important; }
</style>
"""


def stage_badge(stage_key: str) -> str:
    label = STAGE_MAP.get(stage_key, stage_key)
    color = STAGE_COLORS.get(stage_key, "#6b7280")
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600;">{label}</span>'
    )


# ── DB connection (cached for the lifetime of the Streamlit session) ───────────

@st.cache_resource
def get_conn() -> sqlite3.Connection:
    conn = get_connection()
    init_db(conn)
    return conn


# ── DataFrame builders (UI layer — thin wrappers over db.py queries) ──────────

def get_new_jobs(conn) -> pd.DataFrame:
    rows = fetch_new_jobs(conn)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["tech_stack"] = df["tech_stack"].apply(
        lambda v: ", ".join(json.loads(v)) if v else "—"
    )
    return df


def get_applications(conn) -> pd.DataFrame:
    rows = fetch_applications(conn)
    if not rows:
        return pd.DataFrame(columns=["id", "company", "title", "job_url",
                                      "current_stage", "applied_at", "updated_at", "notes"])
    df = pd.DataFrame(rows)
    df["stage_label"] = df["current_stage"].map(STAGE_MAP)
    return df


# ── Views ─────────────────────────────────────────────────────────────────────

def view_new_jobs(conn):
    df = get_new_jobs(conn)
    if df.empty:
        st.info("No new jobs. Run the scraper to fetch the latest listings.")
        return

    for _, job in df.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                url = job.get("job_url", "")
                title_md = f"[{job['title']}]({url})" if url else job["title"]
                st.markdown(f"##### {title_md}")
                loc = escape(job.get("location", ""))
                work = "Remote" if job.get("is_remote") else "On-site / Hybrid"
                st.markdown(
                    f'<span style="color:#94a3b8;font-size:13px;">🏢 {escape(job["company"])}'
                    f'&nbsp;&nbsp;📍 {loc}&nbsp;&nbsp;💼 {work}</span>',
                    unsafe_allow_html=True,
                )
                tech = escape(job.get("tech_stack", "—"))
                st.markdown(
                    f'<span style="color:#64748b;font-size:12px;">🛠 {tech}</span>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.write("")
                if st.button("✅ Applied", key=f"apply_{job['id']}", use_container_width=True):
                    apply_to_job(conn, dict(job))
                    st.toast(f"Added {job['company']} to tracker!", icon="✅")
                    st.rerun()
                if st.button("Dismiss", key=f"dismiss_{job['id']}", use_container_width=True):
                    dismiss_job(conn, job["id"])
                    st.rerun()


def _render_add_manually(conn) -> None:
    with st.expander("➕ Add application manually"):
        mc1, mc2, mc3, mc4 = st.columns([2, 2, 3, 1], vertical_alignment="bottom")
        company_in = mc1.text_input("Company", key="manual_company", placeholder="Company name")
        title_in   = mc2.text_input("Title",   key="manual_title",   placeholder="Job title")
        url_in     = mc3.text_input("URL",     key="manual_url",     placeholder="Job posting URL (optional)")
        applied_in = mc4.date_input("Applied", key="manual_date",    value=date.today(),
                                    label_visibility="collapsed")
        if st.button("Add application", key="manual_submit", type="primary"):
            if not company_in.strip() or not title_in.strip():
                st.warning("Company and title are required.")
            else:
                add_application(conn, company_in.strip(), title_in.strip(),
                                url_in.strip(), str(applied_in))
                st.toast(f"Added {company_in.strip()}!", icon="✅")
                st.rerun()


def view_dashboard(conn):
    df = get_applications(conn)

    total    = len(df)
    active   = len(df[df["current_stage"].isin(ACTIVE_STAGES)]) if total else 0
    rejected = len(df[df["current_stage"].isin({"rejected_cv", "rejected_later"})]) if total else 0
    offers   = len(df[df["current_stage"].isin({"offer", "offer_accepted"})]) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Applied", total)
    c2.metric("In Progress", active)
    c3.metric("Rejected", rejected)
    c4.metric("Offers", offers)

    st.divider()

    _render_add_manually(conn)

    st.markdown("&nbsp;", unsafe_allow_html=True)

    if df.empty:
        st.info("No applications yet. Check the New Jobs tab or add one manually above.")
        return

    # ── Search + filter ──
    fc1, fc2, fc3 = st.columns([3, 2, 1], vertical_alignment="bottom")
    search = fc1.text_input("", placeholder="🔍  Search company or title...", label_visibility="collapsed")
    stage_filter = fc2.multiselect("", options=STAGE_KEYS,
                                   format_func=lambda k: STAGE_MAP[k],
                                   placeholder="Filter by stage",
                                   label_visibility="collapsed")
    open_only = fc3.toggle("Open only", value=False)

    filtered = df.copy()
    if open_only:
        filtered = filtered[filtered["current_stage"].isin(ACTIVE_STAGES)]
    if search:
        mask = (filtered["company"].str.contains(search, case=False, na=False) |
                filtered["title"].str.contains(search, case=False, na=False))
        filtered = filtered[mask]
    if stage_filter:
        filtered = filtered[filtered["current_stage"].isin(stage_filter)]

    # ── Application list ──
    st.markdown("&nbsp;", unsafe_allow_html=True)
    for _, row in filtered.iterrows():
        is_selected = st.session_state.get("selected_app") == row["id"]

        with st.container(border=True):
            h1, h2, h3 = st.columns([3, 2, 1])
            with h1:
                st.markdown(f"**{escape(str(row['company']))}**")
                st.markdown(
                    f'<span style="color:#94a3b8;font-size:13px;">{escape(str(row["title"]))}</span>',
                    unsafe_allow_html=True,
                )
            with h2:
                st.markdown(stage_badge(row["current_stage"]), unsafe_allow_html=True)
                st.markdown(
                    f'<span style="color:#64748b;font-size:12px;">'
                    f'Applied {escape(str(row.get("applied_at","—")))}'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Updated {escape(str(row.get("updated_at","—"))[:10])}'
                    f'</span>',
                    unsafe_allow_html=True,
                )
            with h3:
                label = "▲ Close" if is_selected else "Details"
                if st.button(label, key=f"sel_{row['id']}", use_container_width=True):
                    st.session_state["selected_app"] = None if is_selected else row["id"]
                    st.rerun()

        # ── Detail panel ──
        if is_selected:
            with st.container(border=True):
                if row.get("job_url"):
                    st.markdown(f"🔗 [View job posting]({row['job_url']})")

                events = get_events(conn, row["id"])
                if events:
                    st.markdown("**Timeline**")
                    for i, ev in enumerate(events):
                        color = STAGE_COLORS.get(ev["stage"], "#6b7280")
                        connector = "│" if i < len(events) - 1 else " "
                        is_editing_ev = st.session_state.get("editing_event") == ev["id"]

                        if is_editing_ev:
                            ec1, ec2, ec3, ec4 = st.columns([2, 2, 3, 1])
                            edit_stage = ec1.selectbox(
                                "Stage", STAGE_KEYS, format_func=lambda k: STAGE_MAP[k],
                                index=STAGE_KEYS.index(ev["stage"]) if ev["stage"] in STAGE_KEYS else 0,
                                key=f"edit_stage_{ev['id']}", label_visibility="collapsed",
                            )
                            edit_date = ec2.date_input(
                                "Date", value=date.fromisoformat(ev["event_date"]),
                                key=f"edit_date_{ev['id']}", label_visibility="collapsed",
                            )
                            edit_notes = ec3.text_input(
                                "Notes", value=ev.get("notes") or "",
                                key=f"edit_notes_{ev['id']}", label_visibility="collapsed",
                                placeholder="Notes...",
                            )
                            with ec4:
                                if st.button("Save", key=f"edit_save_{ev['id']}", type="primary", use_container_width=True):
                                    update_event(conn, ev["id"], row["id"], edit_stage, str(edit_date), edit_notes)
                                    st.session_state.pop("editing_event", None)
                                    st.toast("Step updated!", icon="✅")
                                    st.rerun()
                                if st.button("Cancel", key=f"edit_cancel_{ev['id']}", use_container_width=True):
                                    st.session_state.pop("editing_event", None)
                                    st.rerun()
                        else:
                            note_str = f" — {escape(ev['notes'])}" if ev.get("notes") else ""
                            stage_label = escape(STAGE_MAP.get(ev["stage"], ev["stage"]))
                            pending_del = st.session_state.get("confirm_del_event") == ev["id"]
                            dc1, dc2, dc3 = st.columns([8, 0.6, 0.6])
                            with dc1:
                                st.markdown(
                                    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:2px;">'
                                    f'<span style="color:{color};font-size:18px;">●</span>'
                                    f'<span style="color:#e2e8f0;font-size:13px;">{stage_label}</span>'
                                    f'<span style="color:#64748b;font-size:12px;">{escape(ev["event_date"])}{note_str}</span>'
                                    f'</div>'
                                    f'<div style="margin-left:9px;color:#334155;font-size:11px;">{connector}</div>',
                                    unsafe_allow_html=True,
                                )
                            with dc2:
                                if pending_del:
                                    if st.button("✓", key=f"del_confirm_{ev['id']}", help="Confirm delete", use_container_width=True):
                                        delete_event(conn, ev["id"], row["id"])
                                        st.session_state.pop("confirm_del_event", None)
                                        st.rerun()
                                else:
                                    if st.button("✏️", key=f"edit_btn_{ev['id']}", help="Edit step", use_container_width=True):
                                        st.session_state["editing_event"] = ev["id"]
                                        st.rerun()
                            with dc3:
                                if pending_del:
                                    if st.button("✗", key=f"del_cancel_{ev['id']}", help="Cancel", use_container_width=True):
                                        st.session_state.pop("confirm_del_event", None)
                                        st.rerun()
                                else:
                                    if st.button("🗑", key=f"del_btn_{ev['id']}", help="Delete step", use_container_width=True):
                                        st.session_state["confirm_del_event"] = ev["id"]
                                        st.rerun()

                if row.get("notes"):
                    st.markdown(
                        f'<div style="margin-top:8px;padding:10px 14px;background:#0f172a;'
                        f'border-radius:8px;color:#94a3b8;font-size:13px;">📝 {escape(str(row["notes"]))}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown("&nbsp;", unsafe_allow_html=True)
                st.markdown("**Add stage**")
                uc1, uc2, uc3, uc4 = st.columns([2, 2, 3, 1], vertical_alignment="bottom")
                new_stage = uc1.selectbox("Stage", STAGE_KEYS,
                                          format_func=lambda k: STAGE_MAP[k],
                                          key=f"ns_{row['id']}",
                                          label_visibility="collapsed")
                event_date = uc2.date_input("Date", value=date.today(),
                                            key=f"nd_{row['id']}",
                                            label_visibility="collapsed")
                new_notes = uc3.text_input("Notes", key=f"nn_{row['id']}",
                                           label_visibility="collapsed",
                                           placeholder="Notes (optional)...")
                if uc4.button("Add", key=f"save_{row['id']}", type="primary", use_container_width=True):
                    add_event(conn, row["id"], new_stage, str(event_date), new_notes)
                    st.toast("Stage added!", icon="✅")
                    st.rerun()

                with st.expander("🗑 Delete application"):
                    if st.button("Confirm delete", key=f"del_{row['id']}", type="secondary"):
                        delete_application(conn, row["id"])
                        st.session_state["selected_app"] = None
                        st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Job Hunt", page_icon="💼", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

conn = get_conn()

st.markdown("# 💼 Job Hunt")

new_jobs_df = get_new_jobs(conn)
new_count = len(new_jobs_df)
new_tab_label = f"🆕 New Jobs ({new_count})" if new_count else "🆕 New Jobs"

tab1, tab2 = st.tabs(["📊 Applications", new_tab_label])

with tab1:
    view_dashboard(conn)

with tab2:
    view_new_jobs(conn)
