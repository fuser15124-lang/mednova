"""Streamlit entry point for MedNova AI.

Educational medical information only; not clinically validated.
Secrets are read from Streamlit secrets/environment and never embedded in source.
"""
import os
from pathlib import Path
import asyncio
import io

import streamlit as st
from sqlalchemy import select
from pypdf import PdfReader
from fastapi import HTTPException

# Load secrets BEFORE importing app modules because app.config.Settings is created at import time.
def secret(name: str, default: str = "") -> str:
    value = os.getenv(name, "")
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default

for key in (
    "APP_NAME", "DATABASE_URL", "JWT_SECRET", "JWT_EXPIRE_MINUTES",
    "MAX_UPLOAD_MB", "AI_BASE_URL", "AI_API_KEY", "AI_MODEL",
    "AI_TIMEOUT_SECONDS", "NCBI_TOOL", "NCBI_EMAIL",
):
    value = secret(key)
    if value:
        os.environ[key] = value

from app.config import settings
from app.db import Base, engine, SessionLocal
from app.models import User, Conversation, Message, Document
from app.security import hash_password, verify_password
from app.ai import answer
from app.pubmed import search_pubmed

st.set_page_config(page_title="MedNova AI", page_icon="➕", layout="wide")
Base.metadata.create_all(bind=engine)

LANGUAGES = {
    "فارسی": "fa", "English": "en", "Español": "es",
    "Italiano": "it", "Русский": "ru", "עברית": "he",
}
LABELS = {
    "en": {"overview":"Overview", "chat":"Medical AI chat", "evidence":"Evidence search",
           "docs":"Documents", "signin":"Sign in", "signup":"Create account", "email":"Email",
           "password":"Password", "logout":"Sign out", "welcome":"Welcome to MedNova AI",
           "question":"Ask a medical information question", "send":"Send", "search":"Search PubMed",
           "upload":"Upload a PDF or UTF-8 text file", "important":"Important medical information",
           "disclaimer":"MedNova AI provides educational information, not a diagnosis. AI output can be inaccurate. For emergencies, contact local emergency services.",
           "need_ai":"AI is not configured. Add AI_API_KEY and AI_MODEL in Streamlit App → Settings → Secrets.",
           "no_results":"No results found.", "account":"Account", "role":"Use", "general":"General",
           "student":"Student", "professional":"Professional (not enabled)", "history":"Conversation history"},
    "fa": {"overview":"نمای کلی", "chat":"گفت‌وگوی هوش مصنوعی پزشکی", "evidence":"جست‌وجوی شواهد", "docs":"اسناد",
           "signin":"ورود", "signup":"ایجاد حساب", "email":"ایمیل", "password":"رمز عبور", "logout":"خروج",
           "welcome":"به MedNova AI خوش آمدید", "question":"سؤال اطلاعات پزشکی خود را بنویسید", "send":"ارسال",
           "search":"جست‌وجو در PubMed", "upload":"بارگذاری PDF یا فایل متنی UTF-8",
           "important":"اطلاعات مهم پزشکی",
           "disclaimer":"MedNova AI اطلاعات آموزشی ارائه می‌کند و ابزار تشخیص نیست. پاسخ هوش مصنوعی ممکن است نادرست باشد. در وضعیت اورژانسی با خدمات اورژانس محلی تماس بگیرید.",
           "need_ai":"هوش مصنوعی تنظیم نشده است. AI_API_KEY و AI_MODEL را در بخش Secrets برنامه Streamlit تنظیم کنید.",
           "no_results":"نتیجه‌ای پیدا نشد.", "account":"حساب کاربری", "role":"نوع استفاده",
           "general":"عمومی", "student":"دانشجو", "professional":"متخصص (فعال نیست)", "history":"تاریخچه گفتگو"},
}
if "language" not in st.session_state:
    st.session_state.language = "fa"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "page" not in st.session_state:
    st.session_state.page = "overview"
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

lang_name = st.sidebar.selectbox("Language / زبان", list(LANGUAGES), index=list(LANGUAGES.values()).index(st.session_state.language))
st.session_state.language = LANGUAGES[lang_name]
lang = st.session_state.language
T = LABELS[lang]
st.sidebar.title("➕ MedNova AI")
st.sidebar.caption("MEDICAL INFORMATION PLATFORM")
st.sidebar.divider()

