"""
Streamlit chat UI for the Minecraft Panel Agent

Run: streamlit run chat_ui.py
"""
from __future__ import annotations

from pathlib import Path
import json
import uuid

import requests
import streamlit as st

from minecraft_agent.config import DOWNLOADS_DIR, PELICAN_BASE_URL, PELICAN_API_KEY
from minecraft_agent.main import run_agent_stream

st.set_page_config(page_title="Minecraft Panel Agent", page_icon="🟢")

st.title("🟢 Minecraft Panel Agent")
st.caption(
    "Talk to the agent that controls **only** the whitelisted server(s).  "
    "Drop plugin JARs below – they’re added to the `downloads/` folder."
)


HEADERS = {
    "Authorization": f"Bearer {PELICAN_API_KEY}",
    "Accept": "application/vnd.pterodactyl.v1+json",
}
SERVER_FILE = Path("server_ids.json")


@st.cache_data(show_spinner=False, ttl=60 * 10)
def fetch_servers() -> list[tuple[str, str]]:
    """Return [(server_name, uuid), …] for all servers visible to this API key."""
    url = PELICAN_BASE_URL.rstrip("/") + "/api/client"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    return [
        (srv["attributes"]["name"], srv["attributes"]["uuid"])
        for srv in payload.get("data", [])
    ]


if "selected_uuids" not in st.session_state:
    if SERVER_FILE.exists():
        st.session_state.selected_uuids = json.loads(SERVER_FILE.read_text())
    else:
        st.session_state.selected_uuids = []

server_options = fetch_servers()


@st.dialog("Select the server(s) this agent may control", width="large")
def server_picker():
    """Modal dialog that runs until the user completes a selection."""
    names = [name for name, _ in server_options]
    default_selected = [
        name for name, uid in server_options if uid in st.session_state.selected_uuids
    ]

    picked_names = st.multiselect(
        "Search and choose one or more servers",
        options=names,
        default=default_selected,
        key="server_multiselect",
    )

    save_disabled = len(picked_names) == 0
    if st.button("Save selection", disabled=save_disabled):
        chosen_uuids = [
            uid for name, uid in server_options if name in picked_names
        ]
        SERVER_FILE.write_text(json.dumps(chosen_uuids, indent=2))
        st.session_state.selected_uuids = chosen_uuids
        st.success(f"Saved {len(chosen_uuids)} UUIDs → {SERVER_FILE.name}")
        st.rerun()


if not st.session_state.selected_uuids:
    server_picker()

uploader = st.file_uploader(
    "Upload plugin JAR(s)",
    type=["jar"],
    accept_multiple_files=True,
    help="Each file is saved to downloads/.",
)
if uploader:
    for f in uploader:
        dest: Path = DOWNLOADS_DIR / f.name
        dest.write_bytes(f.getbuffer())
        st.success(f"Saved **{f.name}** → downloads/")

with st.expander("📂 downloads/", expanded=False):
    files = [p.name for p in DOWNLOADS_DIR.glob("*.jar")]
    st.markdown("\n".join(f"* {n}" for n in files) or "_empty_")

if "history" not in st.session_state:
    st.session_state.history = []

if "current_steps_idx" not in st.session_state:
    st.session_state.current_steps_idx = None

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask the agent …")
if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    run_id = str(uuid.uuid4())
    st.session_state[f"{run_id}_steps"] = []

    assistant_container = st.chat_message("assistant")
    with assistant_container:
        with st.expander("🪵 Agent steps", expanded=True):
            steps_placeholder = st.empty()
        reply_placeholder = st.empty()

    for kind, content in run_agent_stream(prompt):
        if kind == "step":
            st.session_state[f"{run_id}_steps"].append(content)
            steps_md = "\n".join(st.session_state[f"{run_id}_steps"])
            steps_placeholder.markdown(steps_md, unsafe_allow_html=True)

            if (
                not st.session_state.history
                or not st.session_state.history[-1]["content"].startswith("🪵 Agent steps")
            ):
                st.session_state.history.append(
                    {"role": "assistant", "content": steps_md}
                )
            else:
                st.session_state.history[-1]["content"] = steps_md
        else:
            reply_placeholder.markdown(content)
            st.session_state.history.append({"role": "assistant", "content": content})

with st.sidebar:
    st.markdown("## ⚙️  Settings")
    if st.button("Edit allowed servers"):
        server_picker()