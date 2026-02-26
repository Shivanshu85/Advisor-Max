import argparse
import asyncio
import os
import random
import json
import sys
import re

# Prefer project-local virtualenv packages even when invoked as `python ...`.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_VENV_SITE_PACKAGES = os.path.join(_PROJECT_ROOT, ".venv", "Lib", "site-packages")
if os.path.isdir(_VENV_SITE_PACKAGES) and _VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, _VENV_SITE_PACKAGES)

from dotenv import load_dotenv
from livekit import api

# Load environment variables with local override support.
load_dotenv(".env.local")
load_dotenv(".env")

async def main():
    outbound_enabled = os.getenv("ENABLE_OUTBOUND_CALLS", "false").lower() == "true"
    if not outbound_enabled:
        print("Outbound calling is disabled. Set ENABLE_OUTBOUND_CALLS=true to allow calls.")
        return

    parser = argparse.ArgumentParser(description="Make an outbound call via LiveKit Agent.")
    parser.add_argument("--to", required=True, help="The phone number to call (e.g., +91...)")
    args = parser.parse_args()

    # 1. Validation
    digits = re.sub(r"\D", "", args.to.strip())
    phone_number = f"+{digits}" if digits else ""
    if not phone_number:
        print("Error: phone number is empty after normalization.")
        return

    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    trunk_id = os.getenv("OUTBOUND_TRUNK_ID")
    sip_domain = os.getenv("VOBIZ_SIP_DOMAIN")

    if not (url and api_key and api_secret):
        print("Error: LiveKit credentials missing in .env.local")
        return
    if not trunk_id:
        print("Error: OUTBOUND_TRUNK_ID missing. Run setup and set it in .env.local/.env.")
        return
    if not sip_domain:
        print("Error: VOBIZ_SIP_DOMAIN missing in .env.local/.env.")
        return

    # 2. Setup API Client
    lk_api = api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)

    # 3. Create a unique room for this call
    # We use a random suffix to ensure room names are unique
    room_name = f"call-{phone_number.replace('+', '')}-{random.randint(1000, 9999)}"

    print(f"Initiating call to {phone_number}...")
    print(f"Session Room: {room_name}")

    try:
        # Ensure the room exists before dispatching the agent.
        # Some deployments won't assign a dispatch until the room is present.
        try:
            await lk_api.room.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    empty_timeout=300,
                    max_participants=10,
                )
            )
            print(f"Room ready: {room_name}")
        except Exception as room_err:
            room_err_text = str(room_err)
            if "already exists" in room_err_text.lower():
                print(f"Room already exists: {room_name}")
            else:
                raise

        # 4. Dispatch the Agent
        # We explicitly tell LiveKit to send the 'outbound-caller' agent to this room.
        # We pass the phone number in the 'metadata' field so the agent knows who to dial.
        dispatch_request = api.CreateAgentDispatchRequest(
            agent_name="outbound-caller", # Must match agent.py
            room=room_name,
            metadata=json.dumps({"phone_number": phone_number})
        )
        
        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_request)

        print("\nCall dispatched successfully.")
        print(f"Dispatch ID: {dispatch.id}")
        print(f"Agent Name: {dispatch.agent_name}")
        print("-" * 40)
        print("The agent is now joining the room and will dial the number.")
        print("Check your agent terminal for logs.")
        
    except Exception as e:
        print(f"\nError dispatching call: {e}")
    
    finally:
        await lk_api.aclose()

if __name__ == "__main__":
    asyncio.run(main())
