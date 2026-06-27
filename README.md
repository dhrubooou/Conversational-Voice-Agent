# 🎙️ OpenVoice: Production-Grade Conversational Voice Agent Platform

OpenVoice is a robust, modular, event-driven, and highly maintainable real-time voice agent platform. Built following the principles of **Clean Architecture**, it orchestrates LiveKit rooms, conversational LLM dialog, custom database-backed tool execution, real-time WebSocket event broadcasting, and Twilio warm transfers over public telephone networks.

---

## 🏗️ Clean Architecture Overview

The backend is structured into decoupled modules, guaranteeing a clear separation of concerns, testability, and database-agnostic domain models:

```text
backend/app/
├── api/                  # API Layer (FastAPI endpoints, WebSockets, Twilio TwiML Webhooks)
├── core/                 # Core Infrastructure (Pydantic settings, Structured JSON logging, WebSocket managers)
├── db/                   # Database Connectivity (SQLAlchemy engines, session factories, bootstrappers)
├── models/               # Persistence Domain Models (SQLAlchemy declarative schemas)
├── schemas/              # Input/Output DTO schemas (Pydantic validation models)
├── services/             # Pure Business Logic (Twilio outbound calling, OpenAI summaries)
└── agents/               # LiveKit Voice Agent Pipeline (Worker, tools, state publishers)
```

---

## ⚡ Core Technical Capabilities

1. **Sub-second Conversational Pipeline**: Combines Deepgram (STT/TTS), OpenAI (GPT-4o-mini), and Silero VAD into an extremely low-latency audio stream supporting interruptions and overlapping talk.
2. **WebSocket-driven Event Broadcasts**: HTTP polling is completely replaced by a centralized `WebSocketManager`. State updates are persisted to the database and broadcasted in real-time to supervisor dashboards in under a millisecond.
3. **PSTN to WebRTC Audio Gateway Bridge**: Bi-directional linear PCM (16kHz) to telephone Mu-law (8kHz) audio transcoder built with `audioop` over secure WebSockets, enabling real phone representatives to connect to WebRTC rooms instantly.
4. **Twilio Warm Transfer with DTMF Controls**: Places outbound calls to representatives, speaks an AI-generated concise summary of the transcript, and processes `1` (accept) or `2` (decline) DTMF dial pad choices.
5. **Database-backed Tools**: Core LLM functions `check_availability()` and `book_appointment()` read and write to local MySQL schemas with built-in weekend blocking.
6. **Detailed Post-Call summaries**: Evaluates call transcript upon disconnect, generating a beautiful structured markdown summary containing Call Details, Booking codes, and timeline highlights.
7. **Production JSON Logging & Configuration**: Incorporates structured JSON logging formatters and centralized Pydantic settings loading.

---

## ⚙️ Quick Start Installation & Execution

### 📋 Prerequisites
*   **MySQL Server** running locally on port `3306` (with password `254131` or configured differently in `.env`).
*   **LiveKit Cloud Account** (Sign up at [livekit.io](https://livekit.io) for free API keys).
*   **OpenAI API Key** (Get sk-proj keys from [platform.openai.com](https://platform.openai.com)).
*   **Deepgram API Key** (Get sk-ef keys from [console.deepgram.com](https://console.deepgram.com)).
*   **Twilio Account** (Optional - needed only for real warm transfer outbound routing).

---

### Step 1: Configure Environment variables
Create and edit `backend/.env` with your API parameters:

```env
# LiveKit Keys (Get from livekit.io dashboard)
LIVEKIT_URL=wss://YOUR-LIVEKIT-DOMAIN.livekit.cloud
LIVEKIT_API_KEY=api-key-here
LIVEKIT_API_SECRET=api-secret-here

# LLM & Voice Keys
OPENAI_API_KEY=sk-proj-your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key

# Twilio Keys (Optional)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
HUMAN_AGENT_PHONE_NUMBER=+1XXXXXXXXXX

# Connections
PUBLIC_BACKEND_URL=http://localhost:8000
BACKEND_URL=http://localhost:8000

# MySQL Configuration (Default local credentials)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=254131
MYSQL_DB=dental_clinic
```

---

### Step 2: Boot Python Backend Services

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Activate your virtual environment and install packages:
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Launch the FastAPI API & WebSocket broadcaster:
   ```bash
   python -m app.main
   ```
   *FastAPI automatically runs raw SQL schema checkers on startup, creating the database `dental_clinic` and table schemas in local MySQL.*

4. Launch the LiveKit Agent Worker in a second terminal:
   ```bash
   .venv\Scripts\python -m app.agents.worker dev
   ```

---

### Step 3: Run Next.js Frontend App

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Set your environment variables in `frontend/.env.local`:
   ```env
   NEXT_PUBLIC_LIVEKIT_URL=wss://YOUR-LIVEKIT-DOMAIN.livekit.cloud
   ```
4. Start the developer server:
   ```bash
   npm run dev
   ```
   *Dashboard launches on [http://localhost:3000](http://localhost:3000).*

---

## 🧪 Running the Test Suite

We provide a self-contained unit and integration test suite using `pytest` and SQLite in-memory databases. It evaluates schema formats, state updates, transcripts and persistent CRUD boundaries.

To execute the tests:
```bash
cd backend
.venv\Scripts\pytest -v
```

---

## 🎯 Verification and Demos

### 📱 Flow 1: Interactive Caller Interface
1. Load `http://localhost:3000`.
2. Click **Join as Caller** and allow mic permissions.
3. Speak naturally to Agent A: *"My name is Alice Smith, I have a bad toothache, can I book an appointment on Tuesday at 10 AM, and my contact is 555-0199."*
4. Agent A checks MySQL availability, registers the booking, and outputs a confirmation code.

### 📊 Flow 2: Supervisor WebSocket Monitor & Takeover
1. Load `http://localhost:3000` in a separate side-by-side browser window.
2. Click **Join as Watcher** to monitor.
3. WebSockets establish connection instantly. As the caller speaks, view the transcripts populating in real-time, the state transitioning smoothly, and the collected info panel updating dynamically.
4. View the **Live Call Event Timeline** mapping connection, verification, and confirmation milestones as they happen.
5. Click **Take Over Call (Mute Agent A)**. Agent A's track is muted instantly at source, and the watcher's microphone is unmuted. The conversation continues seamlessly between Watcher and Caller.

### 📞 Flow 3: Twilio Warm Transfer and Simulator
1. While speaking to Agent A, say: *"Can I speak to a human?"*
2. The **Live Call Event Timeline** flashes `Outbound Handoff Initiated`.
3. If Twilio credentials are configured, a real outbound call dials. If running in a sandbox, click **Accept (Bridge Call)** or **Decline (Refuse)** on the Watcher's simulator control card.
4. Watch the flow complete:
   *   On **Accept**: Control is bridged to the supervisor, and the timeline transitions to `Human Connected`.
   *   On **Decline**: Agent A returns to the call, saying: *"I apologize, but our teams are currently in a meeting. Is there anything else I can do for you?"*
