import streamlit as st
from google import genai
from google.genai import types

# If Google renames or retires this model, change it here.
MODEL = "gemini-3.8-flash"
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
    return genai.Client(api_key=key)


client = get_client(api_key)

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
        try:
            with st.spinner("Thinking..."):
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM),
                )
            reply = resp.text or "Sorry, I could not generate an answer."
        except Exception as e:
            reply = f"Sorry, something went wrong: {e}"
        st.write(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
