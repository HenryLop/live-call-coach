"""Optional audio source: transcribe a recording with faster-whisper on the CPU or a GPU.

    pip install faster-whisper
    python -m live_call_coach --mode interview --audio call.wav

Not needed for the demo or the tests. The model is downloaded by faster-whisper on first use.
"""


def transcribe(path, model_size="base", speaker="Interviewer"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("faster-whisper is not installed: pip install faster-whisper")
    model = WhisperModel(model_size, compute_type="int8")
    segments, _ = model.transcribe(path)
    return [{"t": round(s.end, 2), "speaker": speaker, "text": s.text.strip()} for s in segments]
