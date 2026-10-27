import whisper
import os
import requests
from pydub import AudioSegment

# Groq's transcription endpoint handles short pieces seamlessly.
# Slicing each chunk into 25s pieces (with a 5s safety margin) before sending.
GROQ_PIECE_SECONDS = 25

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

# Configured for Groq API Cloud execution
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_STT_URL = "https://groq.com"
GROQ_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")

_model = None


def load_model():
    global _model

    if _model is None:
        print(f"Loading Whisper model: {WHISPER_MODEL} ...")
        _model = whisper.load_model(WHISPER_MODEL)
        print("Whisper model loaded.")
    return _model


def transcribe_chunk_whisper(chunk_path: str) -> str:
    model = load_model()

    result = model.transcribe(chunk_path, task="transcribe")
    return result["text"]


def _send_to_groq(piece_path: str) -> str:
    """Send one ≤30s WAV file to Groq and return the English transcript."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    with open(piece_path, "rb") as f:
        files = {"file": (os.path.basename(piece_path), f, "audio/wav")}
        data = {
            "model": GROQ_MODEL,
            "language": "en",
            "response_format": "json"
        }
        response = requests.post(
            GROQ_STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )

    if not response.ok:
        print(f"\n❌ Groq returned {response.status_code}")
        print(f"Response body: {response.text}\n")
        response.raise_for_status()

    return response.json().get("text", "")


def transcribe_chunk_groq(chunk_path: str) -> str:
    """
    Groq sync API execution. We split this chunk into
    25-second pieces, send each separately, and join the transcripts.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in environment / .env")

    audio = AudioSegment.from_wav(chunk_path)
    piece_ms = GROQ_PIECE_SECONDS * 1000

    full_text = ""
    total_pieces = (len(audio) + piece_ms - 1) // piece_ms

    for i, start in enumerate(range(0, len(audio), piece_ms)):
        piece = audio[start: start + piece_ms]
        piece_path = f"{chunk_path}_gq_{i}.wav"
        piece.export(piece_path, format="wav")

        try:
            print(f"  → Groq piece {i + 1}/{total_pieces} ...")
            full_text += _send_to_groq(piece_path) + " "
        finally:
            if os.path.exists(piece_path):
                os.remove(piece_path)

    return full_text.strip()


def transcribe_chunk(chunk_path: str, language: str = "english") -> str:
    """
    Route one chunk to Whisper or Groq depending on language choice.
    - english  → Whisper (local model)
    - hinglish → Groq cloud endpoint
    """
    if language.lower() == "hinglish":
        return transcribe_chunk_groq(chunk_path)
    return transcribe_chunk_whisper(chunk_path)


def transcribe_all(chunks: list, language: str = "english") -> str:
    full_transcript = ""

    engine = "Groq API" if language.lower() == "hinglish" else "Whisper"
    print(f"Using {engine} for transcription.")

    for i, chunk in enumerate(chunks):
        print(f"Transcribing chunk {i + 1}/{len(chunks)}...")
        text = transcribe_chunk(chunk, language=language)
        full_transcript += text + " "

    print("Transcription complete.")
    return full_transcript.strip()
