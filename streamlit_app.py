import base64
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# 1. Inject project root cleanly into system paths
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. Standard library imports

# 3. Third-party and project imports
import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402
from main import run_pipeline  # noqa: E402
from core.rag_engine import ask_question  # noqa: E402


BASE = Path(__file__).parent
MAX_UPLOAD_MB = 60

st.set_page_config(page_title="AI Meeting Intelligence", page_icon="🎬", layout="wide",
                   initial_sidebar_state="collapsed")

# Streamlit secrets -> environment variables (so the Gemini key reaches your code)
try:
    for _k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

from main import run_pipeline                 # noqa: E402  your existing pipeline
from core.rag_engine import ask_question      # noqa: E402  your existing chat chain

# ---- hide Streamlit's own chrome so only the page shows -------------------------------
st.markdown("""
<style>
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], #MainMenu, footer { display: none !important }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #04060b !important; overflow: hidden !important }
.block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; margin: 0 !important; max-width: 100% !important }
iframe[title$="meeting_stage"], [data-testid="stCustomComponentV1"] iframe {
  position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; border: 0 !important; z-index: 999 }
</style>
""", unsafe_allow_html=True)


# ---- build the component folder from your own meeting.html + bridge.js ---------------
@st.cache_resource
def build_frontend(stamp: float) -> str:
    html = (BASE / "meeting.html").read_text(encoding="utf-8")
    bridge = (BASE / "bridge.js").read_text(encoding="utf-8")
    i = html.rfind("</body>")
    html = html[:i] + "<script>\n" + bridge + "\n</script>\n" + html[i:]
    out = BASE / "frontend"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    return str(out)


stamp = max((BASE / "meeting.html").stat().st_mtime,
            (BASE / "bridge.js").stat().st_mtime)
stage = components.declare_component(
    "meeting_stage", path=build_frontend(stamp))


# ---- shared memory for jobs and chat chains (lives as long as the server runs) -------
@st.cache_resource
def store():
    return {"jobs": {}, "chains": {}}


def safe_error(e: Exception) -> str:
    msg = str(e)
    msg = re.sub(r"(key=)[^&\s'\"]+", r"\1***", msg)
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            msg = msg.replace(secret, "***")
    return msg[:600]


def as_list(x):
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return list(x)
    if isinstance(x, str):
        lines = [re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "",
                        l).strip() for l in x.splitlines()]
        return [l for l in lines if l]
    return [str(x)]


def to_payload(r: dict, job_id: str) -> dict:
    # rag_chain is a Python object, so it stays on the server and is reached through session_id
    return {
        "title": r.get("title", ""),
        "summary": r.get("summary", ""),
        "action_items": as_list(r.get("action_items")),
        "decisions": as_list(r.get("key_decisions")),
        "open_questions": as_list(r.get("open_questions")),
        "transcript": r.get("transcript", ""),
        "session_id": job_id,
    }


def run_job(S: dict, job_id: str, source: str, language: str, tmp):
    """Runs in a background thread, so the page keeps playing while Python works."""
    try:
        r = run_pipeline(source, language)
        S["chains"][job_id] = r.get("rag_chain")
        S["jobs"][job_id] = {"status": "done",
                             "result": to_payload(r, job_id), "t": time.time()}
    except Exception as e:
        print(f"Job {job_id} failed: {safe_error(e)}")
        S["jobs"][job_id] = {
            "status": "error", "error": "Pipeline failed: " + safe_error(e), "t": time.time()}
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def handle(a: dict) -> dict:
    S, act = store(), a.get("action")

    if act == "analyse":
        language, tmp = a.get("language") or "english", None
        if a.get("data"):
            raw = base64.b64decode(a["data"].split(",", 1)[-1])
            if len(raw) > MAX_UPLOAD_MB * 1048576:
                return {"ok": False, "error": f"That file is over {MAX_UPLOAD_MB} MB."}
            suffix = Path(a.get("filename") or "audio").suffix or ".mp3"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(raw)
                tmp = f.name
            source = tmp
        elif (a.get("url") or "").strip():
            source = a["url"].strip()
        else:
            return {"ok": False, "error": "Provide a url or a file"}
        for k in [k for k, v in S["jobs"].items() if time.time() - v.get("t", 0) > 3600]:
            S["jobs"].pop(k, None)
            S["chains"].pop(k, None)
        job_id = uuid.uuid4().hex
        S["jobs"][job_id] = {"status": "running", "t": time.time()}
        threading.Thread(target=run_job, args=(
            S, job_id, source, language, tmp), daemon=True).start()
        return {"ok": True, "job_id": job_id}

    if act == "poll":
        job = S["jobs"].get(a.get("job_id"))
        if not job:
            return {"ok": True, "status": "missing"}
        return {"ok": True, **{k: v for k, v in job.items() if k != "t"}}

    if act == "chat":
        chain = S["chains"].get(a.get("session_id"))
        if chain is None:
            return {"ok": False, "error": "This meeting is no longer in memory."}
        try:
            return {"ok": True, "answer": str(ask_question(chain, a.get("question", "")))}
        except Exception as e:
            return {"ok": False, "error": safe_error(e)}

    return {"ok": False, "error": "Unknown action"}


# ---- the page ------------------------------------------------------------------------
if "reply" not in st.session_state:
    st.session_state.reply = None
    st.session_state.handled = None

value = stage(key="stage", reply=st.session_state.reply, default=None)

if value and value.get("id") != st.session_state.handled:
    st.session_state.handled = value["id"]
    out = handle(value)
    out["id"] = value["id"]
    st.session_state.reply = out
    st.rerun()
