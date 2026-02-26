import logging
import os
import json
import sys
import re
import asyncio
import csv
import time

# Prefer project-local virtualenv packages even when invoked as `python ...`.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_VENV_SITE_PACKAGES = os.path.join(_PROJECT_ROOT, ".venv", "Lib", "site-packages")
if os.path.isdir(_VENV_SITE_PACKAGES) and _VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, _VENV_SITE_PACKAGES)

from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, inference
from livekit.plugins import openai
from personal_stt import build_personal_stt
from personal_tts import build_personal_tts

# Load environment variables with local override support.
load_dotenv(".env.local")
load_dotenv(".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")


# TRUNK ID - This needs to be set after you crate your trunk
# You can find this by running 'python setup_trunk.py --list' or checking LiveKit Dashboard
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")
SIP_DOMAIN = os.getenv("VOBIZ_SIP_DOMAIN") 
DEFAULT_PRO_GREETING = (
    "Namaste. Main AdvisorMax se bol raha hoon. "
    "Aap kis shehar ya location mein zameen kharidna chahte hain?"
)
DEFAULT_PROPERTY_CSV_PATH = r"c:\Users\tshiv\Downloads\pan_india_property_listings_2025.csv"


def _validate_runtime_config() -> None:
    required_common = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "OUTBOUND_TRUNK_ID",
    ]
    missing = [k for k in required_common if not os.getenv(k)]

    llm_provider = os.getenv("LLM_PROVIDER", "livekit").lower()
    tts_provider = os.getenv("TTS_PROVIDER", "openai").lower()

    if llm_provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")
    elif llm_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    elif llm_provider == "livekit":
        # Uses LiveKit API key/secret from required_common.
        pass

    if tts_provider == "cartesia" and not os.getenv("CARTESIA_API_KEY"):
        missing.append("CARTESIA_API_KEY")
    elif tts_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    elif tts_provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")
    elif tts_provider == "livekit":
        # Uses LiveKit API key/secret from required_common.
        pass

    # Remove duplicates while preserving readability.
    missing = list(dict.fromkeys(missing))
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def _normalize_phone_number(phone_number: str) -> str:
    """Normalize user-provided phone input to E.164-like +<digits>."""
    digits = re.sub(r"\D", "", phone_number or "")
    if not digits:
        return ""
    return f"+{digits}"


def _participant_identity_for_phone(phone_number: str) -> str:
    """Build a LiveKit-safe participant identity from phone number digits."""
    digits = re.sub(r"\D", "", phone_number or "")
    return f"sip_{digits}" if digits else "sip_unknown"


def _build_llm():
    """Configure a fast default LLM for conversational turns."""
    provider = os.getenv("LLM_PROVIDER", "livekit").lower()
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "180"))

    if provider == "livekit":
        logger.info("Using LiveKit Inference LLM")
        return inference.LLM(
            model=os.getenv("LIVEKIT_INFERENCE_LLM_MODEL", "openai/gpt-4o-mini"),
            extra_kwargs={
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
            },
        )

    if provider == "gemini":
        logger.info("Using Gemini LLM")
        return openai.LLM(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )

    logger.info("Using OpenAI LLM")
    return openai.LLM(
        model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=temperature,
        max_completion_tokens=max_tokens,
    )


def _load_property_brief(max_rows: int = 8) -> str:
    """
    Load a short property brief from CSV for real-estate conversations.
    Safe fallback: returns empty string on any read/parse error.
    """
    csv_path = os.getenv("PROPERTY_CSV_PATH", DEFAULT_PROPERTY_CSV_PATH)
    if not os.path.exists(csv_path):
        return ""

    lines = []
    try:
        with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                lines.append(
                    f"- {row.get('city','')}, {row.get('locality','')}: "
                    f"{row.get('bhk','')} BHK {row.get('property_type','')} "
                    f"{row.get('area_sqft','')} sqft, price {row.get('price','')}, "
                    f"{row.get('sale_rent','')}, amenities: {row.get('amenities','')}"
                )
    except Exception:
        return ""

    if not lines:
        return ""
    return "Available property sample:\n" + "\n".join(lines)


