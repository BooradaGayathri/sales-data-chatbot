import streamlit as st

from chatbot import answer, build_database

st.set_page_config(page_title="Sales Data Chatbot", page_icon="💬")
st.title("💬 Sales Data Chatbot")
st.caption("Ask questions about the sales data. The bot answers using SQL.")


@st.cache_resource
def get_conn():
    return build_database()


conn = get_conn()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! Ask me e.g. 'total revenue in South' or 'top product'."}
    ]

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])
        if m.get("sql"):
            st.code(m["sql"], language="sql")

if prompt := st.chat_input("Ask about sales..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    reply, sql = answer(prompt, conn)
    st.session_state.messages.append({"role": "assistant", "content": reply, "sql": sql})
    with st.chat_message("assistant"):
        st.write(reply)
        if sql:
            st.code(sql, language="sql")
