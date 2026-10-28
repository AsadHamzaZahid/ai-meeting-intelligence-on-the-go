<div align="center">

# 🎬 AI Meeting Intelligence On The Go

### Turn any video into structured insight

Paste a YouTube URL or drop a local file path — get a full transcript, summary, action items, decisions, and a live Q&A chat with your meeting.

</div>

---

## 🌐 Live demo

Try it without installing anything: **[Open the live app](https://ai-meeting-intelligence-on-the-go-onu9smazb73um55cjz9fbc.streamlit.app/)**

> The app may take a few seconds to wake up if it has been idle.

---

## ✨ What it does

Drop in **any video** — a YouTube link or a file sitting on your machine — and get back a fully structured breakdown of what was said, no manual note-taking required.

| 📥 Input | ⚙️ Pipeline | 📤 Output |
|---|---|---|
| YouTube URL or local file | Download → Convert → Chunk → Transcribe → Analyze | Title, Summary, Action Items, Decisions, Open Questions, Full Transcript, Live Chat |

---

## 🧩 Features

**📄 Overview**
- Auto-generated meeting **title**
- Concise AI **summary** of the whole recording
- ✅ **Action items** with owner + deadline (when mentioned)
- 🔑 **Key decisions** made during the meeting
- ❓ **Open questions** flagged for follow-up

**🔍 Details**
- Full raw **transcript**, searchable

**💬 Chat**
- Ask anything about the meeting — answered **only from the transcript** via a retrieval-augmented (RAG) chain, so no hallucinated answers

**🎨 Custom front end**
- A custom HTML meeting stage embedded in Streamlit as a component, on top of the standard tabbed results

---

## 🏗️ How it works

```
YouTube URL / Local File
        │
        ▼
 ┌───────────────┐     yt-dlp + ffmpeg
 │ Download/Load │────────────────────┐
 └───────────────┘                    │
        │                             ▼
        ▼                     Convert to WAV audio
 ┌───────────────┐
 │ Chunk Audio   │  (fixed-length segments via pydub)
 └───────────────┘
        │
        ▼
 ┌───────────────┐     Whisper speech-to-text
 │ Transcribe    │────────────────────┐
 └───────────────┘                    │
        │                             ▼
        ▼                    Full transcript (joined chunks)
 ┌───────────────────────────────────────────┐
 │  LLM  ×  LangChain                         │
 │  ├── Title generation                      │
 │  ├── Summary                               │
 │  ├── Action items / Decisions / Questions  │
 │  └── RAG chain (Chroma + HF Embeddings)    │
 └───────────────────────────────────────────┘
        │
        ▼
   Streamlit UI  (Overview · Details · Chat)
```

---

## 🚀 Getting started

### 1. Clone & set up environment

```bash
git clone https://github.com/AsadHamzaZahid/ai-meeting-intelligence-on-the-go.git
cd ai-meeting-intelligence-on-the-go

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r Requirements.txt
```

> **ffmpeg is required** for audio extraction. Check with `ffmpeg -version`.
> Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg`

### 2. Add your API key

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_api_key_here
```

> Never commit your `.env` file. It is already listed in `.gitignore`.

### 3. Run it

**Streamlit UI:**
```bash
streamlit run streamlit_app.py
```
Open `http://localhost:8501` in your browser.

**CLI:**
```bash
python main.py
```

---

## 📁 Project structure

```
.
├── streamlit_app.py         # Streamlit UI — input, tabbed results, chat
├── main.py                  # Pipeline orchestrator (run_pipeline, CLI entry point)
├── core/
│   ├── transcriber.py       # Speech-to-text transcription
│   ├── summarizer.py        # Title + summary generation
│   ├── extractor.py         # Action items / decisions / questions
│   ├── vector_store.py      # Chroma vector store + embeddings
│   └── rag_engine.py        # LangChain RAG chain for meeting Q&A
├── utils/
│   └── audio_processor.py   # Download, convert, chunk audio
├── frontend/                # Custom HTML component (meeting stage)
├── Requirements.txt
├── packages.txt             # System packages for cloud deploys (ffmpeg)
└── .gitignore
```

---

## 🛠️ Tech stack

- **Streamlit** — UI
- **yt-dlp + ffmpeg** — video/audio download & extraction
- **pydub** — audio conversion & chunking
- **Whisper** — speech-to-text
- **LangChain** — orchestration
- **Groq LLM** — summarization, extraction, Q&A
- **ChromaDB + HuggingFace Embeddings** — vector store for RAG

---

## 🧯 Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'utils.audio_processor'` | Another package called `utils` is installed in your Python. Run `pip uninstall utils`, or use a clean virtual environment. |
| `No module named 'langchain_chroma'` (or similar) | `pip install langchain-chroma langchain-huggingface langchain-groq yt-dlp pydub python-dotenv` |
| Audio extraction fails | Make sure `ffmpeg` is installed and on your PATH. |
| App closes silently on Windows | Use a fresh venv and test imports with `python -X faulthandler -c "import main"` to find the crashing library. |

---

## ⚠️ Notes

- Longer videos take longer to transcribe, especially on CPU.
- On a hosted deployment, resources are limited, so long videos may be slow.
- Only the transcript text is sent to the LLM provider for analysis.
- This is a personal/practice project exploring an end-to-end AI pipeline — not hardened for production use.

---

<div align="center">

Built with 🧡 and 🌿 — orange for effort, mint for clarity.

</div>
