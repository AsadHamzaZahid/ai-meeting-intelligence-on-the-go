import os
import yt_dlp
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


def download_youtube_audio(url: str) -> str:
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    last_err = None

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
            "quiet": False,
            "verbose": True,       # remove later once it works
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
            print(f"Download attempt failed with clients={clients}: {e}")

    raise RuntimeError(
        "YouTube refused the download from this server. "
        "Please upload the video file instead."
    ) from last_err


def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)  # 16khz
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
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks
