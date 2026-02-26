import asyncio
import os
import sys

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
    # Initialize LiveKit API
    # Credentials (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET) are auto-loaded from .env
    lkapi = api.LiveKitAPI()
    sip = lkapi.sip
    
    trunk_id = os.getenv("OUTBOUND_TRUNK_ID")
    address = os.getenv("VOBIZ_SIP_DOMAIN")
    username = os.getenv("VOBIZ_USERNAME")
    password = os.getenv("VOBIZ_PASSWORD")
    number = os.getenv("VOBIZ_OUTBOUND_NUMBER")
    
    if not trunk_id:
        print("Error: OUTBOUND_TRUNK_ID not found in .env")
        return

    print(f"Updating SIP Trunk: {trunk_id}")
    print(f"  Address: {address}")
    print(f"  Username: {username}")
    print(f"  Numbers: [{number}]")

    try:
        # Update the trunk with the correct credentials and settings
        await sip.update_outbound_trunk_fields(
            trunk_id,
            address=address,
            auth_username=username,
            auth_password=password,
            numbers=[number] if number else [],
        )
        print("\nSIP trunk updated successfully.")
        print("The 'max auth retry attempts' error should be resolved now.")
        
    except Exception as e:
        print(f"\nFailed to update trunk: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())