if st.session_state.user_id:
    with SessionLocal() as db:
        user = db.get(User, st.session_state.user_id)
        if user is None:
            st.session_state.user_id = None
        else:
            st.sidebar.caption(f"{T['account']}: {user.email}")
            for key, label in [("overview", T["overview"]), ("chat", T["chat"]), ("evidence", T["evidence"]), ("docs", T["docs"])]:
                if st.sidebar.button(label, use_container_width=True, type="primary" if st.session_state.page == key else "secondary"):
                    st.session_state.page = key
                    st.rerun()
            if st.sidebar.button(T["logout"], use_container_width=True):
                st.session_state.user_id = None
                st.session_state.conversation_id = None
                st.session_state.page = "overview"
                st.rerun()
else:
    st.sidebar.info("Create an account or sign in to use saved chats, evidence search and documents.")

st.title(T["welcome"])
st.caption("Evidence-led health information · Transparent limitations")
st.warning(T["disclaimer"], icon="⚕️")

def auth_panel():
    st.subheader(T["signin"] + " / " + T["signup"])
    mode = st.radio(" ", [T["signin"], T["signup"]], horizontal=True, label_visibility="collapsed")
    with st.form("auth_form", clear_on_submit=False):
        email = st.text_input(T["email"]).strip().lower()
        password = st.text_input(T["password"], type="password", help="Use at least 10 characters.")
        selected_role = st.selectbox(T["role"], [T["general"], T["student"], T["professional"]])
        submitted = st.form_submit_button(T["signin"] if mode == T["signin"] else T["signup"], type="primary")
    if submitted:
        if not email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            st.error("Enter a valid email address.")
            return
        with SessionLocal() as db:
            if mode == T["signup"]:
                if len(password) < 10:
                    st.error("Password must be at least 10 characters.")
                    return
                role_map = {T["general"]: "general", T["student"]: "student", T["professional"]: "professional"}
                role = role_map[selected_role]
                if role == "professional":
                    st.error("Professional access is not enabled because credential verification is not implemented.")
                    return
                if db.scalar(select(User).where(User.email == email)):
                    st.error("An account with this email already exists.")
                    return
                user = User(email=email, password_hash=hash_password(password), language=lang, role=role)
                db.add(user)
                db.commit()
                db.refresh(user)
                st.session_state.user_id = user.id
                st.session_state.page = "overview"
                st.success("Account created.")
                st.rerun()
            else:
                user = db.scalar(select(User).where(User.email == email))
                if not user or not verify_password(password, user.password_hash):
                    st.error("Incorrect email or password.")
                    return
                st.session_state.user_id = user.id
                st.session_state.page = "overview"
                st.success("Signed in.")
                st.rerun()

if not st.session_state.user_id:
    auth_panel()
    st.stop()

if st.session_state.page == "overview":
    st.subheader("Better questions. Clearer medical knowledge.")
    st.write("Use the workspace to ask general medical-information questions, search PubMed records, and extract text from documents.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### ✳️ " + T["chat"])
        st.write("Ask questions with clear limitations.")
        if st.button("Open chat", use_container_width=True):
            st.session_state.page = "chat"; st.rerun()
    with c2:
        st.markdown("### 🔎 " + T["evidence"])
        st.write("Search indexed biomedical literature on PubMed.")
        if st.button("Search evidence", use_container_width=True):
            st.session_state.page = "evidence"; st.rerun()
    with c3:
        st.markdown("### 📄 " + T["docs"])
        st.write("Extract text from PDFs and UTF-8 text files.")
        if st.button("Open documents", use_container_width=True):
            st.session_state.page = "docs"; st.rerun()
    st.info("This starter is not clinically validated. Do not use it for diagnosis, emergencies, or treatment decisions.")

