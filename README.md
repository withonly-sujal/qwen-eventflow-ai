# EventFlow AI

EventFlow AI is an intelligent CLI assistant for the Solace Event Portal. It allows you to explore and query your Event-Driven Architecture (EDA) using natural language.

Built on the Model Context Protocol (MCP) and powered by local LLMs (Ollama), EventFlow AI ensures your data stays private while providing an intuitive way to navigate complex Solace API relationships.


## Prerequisites

1. **Python 3.10+**
2. **[uv](https://github.com/astral-sh/uv)**: An extremely fast Python package and project manager.
3. **[Ollama](https://ollama.com/)**: Must be installed and running locally.
4. **Qwen3 Model**: Pull the required model via Ollama:
   ```bash
   ollama run qwen3:8b
   ```

## Setup

1. **Clone the repository** and navigate to the project root.
2. **Create a `.env` file** in the root directory based on the following template:
   ```env
   # Design-Time (Event Portal) Credentials
   SOLACE_API_TOKEN=your_solace_token_here
   SOLACE_API_BASE_URL=https://api.solace.cloud
   
   # Runtime (Event Broker) Credentials
   SOLACE_SEMPV2_BASE_URL=https://your-broker-url:943
   SOLACE_SEMPV2_VPN=default
   SOLACE_SEMPV2_USERNAME=admin
   SOLACE_SEMPV2_PASSWORD=password
   
   # Ollama Configuration
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_MODEL=qwen3:8b
   ```

## Usage

You can interact with EventFlow AI through the Command-Line Interface (CLI) or the Web User Interface (UI).

### Option A: Command-Line Interface (CLI)
Start the interactive CLI application using `uv`:

```bash
uv run python -m EventFlow_AI.app
```

### Option B: Web User Interface (UI)
Start the FastAPI web server to use the graphical interface:

```bash
uv run python -m uvicorn EventFlow_AI.web_server:app --host 0.0.0.0 --port 8000
```
Then open `http://localhost:8000` in your web browser.

The application will prompt you to select a persona. Once connected, you can type your questions directly into the prompt. 

### Available Commands in CLI
Inside the chat, you can use the following commands:
- `/tools` - View the active tools (Smart Router schemas) provided to the LLM.
- `/persona` - Switch between Admin and End User mode.
- `/clear` - Clear the terminal and conversation history.
- `/help` - View help information.
- `/exit` - Exit the application.