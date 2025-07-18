"""
Streamlit chat UI for the Minecraft Panel Agent
Run: streamlit run chat_ui.py
"""
from pathlib import Path
import uuid
import streamlit as st

from minecraft_agent.config import DOWNLOADS_DIR
from minecraft_agent.main import run_agent_stream

st.set_page_config(page_title="Minecraft Panel Agent", page_icon="🟢")

st.title("🟢 Minecraft Panel Agent")
st.caption(
    "Talk to the agent that controls **only** the whitelisted server.  "
    "Drop plugin JARs below – they’re added to the `downloads/` folder."
)

# --------- drag‑and‑drop JAR upload --------------------------------------- #
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

# ── initialise persistent state ────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

if "current_steps_idx" not in st.session_state:
    # index of the “🪵 Agent steps” message *for the prompt that is currently
    # streaming*.  None means “no prompt is being streamed right now”.
    st.session_state.current_steps_idx = None

# ── replay chat history ────────────────────────────────────────────────────────
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── prompt input ───────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask the agent …")
if prompt:
    # store the user message
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # unique ID for this prompt → persists through every rerun
    run_id = str(uuid.uuid4())
    st.session_state[f"{run_id}_steps"] = []

    # ────────────────────────────────────────────────────────────────────
    # 👇 ***ONE*** assistant container that survives every rerun
    # ────────────────────────────────────────────────────────────────────
    assistant_container = st.chat_message(
        "assistant")
    with assistant_container:
        # collapsible expander with its own stable key
        with st.expander("🪵 Agent steps", expanded=True):
            steps_placeholder = st.empty()          # ← we update this
        reply_placeholder = st.empty()              # final answer

    # ─────────────── stream events from the agent ───────────────────────
    for kind, content in run_agent_stream(prompt):

        # ----- incremental “step” events --------------------------------
        if kind == "step":
            st.session_state[f"{run_id}_steps"].append(content)
            steps_md = (
                "\n".join(st.session_state[f"{run_id}_steps"])
            )

            # live-update the markdown inside the expander
            steps_placeholder.markdown(steps_md, unsafe_allow_html=True)

            # write OR update the matching entry in history
            if (
                not st.session_state.history
                or not st.session_state.history[-1]["content"].startswith("🪵 Agent steps")
            ):
                st.session_state.history.append(
                    {"role": "assistant", "content": steps_md}
                )
            else:
                st.session_state.history[-1]["content"] = steps_md

        # ----- final answer ---------------------------------------------
        else:  # kind == "final"
            reply_placeholder.markdown(content)
            st.session_state.history.append(
                {"role": "assistant", "content": content}
            )