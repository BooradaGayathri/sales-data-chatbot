import streamlit as st
from google import genai
from google.genai import types

# Tried in order. If Google renames or retires a model, edit this list.
MODELS = ["gemini-3.8-flash", "gemini-flash-latest"]
SYSTEM = (
    "You are a helpful, friendly AI assistant. Answer clearly and concisely. "
    "If the user writes in Telugu or Tenglish, reply in the same style."
)

st.set_page_config(page_title="My AI Chatbot", page_icon="🤖")
st.title("🤖 My AI Chatbot")
st.caption("Ask me anything. Powered by Google Gemini.")

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    st.error("API key missing. Add GEMINI_API_KEY in the app's Settings > Secrets.")
    st.stop()


@st.cache_resource
def get_client(key):
    # timeout is in milliseconds
    return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))


client = get_client(api_key)


def stream_reply(contents):
    """Yield the answer piece by piece; fall back to the next model on error."""
    errors = []
    for model in MODELS:
        got_text = False
        try:
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=SYSTEM),
            ):
                if chunk.text:
                    got_text = True
                    yield chunk.text
            if got_text:
                return
            errors.append(f"{model}: empty response")
        except Exception as e:
            if got_text:
                yield "\n\n(The answer was cut off by an error.)"
                return
            errors.append(f"{model}: {e}")
    yield "Sorry, I could not get an answer.\n\n" + "\n\n".join(errors)


if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    contents = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
        for m in st.session_state.messages
    ]
    with st.chat_message("assistant"):
        reply = st.write_stream(stream_reply(contents))
    st.session_state.messages.append({"role": "assistant", "content": reply})
