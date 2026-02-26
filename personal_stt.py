import os
from livekit.agents import inference


def build_personal_stt():
    """
    Build a tuned STT instance using LiveKit Inference.

    Profiles:
    - fast: lowest latency
    - balanced: good latency + stability
    - accurate: better punctuation/formatting, slightly slower
    """
    profile = os.getenv("PERSONAL_STT_PROFILE", "balanced").lower()
    model = os.getenv("LIVEKIT_INFERENCE_STT_MODEL", "deepgram/nova-3")
    language = os.getenv("LIVEKIT_INFERENCE_STT_LANGUAGE", "multi")

    endpointing = int(os.getenv("LIVEKIT_INFERENCE_ENDPOINTING_MS", "25"))
    punctuate = False
    smart_format = False

    if profile == "fast":
        endpointing = int(os.getenv("LIVEKIT_INFERENCE_ENDPOINTING_MS", "20"))
    elif profile == "accurate":
        endpointing = int(os.getenv("LIVEKIT_INFERENCE_ENDPOINTING_MS", "60"))
        punctuate = True
        smart_format = True

    extra_kwargs = {
        "interim_results": True,
        "endpointing": endpointing,
        "punctuate": punctuate,
        "smart_format": smart_format,
    }

    return inference.STT(
        model=model,
        language=language,
        extra_kwargs=extra_kwargs,
    )
