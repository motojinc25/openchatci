# OpenChatCi

**Hawaii-built, localhost-first AI agent platform** powered by [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)

OpenChatCi is a **local AI agent runtime and UI** that connects modern agent frameworks through the **AG-UI protocol**.

Run powerful AI agents **directly on localhost** with a modern UI, streaming responses, and tool integrations.

---

## 🌊 Architecture

The platform connects the UI and agent runtime through the AG-UI protocol.

<p align="center">
<img src="assets/images/diagram1.jpg">
</p>

## 🏝 UI Preview

<p align="center">
<img src="assets/images/screenshot1.png">
<img src="assets/images/screenshot2.png">
<img src="assets/images/screenshot3.png">
</p>
<p align="center">
<sub>Weather Tools · Mermaid Diagrams · Image Analysis</sub>
</p>

---

## ✨ Features

- Chat with AI agents via AG-UI protocol (SSE streaming)
- Rich message rendering: Markdown, code blocks, math (KaTeX), Mermaid diagrams
- LLM reasoning visualization with collapsible thinking blocks
- Web search with inline citation links
- Voice input via microphone with Whisper transcription
- Text-to-Speech playback and download via ElevenLabs
- Multimodal image analysis (file attachment, drag-and-drop, URL)
- Weather tools with rich card widgets (Open-Meteo, no API key)
- Coding tools (file read/write, shell execution, file search)
- Prompt Templates: save, manage, and insert reusable prompts from "+" menu and message actions
- Agent Skills: portable domain knowledge packages with progressive disclosure
- Session management: save, search, pin, archive, fork, rename
- Background Responses: long-running agent timeout prevention with stream resumption
- Context window consumption display with warning levels
- Per-turn token usage display
- Three layout scenarios: Chat, Popup, Sidebar

---

## 🚀 Quick Start (pip install)

```bash
pip install openchatci
openchatci init
# Edit .env and set AZURE_OPENAI_ENDPOINT
az login
openchatci
```

Open:

```
http://localhost:8000/chat
```

---

## 🧑‍💻 Development Setup

### Prerequisites