elif st.session_state.page == "chat":
    st.subheader(T["chat"])
    if not settings.ai_api_key or not settings.ai_model:
        st.info(T["need_ai"])
    with SessionLocal() as db:
        conversations = db.scalars(select(Conversation).where(Conversation.user_id == st.session_state.user_id).order_by(Conversation.updated_at.desc())).all()
        options = {"＋ New conversation": None}
        options.update({f"{c.title[:65]} · #{c.id}": c.id for c in conversations})
        chosen = st.selectbox(T["history"], list(options.keys()))
        if st.session_state.conversation_id != options[chosen]:
            st.session_state.conversation_id = options[chosen]
        if st.button("Start new conversation"):
            st.session_state.conversation_id = None
            st.rerun()
        if st.session_state.conversation_id:
            conv = db.get(Conversation, st.session_state.conversation_id)
            if conv and conv.user_id == st.session_state.user_id:
                for msg in conv.messages:
                    with st.chat_message(msg.role):
                        st.markdown(msg.content)
    prompt = st.chat_input(T["question"])
    if prompt:
        with SessionLocal() as db:
            conv = db.get(Conversation, st.session_state.conversation_id) if st.session_state.conversation_id else None
            if conv and conv.user_id != st.session_state.user_id:
                st.error("Conversation not found.")
                st.stop()
            if not conv:
                conv = Conversation(user_id=st.session_state.user_id, title=prompt[:70], language=lang)
                db.add(conv); db.commit(); db.refresh(conv)
                st.session_state.conversation_id = conv.id
            db.add(Message(conversation_id=conv.id, role="user", content=prompt)); db.commit()
            history = db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc()).limit(20)).all()
            history = list(reversed(history))
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                if not settings.ai_api_key or not settings.ai_model:
                    st.error(T["need_ai"])
                else:
                    with st.spinner("Generating an informational response…"):
                        try:
                            response = asyncio.run(answer([{"role": m.role, "content": m.content} for m in history], lang))
                            st.markdown(response)
                            db.add(Message(conversation_id=conv.id, role="assistant", content=response))
                            db.commit()
                            st.caption(T["disclaimer"])
                        except HTTPException as exc:
                            st.error(f"AI service error ({exc.status_code}): {exc.detail}")
                        except Exception:
                            st.error("The AI service is unavailable. No answer was generated; please retry later.")

elif st.session_state.page == "evidence":
    st.subheader(T["evidence"])
    with st.form("pubmed_form"):
        query = st.text_input("Search terms", placeholder="e.g. diabetes treatment")
        submitted = st.form_submit_button(T["search"], type="primary")
    if submitted:
        if not query.strip():
            st.warning("Enter search terms.")
        else:
            with st.spinner("Searching PubMed…"):
                try:
                    data = asyncio.run(search_pubmed(query.strip(), 1, 10))
                    st.caption(f"{data['total']} records found · page 1")
                    if not data["results"]:
                        st.info(T["no_results"])
                    for item in data["results"]:
                        with st.expander(f"{item['title']} ({item.get('pubdate') or 'date unavailable'})"):
                            st.write("Authors: " + ", ".join(item.get("authors") or []))
                            st.write("Journal: " + str(item.get("journal") or "Not provided"))
                            st.write(item.get("abstract") or "Abstract unavailable.")
                            st.link_button("Open PubMed record", item["url"])
                except HTTPException as exc:
                    st.error(f"PubMed error ({exc.status_code}): {exc.detail}")
                except Exception:
                    st.error("PubMed is temporarily unavailable. Please retry.")

elif st.session_state.page == "docs":
    st.subheader(T["docs"])
    max_bytes = settings.max_upload_mb * 1024 * 1024
    uploaded = st.file_uploader(T["upload"], type=["pdf", "txt"])
    if uploaded is not None:
        raw = uploaded.getvalue()
        if len(raw) > max_bytes:
            st.error(f"File exceeds {settings.max_upload_mb} MB limit.")
        else:
            try:
                if uploaded.name.lower().endswith(".pdf"):
                    if not raw.startswith(b"%PDF-"):
                        raise ValueError("File signature does not match PDF.")
                    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
                    content_type = "application/pdf"
                else:
                    text = raw.decode("utf-8-sig")
                    content_type = "text/plain"
                if st.button("Save extracted text"):
                    with SessionLocal() as db:
                        doc = Document(user_id=st.session_state.user_id, filename=Path(uploaded.name).name[:255],
                                       content_type=content_type, extracted_text=text[:500000])
                        db.add(doc); db.commit(); db.refresh(doc)
                        st.success(f"Saved. Extracted {len(doc.extracted_text)} characters.")
                        st.text_area("Extracted text preview", doc.extracted_text[:5000], height=240)
            except Exception as exc:
                st.error(f"Could not read file: {exc}")
    with SessionLocal() as db:
        docs = db.scalars(select(Document).where(Document.user_id == st.session_state.user_id).order_by(Document.id.desc())).all()
        st.markdown("### Saved documents")
        if not docs:
            st.caption("No documents saved yet.")
        for doc in docs:
            with st.expander(f"{doc.filename} · {len(doc.extracted_text)} characters"):
                st.text_area(f"Preview — {doc.filename}", doc.extracted_text[:5000], height=180, key=f"doc_{doc.id}")
                st.caption("Text extraction only; scanned-PDF OCR and clinical interpretation are not provided.")

st.divider()
st.caption(T["disclaimer"])
