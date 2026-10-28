<div align="center">

# 🎬 AI Meeting Intelligence On The Go

### Turn any recording into structured insight

Pick a sample or upload an audio/video file, and get a full transcript, summary, action items, decisions, and a live Q&A chat with your meeting.

</div>

---

## 🌐 Live demo

Try it without installing anything: **[Open the live app](https://ai-meeting-intelligence-on-the-go-onu9smazb73um55cjz9fbc.streamlit.app/)**

> **Status:** Portfolio prototype, not production software.
> - The free host sleeps when idle, so the first load can take about 30 seconds.
> - Pick one of the 14 **sample clips** (3 minutes each) or **upload your own** audio/video file.
> - **YouTube links work when you run the app locally**, but are blocked on cloud hosts (YouTube rejects datacenter IPs), so use a sample or an upload on the live demo.
> - Samples are trimmed to 3 minutes to stay within free-tier limits. Credit for the original talks goes to their creators.

---

## ✨ What it does

Give it a recording and get back a structured breakdown of what was said, with no manual note-taking.

| 📥 Input | ⚙️ Pipeline | 📤 Output |
|---|---|---|
| Sample clip, uploaded file, or (locally) a YouTube URL | Convert → Chunk → Transcribe → Analyze | Title, Summary, Action Items, Decisions, Open Questions, Full Transcript, Live Chat |

---

## 🧩 Features

**📄 Overview**
- Auto-generated meeting **title**
- Concise AI **summary** of the whole recording
- ✅ **Action items** with owner and deadline (when mentioned)
- 🔑 **Key decisions** made during the meeting
- ❓ **Open questions** flagged for follow-up

**🔍 Details**
- Full raw **transcript**

**💬 Chat**
- Ask anything about the meeting. Answers come **only from the transcript** via a retrieval-augmented (RAG) chain.

**🎮 Story front end**
- A custom HTML "zombie escape" stage embedded in Streamlit as a component. It plays while your file is processed, shows the pipeline stages as live status lights, and lets you **skip** or **keep playing** once the result is ready.

---

## 🏗️ How it works

```
Sample / Uploaded file / YouTube URL (local only)
        │
        ▼
 ┌───────────────┐
 │ Load / Convert│   ffmpeg + pydub → 16 kHz mono WAV
 └───────────────┘
        │
        ▼
 ┌───────────────┐
 │ Chunk Audio   │   fixed-length segments (10 min)
 └───────────────┘
        │
        ▼
 ┌───────────────┐   Groq-hosted Whisper (fast, GPU)
 │ Transcribe    │   falls back to local Whisper if no Groq key
 └───────────────┘
        │
        ▼
 ┌───────────────────────────────────────────┐
 │  LLM  ×  LangChain                         │
 │  ├── Title generation                      │
 │  ├── Summary                               │
 │  ├── Action items / Decisions / Questions  │
 │  └── RAG chain (Chroma + HF Embeddings)    │
 └───────────────────────────────────────────┘
        │
        ▼
   Streamlit + custom HTML UI  (Overview · Details · Chat)
```

---

## 🚀 Getting started

### 1. Clone and set up the environment

```bash
git clone https://github.com/AsadHamzaZahid/ai-meeting-intelligence-on-the-go.git
cd ai-meeting-intelligence-on-the-go

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

> **ffmpeg is required** for audio extraction. Check with `ffmpeg -version`.
> Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg`

### 2. Add your API keys

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here   # only if your LLM steps use Gemini
```

> Never commit your `.env` file. It is listed in `.gitignore`.
> On Streamlit Cloud, put the keys in **Settings → Secrets** instead, each on one line, e.g. `GROQ_API_KEY = "your_key"`.

Without a Groq key, transcription falls back to local Whisper, which needs `pip install openai-whisper` and is much slower on CPU.

### 3. Run it

**Streamlit UI:**
```bash
streamlit run streamlit_app.py
```
Open `http://localhost:8501` in your browser. Running locally also lets you paste YouTube links.

**CLI:**
```bash
python main.py
```

---

## 📁 Project structure

```
.
├── streamlit_app.py         # Streamlit entry point: jobs, samples, chat, component bridge
├── main.py                  # Pipeline orchestrator (run_pipeline, CLI entry point)
├── meeting.html             # Custom front end (story, upload UI, results)
├── bridge.js                # Connects the page to Streamlit/Python
├── core/
│   ├── transcriber.py       # Groq Whisper transcription (local fallback)
│   ├── summarizer.py        # Title + summary generation
│   ├── extractor.py         # Action items / decisions / questions
│   ├── vector_store.py      # Chroma vector store + embeddings
│   └── rag_engine.py        # LangChain RAG chain for meeting Q&A
├── utils/
│   └── audio_processor.py   # Download, convert, chunk audio
├── samples/                 # 14 trimmed demo clips + samples.json
├── .streamlit/config.toml   # Theme and server settings
├── requirements.txt
├── packages.txt             # System packages for cloud deploys (ffmpeg)
└── .gitignore
```

---

## 🛠️ Tech stack

- **Streamlit**: hosting and Python backend
- **Custom HTML/JS component**: story UI and results
- **yt-dlp + ffmpeg**: audio download and extraction (local YouTube links)
- **pydub**: audio conversion and chunking
- **Groq-hosted Whisper**: speech-to-text (local Whisper fallback)
- **LangChain**: orchestration
- **LLM**: summarization, extraction, Q&A
- **ChromaDB + HuggingFace Embeddings**: vector store for RAG

---

## 🧠 Deployment notes

What I ran into while deploying, and how I handled it:

- **YouTube blocks cloud IPs.** The app works locally but YouTube rejects requests from the cloud host. The live app uses samples and file upload instead.
- **Whisper on a free CPU was too slow**, and the app was throttled. Transcription moved to Groq's GPU-hosted Whisper, which cut a multi-minute job to seconds.
- **Secrets pasted into a dashboard can carry a hidden newline**, which breaks HTTP headers. Keys are now stripped at startup.
- **Samples are trimmed to 3 minutes** to stay within free-tier rate limits.

---

## 🧯 Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'utils.audio_processor'` | Another package called `utils` is installed in your Python. Run `pip uninstall utils`, or use a clean virtual environment. |
| `No module named 'langchain_chroma'` (or similar) | `pip install langchain-chroma langchain-huggingface langchain-groq yt-dlp pydub python-dotenv` |
| Audio extraction fails | Make sure `ffmpeg` is installed and on your PATH. |
| YouTube link fails on the live app | Expected: YouTube blocks cloud servers. Use a sample or upload a file, or run locally. |
| App closes silently on Windows | Use a fresh venv and test imports with `python -X faulthandler -c "import main"` to find the crashing library. |

---

## ⚠️ Notes

- Uploads are limited to 60 MB, and long files take longer to process.
- Only the transcript text is sent to the LLM provider for analysis, and audio is sent to Groq for transcription.
- This is a personal/practice project exploring an end-to-end AI pipeline, not hardened for production use.

---

<div align="center">

Built with 🧡 and 🌿: orange for effort, mint for clarity.

</div>
