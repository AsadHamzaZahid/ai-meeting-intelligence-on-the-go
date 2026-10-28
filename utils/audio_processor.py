import os
import re
import yt_dlp
import uuid
from pydub import AudioSegment

DOWNLOAD_DIR = 'downloades'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Different YouTube "player clients" to try if one gets a 403
CLIENT_ATTEMPTS = [
    None,                          # yt-dlp defaults
    ["tv", "web_embedded"],
    ["web_safari"],
    ["android_vr"],
]

# Set YTDLP_VERBOSE=1 in your environment to get full yt-dlp logs
YTDLP_VERBOSE = os.getenv("YTDLP_VERBOSE") == "1"


# ---------------------------------------------------------------------------
# Error signal
# ---------------------------------------------------------------------------

# Short, user-friendly text per failure reason.
FRIENDLY_MESSAGES = {
    "bot_check": "YouTube is asking this server to prove it's not a bot.",
    "forbidden": "YouTube refused the download from this server (403).",
    "private": "This video is private.",
    "age_restricted": "This video is age-restricted and can't be fetched.",
    "unavailable": "This video is unavailable or has been removed.",
    "bad_url": "That doesn't look like a valid YouTube link.",
    "ffmpeg_missing": "ffmpeg isn't installed on this server.",
    "network": "Network problem while reaching YouTube.",
    "unknown": "YouTube download failed for an unknown reason.",
}

# These will not get better by trying another player client, so stop early.
PERMANENT_REASONS = {"private", "age_restricted", "unavailable",
                     "bad_url", "ffmpeg_missing"}

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class YouTubeBlockedError(RuntimeError):
    """Raised when a YouTube URL can't be turned into audio.

    Subclasses RuntimeError, so any existing `except RuntimeError` keeps
    working. The UI can also read `.reason` and `.message`, or call
    `.to_dict()` to hand a clean payload to the front end
    (e.g. window.onYtBlocked).
    """

    def __init__(self, reason: str, message: str, detail: str = ""):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "error": "youtube_blocked",
            "reason": self.reason,
            "message": self.message,
        }


def _classify_error(err: Exception) -> str:
    """Map a raw yt-dlp / OS exception to a short reason code."""
    if isinstance(err, FileNotFoundError):
        return "ffmpeg_missing"

    text = _ANSI.sub("", str(err)).lower()

    # Order matters: the age check must come before the bot check, because
    # "Sign in to confirm your age" also contains "sign in to confirm".
    if "confirm your age" in text or "age-restricted" in text \
            or "age restricted" in text:
        return "age_restricted"
    if "private video" in text:
        return "private"
    if "sign in to confirm" in text or "not a bot" in text:
        return "bot_check"
    if "unsupported url" in text or "is not a valid url" in text:
        return "bad_url"
    if any(s in text for s in ("video unavailable", "has been removed",
                               "does not exist", "copyright",
                               "no longer available")):
        return "unavailable"
    if ("ffmpeg" in text or "ffprobe" in text) and \
            any(s in text for s in ("not found", "not installed")):
        return "ffmpeg_missing"
    if "403" in text or "forbidden" in text:
        return "forbidden"
    if any(s in text for s in ("timed out", "timeout", "connection",
                               "network", "temporary failure",
                               "name resolution")):
        return "network"
    return "unknown"


# ---------------------------------------------------------------------------
# YouTube download
# ---------------------------------------------------------------------------

def download_youtube_audio(url: str) -> str:
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    last_err = None
    last_reason = "unknown"

    for clients in CLIENT_ATTEMPTS:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }
            ],
            "retries": 5,
            "fragment_retries": 5,
            "force_ipv4": True,
            "quiet": not YTDLP_VERBOSE,
            "verbose": YTDLP_VERBOSE,
            "noplaylist": True,
        }

        # Optional proxy from Streamlit Secrets (only used if you set it)
        proxy = os.getenv("YTDLP_PROXY")
        if proxy:
            ydl_opts["proxy"] = proxy

        if clients:
            ydl_opts["extractor_args"] = {
                "youtube": {"player_client": clients}}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            return os.path.splitext(filename)[0] + ".wav"
        except Exception as e:
            last_err = e
            last_reason = _classify_error(e)
            print(f"Download attempt failed with clients={clients} "
                  f"[{last_reason}]: {_ANSI.sub('', str(e))[:300]}")
            if last_reason in PERMANENT_REASONS:
                break  # no point trying other clients

    detail = _ANSI.sub("", str(last_err))[:500] if last_err else ""
    raise YouTubeBlockedError(
        reason=last_reason,
        message=FRIENDLY_MESSAGES[last_reason],
        detail=detail,
    ) from last_err


# ---------------------------------------------------------------------------
# Rest of the pipeline (unchanged)
# ---------------------------------------------------------------------------

def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV. Written to the downloads folder
    with a unique name, so samples are never modified and two jobs on the
    same sample cannot clash."""
    output_path = os.path.join(
        DOWNLOAD_DIR, f"{uuid.uuid4().hex}_converted.wav")
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")
    return output_path


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start: start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")

        chunks.append(chunk_path)

    return chunks


def process_input(source: str) -> list:
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        # may raise YouTubeBlockedError
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks
