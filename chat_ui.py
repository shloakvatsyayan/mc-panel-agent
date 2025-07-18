"""
Streamlit chat UI for the Minecraft Panel Agent – now with live log!
Run: streamlit run chat_ui.py
"""
from pathlib import Path

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

# --------- chat replay ---------------------------------------------------- #
if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --------- input & streaming reply --------------------------------------- #
prompt = st.chat_input("Ask the agent …")
if prompt:
    # show user message instantly
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # prepare containers for live logs & final reply
    with st.chat_message("assistant"):
        log_container = st.container()
        reply_placeholder = st.empty()

        steps_md: list[str] = []

        # stream events
        for kind, content in run_agent_stream(prompt):
            if kind == "step":
                steps_md.append(content)
                # live update expander
                with log_container.expander("🪵 Agent steps", expanded=True):
                    for md in steps_md:
                        st.markdown(md, unsafe_allow_html=True)
            else:  # final
                reply_placeholder.markdown(content)
                st.session_state.history.append({"role": "assistant", "content": content})
