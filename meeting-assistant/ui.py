from datetime import date

import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Meeting Assistant", page_icon="📝")
st.title("📝 AI Meeting Assistant")

meeting_date = st.date_input("Meeting date", value=date.today())


def show_result(data: dict):
    st.subheader("Summary")
    st.write(data["summary"])

    st.subheader("Key Decisions")
    if data["key_decisions"]:
        for decision in data["key_decisions"]:
            st.markdown(f"- {decision}")
    else:
        st.info("No key decisions found.")

    st.subheader("Action Items")
    if data["action_items"]:
        st.table(
            [
                {
                    "Task": a["task"],
                    "Owner": a["owner"] or "-",
                    "Deadline": a["deadline"] or "-",
                }
                for a in data["action_items"]
            ]
        )
    else:
        st.info("No action items found.")

    with st.expander("Raw JSON"):
        st.json(data)


tab_text, tab_audio = st.tabs(["Text transcript", "Audio recording"])

# ---------- Text tab ----------
with tab_text:
    st.write("Paste a meeting transcript or upload a .txt file.")
    uploaded_txt = st.file_uploader("Transcript file (.txt)", type=["txt"])
    default_text = uploaded_txt.read().decode("utf-8") if uploaded_txt else ""
    transcript = st.text_area("Transcript", value=default_text, height=250)

    if st.button("Summarize text"):
        if not transcript.strip():
            st.warning("Please enter a transcript first.")
        else:
            with st.spinner("The AI is working..."):
                try:
                    resp = requests.post(
                        f"{API_BASE}/meetings/summarize",
                        json={"transcript": transcript, "meeting_date": meeting_date.isoformat()},
                        timeout=180,
                    )
                except requests.exceptions.ConnectionError:
                    st.error("The API is not running. Start it first in a separate terminal.")
                    st.stop()

            if resp.status_code != 200:
                st.error(f"Error {resp.status_code}: {resp.text}")
            else:
                show_result(resp.json())

# ---------- Audio tab ----------
with tab_audio:
    st.write("Upload a short meeting recording (mp3, wav, m4a, aac, ogg, flac). Max about 10 minutes.")
    audio_file = st.file_uploader(
        "Audio file", type=["mp4","mp3", "wav", "m4a", "aac", "ogg", "flac"]
    )
    if audio_file:
        st.audio(audio_file)

    if st.button("Transcribe and summarize"):
        if not audio_file:
            st.warning("Please upload an audio file first.")
        else:
            with st.spinner("Transcribing and summarizing... this can take a minute."):
                try:
                    resp = requests.post(
                        f"{API_BASE}/meetings/summarize-audio",
                        files={"file": (audio_file.name, audio_file.getvalue())},
                        data={"meeting_date": meeting_date.isoformat()},
                        timeout=300,
                    )
                except requests.exceptions.ConnectionError:
                    st.error("The API is not running. Start it first in a separate terminal.")
                    st.stop()

            if resp.status_code != 200:
                st.error(f"Error {resp.status_code}: {resp.text}")
            else:
                payload = resp.json()
                with st.expander("Transcript", expanded=True):
                    st.write(payload["transcript"])
                show_result(payload["result"])