| Tool      | Version | Install                                                                                                            |
| --------- | ------- | ------------------------------------------------------------------------------------------------------------------ |
| Node.js   | 22+     | [https://nodejs.org/](https://nodejs.org/)                                                                         |
| pnpm      | 10+     | `npm install -g pnpm`                                                                                              |
| Python    | 3.12+   | [https://www.python.org/](https://www.python.org/)                                                                 |
| uv        | 0.9+    | [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)                                                           |
| Azure CLI | 2.x     | [https://learn.microsoft.com/cli/azure/install-azure-cli](https://learn.microsoft.com/cli/azure/install-azure-cli) |

---

### 1. Azure Authentication

The backend authenticates to Azure OpenAI via `AzureCliCredential`.
You must log in before starting.

```bash
az login
```

Select the subscription if needed:

```bash
az account set --subscription <subscription-id>
```

---

### 2. Backend Setup

**Windows (PowerShell):**

```powershell
cd backend
copy .env.sample .env
# Edit .env and set your Azure OpenAI endpoint
notepad .env
uv sync --prerelease=allow
```

**macOS / Linux:**

```bash
cd backend
cp .env.sample .env
# Edit .env and set your Azure OpenAI endpoint
nano .env
uv sync --prerelease=allow
```

`.env` configuration (required):

```
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-5.4
```

---

### 3. Frontend Setup

```bash
cd frontend
pnpm install
```

---

### 4. Start Development Servers

Open two terminals:

**Terminal 1 -- Backend:**

```bash
cd backend
uv run uvicorn app.main:app --reload --app-dir src
```

Backend starts at [http://localhost:8000](http://localhost:8000)

**Terminal 2 -- Frontend:**

```bash
cd frontend
pnpm dev
```

Frontend dev server starts at [http://localhost:5173](http://localhost:5173)
(API requests are proxied to the backend)

---

### 5. Production Build

```bash
cd frontend
pnpm build

cd ../backend
uv run uvicorn app.main:app --app-dir src
```

The backend serves both frontend build artifacts and the API at [http://localhost:8000](http://localhost:8000)

---

## CLI Usage

```
openchatci                    Start the server
openchatci init               Generate .env from template
openchatci init --force       Overwrite existing .env
openchatci --host 0.0.0.0     Bind to all interfaces
openchatci --port 9000        Use custom port
openchatci --skip-auth-check  Skip Azure CLI login check
openchatci --version          Show version
```

---

## 🧰 Tech Stack

| Layer    | Technology                   | Purpose                        |
| -------- | ---------------------------- | ------------------------------ |
| Frontend | React 19 + TypeScript + Vite | UI framework                   |
| Frontend | Tailwind CSS + shadcn/ui     | Styling + Components           |
| Frontend | Biome                        | Format + Lint                  |
| Backend  | FastAPI + Python 3.12+       | API server                     |
| Backend  | Microsoft Agent Framework    | Agent execution + Tool control |
| Backend  | Ruff                         | Format + Lint                  |
| Package  | uv                           | Python dependency management   |
| Package  | pnpm                         | Node.js dependency management  |

---

## Optional Features

### Prompt Templates

Save and reuse prompt templates from the chat interface:

```
TEMPLATES_DIR=.templates
```

- Click **+** button > **Use template** to open the management modal
- Create, edit, delete templates with name, category, and body
- **Insert to Chat** pastes the template into the input (editable before send)
- Click the **FileText** icon on any user message to save it as a template

Templates are stored as individual JSON files in the configured directory.

---

### Coding Tools

Enable AI-powered file operations and shell execution:

```
CODING_ENABLED=true
CODING_WORKSPACE_DIR=C:\path\to\workspace
```

---

### Text-to-Speech

Enable on-demand TTS for messages via [ElevenLabs](https://elevenlabs.io/):

```
ELEVENLABS_API_KEY=your-api-key
TTS_MODEL_ID=eleven_multilingual_v2
TTS_VOICE_ID=your-voice-id
```

Speaker button plays audio, download button saves MP3 file. Audio is cached to avoid duplicate API calls.

---

### Agent Skills

Extend the agent with domain knowledge packages ([Agent Skills specification](https://agentskills.io/)):

```
SKILLS_DIR=.skills
```

Place `SKILL.md` files in subdirectories. The agent discovers and loads skills on demand:

```
.skills/
  my-skill/
  ├── SKILL.md          # Required: instructions + metadata
  ├── scripts/          # Optional: executable code
  ├── references/       # Optional: documentation
  └── assets/           # Optional: templates, resources
```

Skills use progressive disclosure to minimize context window consumption (~100 tokens per skill when idle).

---

### Background Responses

For long-running agent operations (e.g., o3/o4-mini reasoning models), enable Background Responses to prevent timeouts:

1. Click the **BG** toggle button (left of the context window indicator)
2. ChatInput border turns blue when active
3. Continuation tokens are auto-saved to session for page reload resumption

No environment variable needed -- toggle on/off per session via the UI.

---

### Context Window

Configure the model's context window size for the consumption progress bar:

```
MODEL_MAX_CONTEXT_TOKENS=1050000
```

The progress bar shows consumption rate above the chat input. Colors change at 80% (amber) and 95% (red).

---

### DevUI

Enable Microsoft Agent Framework DevUI for debugging:

```
DEVUI_ENABLED=true
DEVUI_PORT=8080
```

Access at [http://localhost:8080](http://localhost:8080)

---

## Supported Platforms

* Windows 10/11
* macOS (Intel / Apple Silicon)
* Linux (Ubuntu, Debian, etc.)

---

## License

[Apache-2.0](LICENSE.md)
