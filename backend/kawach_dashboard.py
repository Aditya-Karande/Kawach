"""
kawach_dashboard.py
---------------------
A quick Streamlit dashboard for TESTING/DEMO purposes — lets you visually
confirm the whole pipeline is working: events flowing in, risk labels being
assigned, and alerts being created by the correlation engine + LLM.

This is NOT the final polished parent dashboard (that's a separate,
proper frontend project) — this is a fast way to SEE your data without
manually running sqlite3 queries every time.

Run it with:
    pip install streamlit pandas requests
    streamlit run kawach_dashboard.py

Make sure your FastAPI backend is running separately (uvicorn main:app)
for the monitoring toggle button to work — everything else reads the
database file directly.
"""

import sqlite3
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Kawach — Test Dashboard", page_icon="🛡️", layout="wide")

DEFAULT_DB_PATH = "database.db"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"

RISK_COLORS = {
    "high": "#ef4444",
    "medium": "#f59e0b",
    "low": "#84cc16",
}
RISK_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}


# -----------------------------
# Sidebar — config + controls
# -----------------------------
st.sidebar.title("🛡️ Kawach")
st.sidebar.caption("Test dashboard — reads your local database.db directly")

db_path = st.sidebar.text_input("Database file path", value=DEFAULT_DB_PATH)
backend_url = st.sidebar.text_input("Backend URL (for monitoring toggle)", value=DEFAULT_BACKEND_URL)

auto_refresh = st.sidebar.checkbox("Auto-refresh every 5s", value=False)


# -----------------------------
# DB helpers
# -----------------------------
def get_connection():
    return sqlite3.connect(db_path)


def load_events(child_id_filter=None):
    conn = get_connection()
    query = "SELECT id, child_id, type, content, risk_label, risk_confidence, timestamp FROM events ORDER BY timestamp DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    if child_id_filter and child_id_filter != "All":
        df = df[df["child_id"] == child_id_filter]
    return df


def load_alerts(child_id_filter=None):
    conn = get_connection()
    query = "SELECT id, child_id, explanation, risk_level, timestamp FROM alert ORDER BY timestamp DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    if child_id_filter and child_id_filter != "All":
        df = df[df["child_id"] == child_id_filter]
    return df


def load_children():
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT child_id, monitoring_status FROM children", conn)
    except Exception:
        df = pd.DataFrame(columns=["child_id", "monitoring_status"])
    conn.close()
    return df


def get_all_child_ids():
    conn = get_connection()
    try:
        ids = pd.read_sql_query(
            "SELECT DISTINCT child_id FROM events "
            "UNION SELECT DISTINCT child_id FROM alert "
            "UNION SELECT DISTINCT child_id FROM children",
            conn,
        )["child_id"].tolist()
    except Exception:
        ids = []
    conn.close()
    return sorted(ids)