async def _safe_say(session: AgentSession, text: str, timeout: float = 20.0, retries: int = 2) -> bool:
    """Speak text with retry/timeout so call flow does not stall on transient TTS issues."""
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Greeting node: session.say start (attempt {attempt})")
            await asyncio.wait_for(session.say(text), timeout=timeout)
            logger.info("Greeting node: session.say completed")
            return True
        except Exception as e:
            logger.error(f"Greeting TTS failed (attempt {attempt}): {e}")
    return False


async def _safe_generate_reply(
    session: AgentSession, instructions: str, timeout: float = 20.0, retries: int = 2
) -> bool:
    """Generate LLM reply with retry/timeout so call keeps moving."""
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"LLM node: generate_reply start (attempt {attempt})")
            await asyncio.wait_for(session.generate_reply(instructions=instructions), timeout=timeout)
            logger.info("LLM node: generate_reply completed")
            return True
        except Exception as e:
            logger.error(f"Initial LLM follow-up failed (attempt {attempt}): {e}")
    return False


def _format_transfer_destination(destination: str) -> str:
    if "@" not in destination:
        if SIP_DOMAIN:
            clean_dest = destination.replace("tel:", "").replace("sip:", "")
            return f"sip:{clean_dest}@{SIP_DOMAIN}"
        if not destination.startswith("tel:") and not destination.startswith("sip:"):
            return f"tel:{destination}"
        return destination
    if not destination.startswith("sip:"):
        return f"sip:{destination}"
    return destination


async def _transfer_now(ctx: agents.JobContext, phone_number: str | None, reason: str) -> bool:
    enabled = os.getenv("AUTO_TRANSFER_ON_FAILURE", "true").lower() == "true"
    if not enabled:
        logger.warning(f"Auto-transfer disabled. Reason={reason}")
        return False

    destination = os.getenv("DEFAULT_TRANSFER_NUMBER", "").strip()
    if not destination:
        logger.error("Auto-transfer failed: DEFAULT_TRANSFER_NUMBER is missing.")
        return False

    destination = _format_transfer_destination(destination)
    participant_identity = _participant_identity_for_phone(phone_number or "")
    if participant_identity == "sip_unknown":
        for p in ctx.room.remote_participants.values():
            participant_identity = p.identity
            break
    if not participant_identity:
        logger.error("Auto-transfer failed: participant identity not found.")
        return False

    try:
        logger.warning(
            f"Auto-transfer triggered. Reason={reason}, participant={participant_identity}, destination={destination}"
        )
        await ctx.api.sip.transfer_sip_participant(
            api.TransferSIPParticipantRequest(
                room_name=ctx.room.name,
                participant_identity=participant_identity,
                transfer_to=destination,
                play_dialtone=False,
            )
        )
        return True
    except Exception as e:
        logger.error(f"Auto-transfer failed: {e}")
        return False


async def _silence_watchdog(
    ctx: agents.JobContext, phone_number: str | None, activity: dict[str, float]
) -> None:
    threshold = int(os.getenv("SILENCE_TRANSFER_SECONDS", "60"))
    while True:
        await asyncio.sleep(5)
        if time.monotonic() - activity["last_activity"] >= threshold:
            await _transfer_now(ctx, phone_number, f"silence>{threshold}s")
            return


class OutboundAssistant(Agent):

    """
    An AI agent tailored for outbound calls.
    Attempts to be helpful and concise.
    """
    def __init__(self, property_brief: str = "") -> None:
        extra_catalog_rules = ""
        if property_brief:
            extra_catalog_rules = (
                "\n6. Use the provided property catalog when discussing listings. "
                "Do not invent property details.\n"
                f"{property_brief}\n"
            )

        super().__init__(
            instructions="""
            You are AdvisorMax, an Indian real-estate AI calling agent.
            
            Key behaviors:
            1. Speak clearly, politely, and confidently in a real-estate sales tone.
            2. Keep responses short and practical.
            3. Start by confirming this is a good time to discuss property options.
            4. Ask qualification questions one by one: city/locality, budget, BHK, buy vs rent, possession timeline.
            5. Suggest only relevant listings and summarize benefits in plain language.
            6. If the user is not interested, close respectfully without pressure.
            7. If asked, explain you are AdvisorMax, an AI assistant helping with real-estate discovery.
            8. Be Indian-language ready: if the caller speaks Hindi, Bengali, Telugu, Marathi, Tamil,
               Urdu, Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese, or any other Indian language,
               immediately respond in that same language.
            9. If language is unclear, ask one short preference question and continue in the user's chosen language.
            """ + extra_catalog_rules
        )


