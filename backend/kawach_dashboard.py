"""
kawach_dashboard.py
---------------------
A quick Streamlit dashboard for TESTING/DEMO purposes — lets you visually
confirm the whole pipeline is working: signals flowing in, weighted
scores being computed, and tier-3 alerts being created by the
correlation engine + LLM.

This is NOT the final polished parent dashboard (that's a separate,
proper frontend project — React later) — this is a fast way to SEE your
data without manually running sqlite3 queries every time.

Run it with:
    pip install streamlit pandas requests
    streamlit run kawach_dashboard.py

Make sure your FastAPI backend is running separately (uvicorn main:app)
in the same folder — the monitoring toggle, alert feed, and child list
now all go through the real API (they require a logged-in parent),
only the raw event/alert tables below read database.db directly.
"""

import json
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

TIER_LABEL = {1: "🟢 Tier 1 (logged)", 2: "🟡 Tier 2 (nudge)", 3: "🔴 Tier 3 (parent alert)"}
TIER_COLOR = {1: "#84cc16", 2: "#f59e0b", 3: "#ef4444"}


# -----------------------------
# Sidebar — config
# -----------------------------
st.sidebar.title("🛡️ Kawach")
st.sidebar.caption("Test dashboard — reads database.db directly for raw data, uses the real API for auth-gated actions")

db_path = st.sidebar.text_input("Database file path", value=DEFAULT_DB_PATH)
backend_url = st.sidebar.text_input("Backend URL", value=DEFAULT_BACKEND_URL)
auto_refresh = st.sidebar.checkbox("Auto-refresh every 5s", value=False)


# -----------------------------
# Parent auth (needed for toggle / children / alerts-feedback endpoints,
# which all require a bearer token as of the v2 backend).
# -----------------------------
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.parent_email = None

st.sidebar.markdown("---")
st.sidebar.subheader("Parent login")

if st.session_state.token:
    st.sidebar.success(f"Logged in as {st.session_state.parent_email}")
    if st.sidebar.button("Log out"):
        st.session_state.token = None
        st.session_state.parent_email = None
        st.rerun()
else:
    auth_email = st.sidebar.text_input("Email", value="test@parent.com")
    auth_password = st.sidebar.text_input("Password", value="testpass123", type="password")
    col_login, col_signup = st.sidebar.columns(2)

    def _try_auth(path):
        try:
            payload = {"email": auth_email, "password": auth_password}
            if path == "signup":
                payload["name"] = auth_email.split("@")[0]
            r = requests.post(f"{backend_url}/api/auth/{path}", json=payload, timeout=5)
            if r.status_code in (200, 201):
                data = r.json()
                st.session_state.token = data["access_token"]
                st.session_state.parent_email = auth_email
                st.rerun()
            else:
                st.sidebar.error(f"{path} failed: {r.json().get('detail', r.text)}")
        except Exception as e:
            st.sidebar.error(f"Couldn't reach backend: {e}")

    if col_login.button("Log in", width='stretch'):
        _try_auth("login")
    if col_signup.button("Sign up", width='stretch'):
        _try_auth("signup")

    st.sidebar.caption("First time? Use Sign up to create a test parent account, then Log in normally after.")


def auth_headers():
    if not st.session_state.token:
        return {}
    return {"Authorization": f"Bearer {st.session_state.token}"}


# -----------------------------
# DB helpers (raw tables — no auth needed, this is local test data)
# -----------------------------
def get_connection():
    return sqlite3.connect(db_path)


def load_events(child_id_filter=None):
    conn = get_connection()
    query = (
        "SELECT id, child_id, session_id, signal_type, content, risk_label, "
        "risk_confidence, weight, timestamp FROM events ORDER BY timestamp DESC"
    )
    df = pd.read_sql_query(query, conn)
    conn.close()
    if child_id_filter and child_id_filter != "All":
        df = df[df["child_id"] == child_id_filter]
    return df


def load_alerts(child_id_filter=None):
    conn = get_connection()
    query = (
        "SELECT id, child_id, tier, score, status, ai_explanation, "
        "contributing_signal_ids, timestamp, updated_at FROM alert ORDER BY timestamp DESC"
    )
    df = pd.read_sql_query(query, conn)
    conn.close()
    if child_id_filter and child_id_filter != "All":
        df = df[df["child_id"] == child_id_filter]
    return df


def load_children():
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT child_id, monitoring_status, parent_id, weight_multiplier FROM children", conn
        )
    except Exception:
        df = pd.DataFrame(columns=["child_id", "monitoring_status", "parent_id", "weight_multiplier"])
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
    return sorted(i for i in ids if i)


def format_time_ago(ts_str):
    try:
        ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
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


