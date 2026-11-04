"""Streamlit interface for VisionZeroMate, the NYC collision data assistant."""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from chatbot import AssistantError, answer_question, database_status

st.set_page_config(
    page_title="VisionZeroMate | NYC collision insights",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
      :root { --ink:#14231f; --muted:#71817a; --green:#13795b; --lime:#c8f169; --paper:#f6f8f5; }
      html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
      .stApp { background:var(--paper); color:var(--ink); }
      h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.04em; }
      .block-container { max-width:1100px; padding-top:2.2rem; padding-bottom:3rem; }
      [data-testid="stSidebar"] { background:#10231e; }
      [data-testid="stSidebar"] * { color:#e7f0eb; }
      .brand-mark { display:flex; align-items:center; gap:12px; margin:4px 0 34px; }
      .brand-icon { display:grid; place-items:center; width:42px; height:42px; border-radius:14px; background:var(--lime); color:#10231e; font-size:22px; }
      .brand-name { font:800 17px Manrope,sans-serif; line-height:1.15; }
      .brand-sub { font-size:11px; color:#aabbb3; margin-top:4px; }
      .eyebrow { color:var(--green); font-size:12px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }
      .hero-title { font:800 clamp(34px,5vw,54px)/1.08 Manrope,sans-serif; letter-spacing:-.055em; margin:12px 0 10px; }
      .hero-copy { color:#71817a; font-size:16px; max-width:640px; line-height:1.65; }
      .status-card { border:1px solid #dfe7e1; background:white; border-radius:16px; padding:16px; margin:12px 0 22px; }
      .status-label { color:#9aaba3; font-size:10px; text-transform:uppercase; letter-spacing:.12em; font-weight:700; }
      .status-value { font-weight:700; font-size:13px; margin-top:6px; }
      .small-note { color:#aabbb3; font-size:12px; line-height:1.6; }
      .suggestion { border:1px solid #e0e8e2; background:white; border-radius:14px; padding:16px; height:100%; }
      .suggestion strong { font-size:14px; }
      .suggestion p { color:#71817a; font-size:12px; margin:8px 0 0; line-height:1.5; }
      div[data-testid="stChatMessage"] { border:1px solid #e5ebe6; background:#fff; border-radius:16px; padding:16px 18px; }
      .stButton button { border-radius:12px; font-weight:600; }
      div[data-testid="stChatInput"] { border-radius:18px; }
      .source-line { color:#86968e; font-size:11px; padding-top:10px; border-top:1px solid #edf1ed; margin-top:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        '<div class="brand-mark"><div class="brand-icon">🚦</div><div><div class="brand-name">VisionZeroMate</div><div class="brand-sub">NYC crash & safety assistant</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Explore the data")
    st.caption("Ask questions about collision patterns across New York City.")
    st.markdown(" ")
    st.markdown("**Try asking**")
    examples = [
        "How many crashes happened in 2023?",
        "Which borough has the most crashes?",
        "What are the riskiest hours for cyclists?",
        "Show the intersections with the most crashes",
        "How many people were injured and killed?",
    ]
    selected_example = None
    for example in examples:
        if st.button(example, key=f"example-{example}", use_container_width=True):
            selected_example = example
    st.markdown(" ")
    db = database_status()
    st.markdown(
        f'<div class="status-card"><div class="status-label">Data connection</div><div class="status-value">{"🟢 Database ready" if db["ready"] else "🟠 Setup needed"}</div><div class="small-note">{db["message"]}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="small-note">Data: NYC Open Data · Motor Vehicle Collisions<br>Coverage depends on the local database snapshot.</div>', unsafe_allow_html=True)
    if st.button("New conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.markdown('<div class="eyebrow">NYC collision intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Safer streets start<br>with better questions.</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-copy">Explore collision counts, high-risk locations, and injury patterns with a data-grounded assistant. Ask in plain language and get an answer backed by NYC crash records.</div>', unsafe_allow_html=True)
st.markdown(" ")

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.markdown("#### Start with a question")
    cards = st.columns(3)
    prompts = [
        ("📍 Find a hotspot", "Which intersections have the most crashes?", "Discover locations with frequent collisions."),
        ("🕒 Explore timing", "What hours have the most crashes?", "See how collision patterns shift through the day."),
        ("🏙️ Compare boroughs", "Compare crash counts by borough", "Explore the citywide distribution."),
    ]
    for col, (title, question, description) in zip(cards, prompts):
        with col:
            st.markdown(f'<div class="suggestion"><strong>{title}</strong><p>{description}</p></div>', unsafe_allow_html=True)
            if st.button("Ask this", key=f"card-{title}", use_container_width=True):
                selected_example = question

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🚦" if message["role"] == "assistant" else "🧑"):
        st.markdown(message["content"])
        if message.get("details"):
            with st.expander("How this answer was calculated"):
                st.write(message["details"])
                st.caption("Source: NYC Open Data Motor Vehicle Collisions dataset (h9gi-nx95).")

question = st.chat_input("Ask about NYC collisions, injuries, hotspots, or risky hours…")
if selected_example:
    question = selected_example

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(question)
    with st.chat_message("assistant", avatar="🚦"):
        with st.spinner("Checking collision records…"):
            try:
                result = answer_question(question)
                st.markdown(result["answer"])
                if result.get("table"):
                    st.dataframe(result["table"], hide_index=True, use_container_width=True)
                with st.expander("How this answer was calculated"):
                    st.write(result["details"])
                    st.caption("Source: NYC Open Data Motor Vehicle Collisions dataset (h9gi-nx95).")
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["answer"], "details": result["details"]}
                )
            except AssistantError as exc:
                st.warning(str(exc))
                st.session_state.messages.append({"role": "assistant", "content": str(exc)})
            except Exception as exc:  # Keep unexpected backend errors visible but non-fatal to the UI.
                st.error(f"I couldn’t complete that request. Check the app configuration and try again. ({exc})")
                st.session_state.messages.append({"role": "assistant", "content": "I couldn’t complete that request. Check the app configuration and try again."})