async def entrypoint(ctx: agents.JobContext):
    """
    Main entrypoint for the agent.
    
    For outbound calls:
    1. Checks for 'phone_number' in the job metadata.
    2. Connects to the room.
    3. Initiates the SIP call to the phone number.
    4. Waits for answer before speaking.
    """
    logger.info(f"Connecting to room: {ctx.room.name}")
    _validate_runtime_config()
    
    # parse the phone number from the metadata sent by the dispatch script
    phone_number = None
    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = _normalize_phone_number(data.get("phone_number", ""))
    except Exception:
        logger.warning("No valid JSON metadata found. This might be an inbound call.")

    property_brief = _load_property_brief()
    if property_brief:
        logger.info("Loaded property catalog context from CSV.")

    # Initialize the Agent Session with plugins

    session = AgentSession(
        stt=build_personal_stt(),
        llm=_build_llm(),
        tts=build_personal_tts(logger),
    )

    # Start the session
    await session.start(room=ctx.room, agent=OutboundAssistant(property_brief=property_brief))

    if phone_number:
        outbound_enabled = os.getenv("ENABLE_OUTBOUND_CALLS", "false").lower() == "true"
        if not outbound_enabled:
            logger.warning("Outbound calling is disabled by configuration. Skipping SIP dial.")
            return

        if not OUTBOUND_TRUNK_ID:
            logger.error("OUTBOUND_TRUNK_ID is missing. Set it in .env.local or .env.")
            ctx.shutdown()
            return
        logger.info(f"Initiating outbound SIP call to {phone_number}...")
        try:
            # Create a SIP participant to dial out
            # This effectively "calls" the phone number and brings them into this room
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=_participant_identity_for_phone(phone_number),
                    wait_until_answered=True, # Important: Wait for pickup before continuing
                )
            )
            logger.info("Call answered! Agent is now listening.")
            activity = {"last_activity": time.monotonic()}
            asyncio.create_task(_silence_watchdog(ctx, phone_number, activity))
            # Guaranteed greeting on pickup.
            greeting = os.getenv("OUTBOUND_GREETING", DEFAULT_PRO_GREETING)
            greeted = await _safe_say(session, greeting)
            if greeted:
                activity["last_activity"] = time.monotonic()
            else:
                transferred = await _transfer_now(ctx, phone_number, "greeting_failed")
                if transferred:
                    return

            # Keep conversation moving with a concise professional follow-up.
            await asyncio.sleep(0.25)
            replied = await _safe_generate_reply(
                session,
                instructions=(
                    "Continue in Hindi unless user chooses another language. "
                    "Ask a clear land-buying qualification question about preferred location."
                ),
            )
            if replied:
                activity["last_activity"] = time.monotonic()
            else:
                transferred = await _transfer_now(ctx, phone_number, "llm_reply_failed")
                if transferred:
                    return

            # Hard fallback when model/TTS pipeline still fails.
            if not greeted and not replied:
                await _transfer_now(ctx, phone_number, "both_greeting_and_reply_failed")
            
        except Exception as e:
            logger.error(f"Failed to place outbound call: {e}")
            # Ensure we clean up if the call fails
            ctx.shutdown()
    else:
        # Fallback for inbound calls (if this agent is used for that)
        logger.info("No phone number in metadata. Treating as inbound/web call.")
        await _safe_say(session, "Hello, this is the Vobiz assistant. How can I help you today?")
        await _safe_generate_reply(session, "Greet the user professionally.")


if __name__ == "__main__":
    # The agent name "outbound-caller" is used by the dispatch script to find this worker
    worker_port = int(os.getenv("AGENT_PORT", "0"))
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
            port=worker_port,
        )
    )