def parse_ai_explanation(raw):
    """ai_explanation is stored as JSON text/dict depending on the SQLite driver."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return None


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
        f"same folder as your backend's database.db, or fix the path in the sidebar.\n\n"
        f"Error: {e}\n\n"
        f"If this is a first run, start the backend once (`uvicorn main:app`) so it creates the file."
    )
    st.stop()


# -----------------------------
# Child selector
# -----------------------------
all_child_ids = get_all_child_ids()
child_options = ["All"] + all_child_ids
selected_child = st.sidebar.selectbox("Child", child_options)


# -----------------------------
# Create/link a child (POST /api/children — requires login)
# -----------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Create a test child")

if not st.session_state.token:
    st.sidebar.caption("Log in above first.")
else:
    new_child_id = st.sidebar.text_input("New child_id", value="child_001")
    if st.sidebar.button("Create child + get pairing code", width='stretch'):
        try:
            r = requests.post(
                f"{backend_url}/api/children",
                json={"child_id": new_child_id},
                headers=auth_headers(),
                timeout=5,
            )
            if r.status_code == 201:
                data = r.json()
                st.sidebar.success(f"Created. Pairing code: {data['pairing_code']}")
            else:
                st.sidebar.error(f"Failed: {r.json().get('detail', r.text)}")
        except Exception as e:
            st.sidebar.error(f"Couldn't reach backend: {e}")


# -----------------------------
# Monitoring toggle (calls the REAL backend API — requires login +
# that the logged-in parent owns this child_id)
# -----------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Monitoring control")

if not st.session_state.token:
    st.sidebar.caption("Log in above first — toggling now requires a parent session.")
else:
    if selected_child != "All":
        toggle_child_id = st.sidebar.text_input("Child ID to toggle", value=selected_child)
    else:
        toggle_child_id = st.sidebar.text_input("Child ID to toggle", value=all_child_ids[0] if all_child_ids else "")

    col_on, col_off = st.sidebar.columns(2)

    def _toggle(status):
        try:
            r = requests.post(
                f"{backend_url}/api/monitoring/toggle",
                json={"child_id": toggle_child_id, "status": status},
                headers=auth_headers(),
                timeout=5,
            )
            if r.status_code == 200:
                st.sidebar.success(f"Status: {r.json().get('monitoring_status')}")
            elif r.status_code == 404:
                st.sidebar.error("Not found — this child_id doesn't exist or isn't owned by this parent. Create it above first.")
            elif r.status_code == 401:
                st.sidebar.error("Not authenticated — log in again.")
            else:
                st.sidebar.error(f"Failed: {r.text}")
        except Exception as e:
            st.sidebar.error(f"Couldn't reach backend: {e}")

    if col_on.button("Turn ON", width='stretch'):
        _toggle("on")
    if col_off.button("Turn OFF", width='stretch'):
        _toggle("off")


# -----------------------------
# Main content
# -----------------------------
st.title("🛡️ Kawach — Test Dashboard")
st.caption(
    "This is a TESTING view — not the final parent-facing design. Raw event/alert "
    "tables read the database directly; monitoring toggle and child creation go "
    "through the real, auth-gated API."
)

events_df = load_events(selected_child)
alerts_df = load_alerts(selected_child)
children_df = load_children()

# --- Top stats row ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total events", len(events_df))
risky_count = len(events_df[events_df["risk_label"].notna() & (events_df["risk_label"] != "safe")])
col2.metric("Risky events", risky_count)
col3.metric("Tier-3 alerts (sent to parent)", len(alerts_df))
tier3_count = len(alerts_df[alerts_df["tier"] == 3]) if len(alerts_df) else 0
col4.metric("Currently 'new' status", len(alerts_df[alerts_df["status"] == "new"]) if len(alerts_df) else 0)

st.markdown("---")

# --- Alerts feed ---
st.subheader("🚨 Alerts (tier 3 only — tiers 1/2 never create an Alert row, see raw log below)")
if alerts_df.empty:
    st.info("No tier-3 alerts yet. Send enough weighted signals for the same child+session within 30 minutes (score 6+) to trigger one.")
else:
    for _, alert in alerts_df.iterrows():
        tier = int(alert["tier"]) if pd.notna(alert["tier"]) else 3
        explanation = parse_ai_explanation(alert["ai_explanation"]) or {}
        label = TIER_LABEL.get(tier, f"Tier {tier}")

        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"**{label}** — child: `{alert['child_id']}` &nbsp;|&nbsp; "
                    f"score: {alert['score']} &nbsp;|&nbsp; status: `{alert['status']}`"
                )
                if explanation:
                    st.write(f"**What happened:** {explanation.get('what_happened', '—')}")
                    st.write(f"**Why it matters:** {explanation.get('why_it_matters', '—')}")
                    st.write(f"**Recommended action:** {explanation.get('recommended_action', '—')}")
                    st.caption(f"Severity: {explanation.get('severity_label', '—')}")
                else:
                    st.caption("No AI explanation stored on this alert.")

                try:
                    ids = json.loads(alert["contributing_signal_ids"]) if isinstance(alert["contributing_signal_ids"], str) else alert["contributing_signal_ids"]
                    if ids:
                        st.caption(f"Contributing event IDs: {ids}")
                except Exception:
                    pass
            with c2:
                st.caption(format_time_ago(alert["timestamp"]))
                st.caption(alert["timestamp"])

st.markdown("---")

# --- Raw events log ---
st.subheader("📋 Raw signal log")

filter_col1, filter_col2 = st.columns(2)
show_only_risky = filter_col1.checkbox("Show only risky signals", value=False)
signal_type_filter = filter_col2.multiselect(
    "Signal type", options=events_df["signal_type"].dropna().unique().tolist() if not events_df.empty else []
)

display_df = events_df.copy()
if show_only_risky:
    display_df = display_df[display_df["risk_label"].notna() & (display_df["risk_label"] != "safe")]
if signal_type_filter:
    display_df = display_df[display_df["signal_type"].isin(signal_type_filter)]

if display_df.empty:
    st.info("No signals match the current filters.")
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
st.subheader("👤 Children")
if children_df.empty:
    st.info("No children yet — use 'Create a test child' in the sidebar (requires login) to add one.")
else:
    st.dataframe(children_df, width='stretch', hide_index=True)

# --- Auto-refresh ---
if auto_refresh:
    time.sleep(5)
    st.rerun()
