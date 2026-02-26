import os
from livekit.plugins import openai, cartesia
from livekit.agents import inference


def build_personal_tts(logger):
    """
    Build a tuned TTS instance for this project.

    Providers:
    - openai
    - cartesia
    - gemini
    - livekit

    Styles:
    - professional
    - warm
    - concise
    """
    provider = os.getenv("TTS_PROVIDER", "openai").lower()
    style = os.getenv("PERSONAL_TTS_STYLE", "professional").lower()

    if provider == "cartesia":
        logger.info("Using Cartesia TTS")
        model = os.getenv("CARTESIA_TTS_MODEL", "sonic-2")
        voice = os.getenv("CARTESIA_TTS_VOICE", "f786b574-daa5-4673-aa0c-cbe3e8534c02")
        return cartesia.TTS(model=model, voice=voice)

    if provider == "gemini":
        logger.info("Using Gemini TTS")
        model = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
        voice = os.getenv("GEMINI_TTS_VOICE", "Puck")
        speed = float(os.getenv("GEMINI_TTS_SPEED", "1.0"))
        instructions = os.getenv("GEMINI_TTS_INSTRUCTIONS", "")
        return openai.TTS(
            model=model,
            voice=voice,
            speed=speed,
            instructions=instructions,
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
        )

    if provider == "livekit":
        logger.info("Using LiveKit Inference TTS")
        model = os.getenv("LIVEKIT_INFERENCE_TTS_MODEL", "deepgram/aura")
        voice = os.getenv("LIVEKIT_INFERENCE_TTS_VOICE", "").strip()
        language = os.getenv("LIVEKIT_INFERENCE_TTS_LANGUAGE", "").strip()
        kwargs = {}
        if voice:
            kwargs["voice"] = voice
        if language:
            kwargs["language"] = language
        return inference.TTS(model=model, **kwargs)

    logger.info("Using OpenAI TTS")
    model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.getenv("OPENAI_TTS_VOICE", "ash")
    speed = float(os.getenv("OPENAI_TTS_SPEED", "1.1"))
    instructions = os.getenv("OPENAI_TTS_INSTRUCTIONS", "")

    if not instructions:
        if style == "warm":
            instructions = "Speak warmly, naturally, and politely with calm pacing."
        elif style == "concise":
            instructions = "Speak clearly and briefly with a professional tone."
        else:
            instructions = "Speak in a polished, confident, professional business tone."

    return openai.TTS(
        model=model,
        voice=voice,
        speed=speed,
        instructions=instructions,
    )
