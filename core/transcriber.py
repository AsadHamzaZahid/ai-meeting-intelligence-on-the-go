import os
import time
import requests
from pydub import AudioSegment


def _key():
    k = os.getenv("GROQ_API_KEY")
    return k.strip().strip('"').strip("'") if k else None


GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")   # local fallback only
# only used if a chunk is large
PIECE_SECONDS = 120

LANG = {"english": "en", "hinglish": "en", "urdu": "ur", "hindi": "hi",
        "arabic": "ar", "spanish": "es", "french": "fr", "german": "de"}

_model = None


def load_model():
    """Local Whisper, loaded once. Imported lazily so the deployed app does not need it."""
    global _model
    if _model is None:
        import whisper
        print(f"Loading Whisper model: {WHISPER_MODEL} ...")
        _model = whisper.load_model(WHISPER_MODEL)
    return _model


def transcribe_chunk_local(chunk_path: str, language: str) -> str:
    code = LANG.get(language.lower(), "en")
    return load_model().transcribe(chunk_path, task="transcribe", language=code)["text"]


def _send_to_groq(path: str, language: str) -> str:
    headers = {"Authorization": f"Bearer {_key()}"}
    for attempt in range(4):
        with open(path, "rb") as f:
            r = requests.post(
                GROQ_STT_URL, headers=headers,
                files={"file": (os.path.basename(path), f, "audio/wav")},
                data={"model": GROQ_MODEL, "language": LANG.get(language.lower(), "en"),
                      "response_format": "json"},
                timeout=120)
        if r.status_code == 429 and attempt < 3:        # rate limited: wait and retry
            time.sleep(float(r.headers.get("retry-after", 3 + attempt * 3)))
            continue
        if not r.ok:
            print(f"Groq returned {r.status_code}: {r.text[:300]}")
            r.raise_for_status()
        return r.json().get("text", "")
    return ""


def transcribe_chunk_groq(chunk_path: str, language: str) -> str:
    # under Groq's upload limit: send the whole chunk
    if os.path.getsize(chunk_path) <= 20 * 1024 * 1024:
        return _send_to_groq(chunk_path, language).strip()
    audio = AudioSegment.from_wav(
        chunk_path).set_frame_rate(16000).set_channels(1)
    step, text = PIECE_SECONDS * 1000, []
    for i, start in enumerate(range(0, len(audio), step)):
        p = f"{chunk_path}_gq_{i}.wav"
        audio[start:start + step].export(p, format="wav")
        try:
            text.append(_send_to_groq(p, language))
        finally:
            if os.path.exists(p):
                os.remove(p)
    return " ".join(text).strip()


def transcribe_chunk(chunk_path: str, language: str = "english") -> str:
    if _key():
        return transcribe_chunk_groq(chunk_path, language)
    return transcribe_chunk_local(chunk_path, language)


def transcribe_all(chunks: list, language: str = "english") -> str:
    engine = "Groq API" if _key() else "local Whisper (GROQ_API_KEY not found)"
    print(f"Using {engine} for transcription.")
    out = []
    for i, chunk in enumerate(chunks):
        print(f"Transcribing chunk {i + 1}/{len(chunks)}...")
        out.append(transcribe_chunk(chunk, language))
    print("Transcription complete.")
    return " ".join(out).strip()
