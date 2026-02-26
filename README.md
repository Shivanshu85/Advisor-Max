# LiveKit Outbound Calling Agent

This project provides a production-ready solution for making outbound AI phone calls using LiveKit and Vobiz SIP trunks. The AI agent can place calls, wait for an answer, and hold a natural conversation with the recipient.

## 📂 Project Structure

| File | Description |
|------|-------------|
| `agent.py` | The main AI worker. It runs in the background, waits for dispatch jobs, and places outbound calls. |
| `make_call.py` | A utility script to trigger calls. It dispatches the agent to a unique room with the target phone number. |
| `setup_trunk.py` | Script to configure the LiveKit SIP Trunk with Vobiz credentials. |
| `transfer_call.md` | Guide for configuring and using SIP transfers. |
| `.env.example` | Template for environment variables and secrets. |
| `requirements.txt` | List of Python dependencies. |

---

## 🚀 Installation & Setup

### 1. Prerequisites

Ensure you have the following installed:
- **Python 3.9+**
- **uv** (recommended for fast package management) - [Install uv](https://github.com/astral-sh/uv)

### 2. LiveKit & Vobiz Credentials

You will need the following accounts:

1.  **LiveKit Cloud Account**: Get your Project URL, API Key, and Secret from [cloud.livekit.io](https://cloud.livekit.io).
2.  **Vobiz Account**:
    *   Log in to the **Vobiz Console Platform**.
    *   Navigate to your SIP Trunk settings to find:
        *   SIP Domain (e.g., `xxx.sip.vobiz.ai`)
        *   Username & Password
    *   Get your DID Number (e.g., `+91...`).
3.  **Model Provider Keys (Optional)**:
    *   By default this project uses **LiveKit Inference** for LLM/STT/TTS.
    *   If you switch provider in `.env`, add provider-specific keys (Gemini/OpenAI/Cartesia).

### 3. Installation Steps

1.  **Clone/Copy the project** to your local machine.
2.  **Open a terminal** in the project folder (`livekit-outbound-calls`).
3.  **Install dependencies** using `uv`:

    ```powershell
    # Create virtual environment
    uv venv

    # Install required packages
    uv pip install -r requirements.txt
    ```

### 4. Configuration

1.  **Create your env file**:
    ```powershell
    cp .env.example .env
    ```
2.  **Edit `.env`** and fill in your keys:
    ```env
    LIVEKIT_URL=wss://...
    LIVEKIT_API_KEY=...
    LIVEKIT_API_SECRET=...
    LLM_PROVIDER=livekit
    TTS_PROVIDER=livekit
    
    # SIP Config
    VOBIZ_SIP_DOMAIN=...
    VOBIZ_USERNAME=...
    VOBIZ_PASSWORD=...
    VOBIZ_OUTBOUND_NUMBER=+91...
    OUTBOUND_TRUNK_ID=ST_...
    ```
3.  **Set calling safety toggle in `.env`**:
    *   Keep `ENABLE_OUTBOUND_CALLS=false` while testing config.
    *   Set `ENABLE_OUTBOUND_CALLS=true` only when you are ready to place live calls.

---

## 📞 How to Use

### Step 1: Start the Background Agent

Open a PowerShell terminal and run:

```powershell
uv run python agent.py start
```

*   **Wait** until you see the message: `INFO:livekit.agents:registered worker ...`
*   **Keep this terminal open.** This agent will listen for call requests.

### Step 2: Make a Call

Open a **separate** terminal window (keep the first one running) and run:

```powershell
uv run python make_call.py --to +919988776655 (your number)
```

*(Replace `+919988776655` with the actual number you want to call)*

### What Happens Next?

1.  `make_call.py` sends a "dispatch" request to LiveKit.
2.  LiveKit assigns the job to your running `agent.py`.
3.  The agent joins a secure room (e.g., `call-9148...`).
4.  The agent dials the phone number via the Vobiz SIP trunk.
5.  **When the user answers**, the agent will start listening and speaking.
6.  **Call Transfer**: You can ask the agent to transfer you.
    *   *Default*: "Transfer me." -> Transfers to the configured default number.
    *   *Custom*: "Transfer me to +1..." -> Transfers to the specific number.
    *   For detailed setup and troubleshooting, see [transfer_call.md](transfer_call.md).

---

## 🛠️ Troubleshooting

- **Agent not starting?**
    - Check `.env` is correct.
    - Ensure dependencies are installed (`uv pip install ...`).

- **Call not connecting?**
    - Check `OUTBOUND_TRUNK_ID` in `agent.py`.
    - Verify your Vobiz SIP credentials and balance.
    - Ensure the phone number includes the country code (e.g., `+91`).

- **No audio?**
    - If using non-LiveKit providers, check provider API keys.
    - Check the agent logs for errors.
# Advisor-Max