def format_time_ago(ts_str):
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
        diff = now - ts
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{int(seconds // 60)} min ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)} hr ago"
        else:
            return f"{int(seconds // 86400)} day(s) ago"
    except Exception:
        return ts_str


# -----------------------------
# Try to connect, show a clear error if the DB isn't found
# -----------------------------
try:
    conn_test = get_connection()
    conn_test.execute("SELECT 1 FROM events LIMIT 1")
    conn_test.close()
except Exception as e:
    st.error(
        f"Couldn't read `{db_path}`. Make sure this dashboard is running in the "
        f"same folder as your backend's database.db, or fix the path in the sidebar.\n\nError: {e}"
    )
    st.stop()


# -----------------------------
# Child selector
# -----------------------------
all_child_ids = get_all_child_ids()
child_options = ["All"] + all_child_ids
selected_child = st.sidebar.selectbox("Child", child_options)

# -----------------------------
# Monitoring toggle (calls the REAL backend API)
# -----------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Monitoring control")

if selected_child != "All":
    toggle_child_id = st.sidebar.text_input("Child ID to toggle", value=selected_child)
else:
    toggle_child_id = st.sidebar.text_input("Child ID to toggle", value=all_child_ids[0] if all_child_ids else "")

col_on, col_off = st.sidebar.columns(2)
if col_on.button("Turn ON", width='stretch'):
    try:
        r = requests.post(f"{backend_url}/toggle-monitoring", json={"child_id": toggle_child_id, "status": "on"}, timeout=5)
        st.sidebar.success(f"Status: {r.json().get('monitoring_status')}")
    except Exception as e:
        st.sidebar.error(f"Couldn't reach backend: {e}")

if col_off.button("Turn OFF", width='stretch'):
    try:
        r = requests.post(f"{backend_url}/toggle-monitoring", json={"child_id": toggle_child_id, "status": "off"}, timeout=5)
        st.sidebar.success(f"Status: {r.json().get('monitoring_status')}")
    except Exception as e:
        st.sidebar.error(f"Couldn't reach backend: {e}")


# -----------------------------
# Main content
# -----------------------------
st.title("🛡️ Kawach — Test Dashboard")
st.caption("This is a TESTING view — not the final parent-facing design. It reads your database directly so you can confirm the whole pipeline is working.")

events_df = load_events(selected_child)
alerts_df = load_alerts(selected_child)
children_df = load_children()

# --- Top stats row ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total events", len(events_df))
risky_count = len(events_df[events_df["risk_label"].notna() & (events_df["risk_label"] != "safe")])
col2.metric("Risky events", risky_count)
col3.metric("Alerts triggered", len(alerts_df))
high_risk_alerts = len(alerts_df[alerts_df["risk_level"] == "high"]) if len(alerts_df) else 0
col4.metric("High-risk alerts", high_risk_alerts)

st.markdown("---")

# --- Alerts feed ---
st.subheader("🚨 Alerts")
if alerts_df.empty:
    st.info("No alerts yet. Send 2+ risky events for the same child within 20 minutes to trigger one.")
else:
    for _, alert in alerts_df.iterrows():
        risk = alert["risk_level"]
        emoji = RISK_EMOJI.get(risk, "⚪")
        color = RISK_COLORS.get(risk, "#999")
        is_long_term = "long-term pattern" in (alert["explanation"] or "")
        pattern_badge = "🐢 Long-term pattern" if is_long_term else "⚡ Short-term burst"

        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{emoji} {risk.upper()} RISK** — child: `{alert['child_id']}` &nbsp;|&nbsp; {pattern_badge}")
                st.write(alert["explanation"])
            with c2:
                st.caption(format_time_ago(alert["timestamp"]))
                st.caption(alert["timestamp"])

st.markdown("---")

# --- Raw events log ---
st.subheader("📋 Raw activity log")

filter_col1, filter_col2 = st.columns(2)
show_only_risky = filter_col1.checkbox("Show only risky events", value=False)
event_type_filter = filter_col2.multiselect("Event type", options=events_df["type"].unique().tolist() if not events_df.empty else [])

display_df = events_df.copy()
if show_only_risky:
    display_df = display_df[display_df["risk_label"].notna() & (display_df["risk_label"] != "safe")]
if event_type_filter:
    display_df = display_df[display_df["type"].isin(event_type_filter)]

if display_df.empty:
    st.info("No events match the current filters.")
else:
    def highlight_risk(row):
        label = row["risk_label"]
        if label and label != "safe":
            return ["background-color: #fee2e2"] * len(row)
        return [""] * len(row)

    st.dataframe(
        display_df.style.apply(highlight_risk, axis=1),
        width='stretch',
        hide_index=True,
    )

st.markdown("---")

# --- Children / monitoring status table ---
st.subheader("👤 Children being monitored")
if children_df.empty:
    st.info("No children registered yet (this table populates after the first /toggle-monitoring call for a child_id).")
else:
    st.dataframe(children_df, width='stretch', hide_index=True)

# --- Auto-refresh ---
if auto_refresh:
    time.sleep(5)
    st.rerun()