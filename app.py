import json
import time
import uuid

import streamlit as st
from google import genai
from google.genai import types

PREFERRED = "gemini-3.8-flash"
SYSTEM = (
    "You are a helpful, friendly AI assistant. Answer clearly and concisely. "
    "If the user writes in Telugu or Tenglish, reply in the same style."
)

st.set_page_config(page_title="My AI Chatbot", page_icon="🤖")

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    st.error("API key missing. Add GEMINI_API_KEY in the app's Settings > Secrets.")
    st.stop()


@st.cache_resource
def get_client(key):
    # timeout is in milliseconds
    return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))


client = get_client(api_key)


@st.cache_data(ttl=3600)
def model_list(key):
    """Preferred model first, then other flash models this key can really use."""
    names = []
    try:
        for m in get_client(key).models.list():
            name = (m.name or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None)
            if actions is not None and "generateContent" not in actions:
                continue
            if "flash" not in name:
                continue
            if any(x in name for x in ("image", "tts", "live", "audio", "embedding", "robotics", "computer")):
                continue
            names.append(name)
    except Exception:
        pass
    names = sorted(set(names), reverse=True)
    if PREFERRED in names:
        names.remove(PREFERRED)
    return [PREFERRED] + names[:3]


def stream_reply(contents):
    """Yield the answer piece by piece. Retry on busy servers, then try other models."""
    errors = []
    for model in model_list(api_key):
        for attempt in range(2):
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
                break
            except Exception as e:
                if got_text:
                    yield "\n\n(The answer was cut off by an error.)"
                    return
                busy = any(s in str(e) for s in ("503", "UNAVAILABLE", "429"))
                if busy and attempt == 0:
                    time.sleep(2)
                    continue
                errors.append(f"{model}: {str(e)[:200]}")
                break
    yield "Sorry, I could not get an answer right now. Please try again in a minute.\n\n" + "\n\n".join(errors)


# ---------- chat storage (per browser session) ----------
def new_chat():
    cid = uuid.uuid4().hex[:8]
    st.session_state.chats[cid] = {"title": "New chat", "messages": []}
    st.session_state.current = cid


if "chats" not in st.session_state:
    st.session_state.chats = {}
    st.session_state.editing = False
    st.session_state.pending = None
    st.session_state.truncate = 0
    new_chat()

chat = st.session_state.chats[st.session_state.current]
messages = chat["messages"]

with st.sidebar:
    st.header("Chats")
    if st.button("➕ New chat"):
        new_chat()
        st.session_state.editing = False
        st.rerun()
    for cid, c in reversed(list(st.session_state.chats.items())):
        label = ("🟢 " if cid == st.session_state.current else "") + c["title"][:28]
        if st.button(label, key=f"chat_{cid}"):
            st.session_state.current = cid
            st.session_state.editing = False
            st.rerun()
    st.divider()
    if messages:
        st.download_button(
            "⬇️ Download this chat",
            json.dumps(chat, ensure_ascii=False, indent=2),
            file_name="chat.json",
            mime="application/json",
        )
    up = st.file_uploader("Load a saved chat", type="json")
    if up is not None:
        marker = f"{up.name}-{up.size}"
        if st.session_state.get("loaded") != marker:
            try:
                data = json.loads(up.getvalue())
                msgs = [
                    {"role": m["role"], "content": str(m["content"])}
                    for m in data["messages"]
                    if m["role"] in ("user", "assistant")
                ]
                new_chat()
                st.session_state.chats[st.session_state.current] = {
                    "title": str(data.get("title", "Loaded chat")), "messages": msgs,
                }
                st.session_state.loaded = marker
                st.rerun()
            except Exception:
                st.error("That file is not a valid saved chat.")
    st.caption("Chats are kept only while this page is open. Download a chat to keep it.")

st.title("🤖 My AI Chatbot")
st.caption("Ask me anything. Powered by Google Gemini.")

# A message sent from the edit box: cut the chat back to that point and resend.
prompt = None
if st.session_state.pending:
    del messages[st.session_state.truncate:]
    prompt = st.session_state.pending
    st.session_state.pending = None

for m in messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

typed = st.chat_input("Ask me anything...")
prompt = prompt or typed

if prompt:
    if chat["title"] == "New chat":
        chat["title"] = prompt[:30]
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    contents = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    with st.chat_message("assistant"):
        reply = st.write_stream(stream_reply(contents))
    messages.append({"role": "assistant", "content": reply})

# ---------- edit last message ----------
user_idx = [i for i, m in enumerate(messages) if m["role"] == "user"]
if user_idx:
    last = user_idx[-1]
    if not st.session_state.editing:
        if st.button("✏️ Edit last message"):
            st.session_state.editing = True
            st.rerun()
    else:
        new_text = st.text_area(
            "Edit your last message",
            value=messages[last]["content"],
            key=f"edit_{st.session_state.current}_{len(messages)}",
        )
        c1, c2 = st.columns(2)
        if c1.button("Send") and new_text.strip():
            st.session_state.pending = new_text.strip()
            st.session_state.truncate = last
            st.session_state.editing = False
            st.rerun()
        if c2.button("Cancel"):
            st.session_state.editing = False
            st.rerun()
