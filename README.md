# MCP Local LLM Server

A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes a locally-hosted HuggingFace language model as MCP tools, plus a free weather tool.

## Overview

This server lets any MCP-compatible client (e.g. Claude Desktop, Cursor) use a local HuggingFace model for text generation and chat, without sending data to an external API.

```
src/
├── llm_server.py       # Entry point, argument parsing, server startup
├── model.py            # Model loading, token generation, chat prompt building
├── resources.py        # MCP resource: llm://info
└── tools/
    ├── generate.py     # Tool: generate
    ├── chat.py         # Tool: chat
    ├── weather.py      # Tool: get_weather
    └── agent.py        # Tool: run_agent (autonomous ReAct agent)
```

## Requirements

- Python 3.10+
- A local HuggingFace model directory (e.g. `models/Qwen2.5-7B-Instruct`)
- CUDA-capable GPU recommended for large models

Install dependencies:

```bash
pip install -r requirements.txt
```

For GPU support, install the CUDA build of PyTorch separately:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

## Starting the Server

### stdio transport (default — for MCP clients like Claude Desktop)

```bash
python src/llm_server.py --model models/Qwen2.5-7B-Instruct
```

### HTTP transport (for network clients or testing with curl)

```bash
python src/llm_server.py --model models/Qwen2.5-7B-Instruct --transport http --port 8000
```

**CLI flags**

| Flag | Default | Description |
|---|---|---|
| `--model` | *(required)* | Path to local HuggingFace model directory |
| `--transport` | `stdio` | `stdio` or `http` |
| `--port` | `8000` | Port number (HTTP transport only) |

---

## Tools

### `generate`

Generate text from a raw prompt using the local LLM. The input prompt is **not** included in the returned text.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prompt` | `string` | *(required)* | Input text to continue |
| `max_new_tokens` | `int` | `512` | Maximum tokens to generate |
| `temperature` | `float` | `0.7` | Sampling temperature; `0` = greedy (deterministic) |
| `top_p` | `float` | `0.9` | Nucleus-sampling cumulative probability cutoff |
| `top_k` | `int` | `0` | Top-k vocabulary filter; `0` = disabled |
| `repetition_penalty` | `float` | `1.0` | Penalty for repeating tokens; `1.0` = no penalty |
| `stop_sequences` | `list[string]` | `null` | Strings that halt generation when produced |
| `seed` | `int` | `null` | RNG seed for reproducible outputs |

**Returns:** The generated text as a plain string.

**Example**

```json
{
  "prompt": "The capital of France is",
  "max_new_tokens": 50,
  "temperature": 0
}
```

---

### `chat`

Chat with the local LLM using a conversation history. Applies the model's built-in chat template (falls back to a plain `role: content` format if none is defined).

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `messages` | `list[{"role": string, "content": string}]` | *(required)* | Conversation history. Valid roles: `"system"`, `"user"`, `"assistant"` |
| `max_new_tokens` | `int` | `512` | Maximum tokens to generate |
| `temperature` | `float` | `0.7` | Sampling temperature; `0` = greedy (deterministic) |
| `top_p` | `float` | `0.9` | Nucleus-sampling cumulative probability cutoff |
| `top_k` | `int` | `0` | Top-k vocabulary filter; `0` = disabled |
| `repetition_penalty` | `float` | `1.0` | Penalty for repeating tokens; `1.0` = no penalty |
| `stop_sequences` | `list[string]` | `null` | Strings that halt generation when produced |
| `seed` | `int` | `null` | RNG seed for reproducible outputs |

**Returns:** The assistant's reply as plain text.

**Example**

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the Eiffel Tower?"}
  ],
  "temperature": 0.7,
  "max_new_tokens": 256
}
```

---

### `run_agent`

Run an autonomous [ReAct](https://arxiv.org/abs/2210.03629) agent powered by the local LLM. The agent reasons step by step and calls tools as many times as needed before producing a final answer — no external API required.

**How it works**

```
User goal
   ↓
LLM decides: call a tool or answer?
   ↓ (if tool)
Tool executes → result fed back to LLM
   ↓
LLM decides again … (repeats up to max_steps)
   ↓ (when done)
FINAL answer returned
```

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `goal` | `string` | *(required)* | The task or question for the agent to solve |
| `max_steps` | `int` | `10` | Maximum tool-call iterations before stopping |

**Returns:** The agent's final answer as plain text.

**Tools available to the agent**

| Tool | Description |
|---|---|
| `get_weather` | Fetch current weather for any city |

**Examples**

Single tool call:
```json
{"goal": "What should I wear in Paris today?"}
```

Multi-step (two tool calls):
```json
{"goal": "Compare the weather in London and Tokyo, then tell me which city is warmer."}
```

---

### `get_weather`

Fetch current weather for any location using the free [Open-Meteo API](https://open-meteo.com/). No API key required.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `location` | `string` | *(required)* | City name or region (e.g. `"London"`, `"New York"`, `"Tokyo"`) |
| `units` | `string` | `"metric"` | `"metric"` (°C, km/h) or `"imperial"` (°F, mph) |

**Returns:** A short summary including conditions, temperature, humidity, and wind speed.

**Example output**

```
Weather in London, England, United Kingdom:
  Conditions:  Partly cloudy
  Temperature: 12.3°C
  Humidity:    74%
  Wind:        18.5 km/h
```

---

## Resources

### `llm://info`

Returns metadata about the currently loaded model.

**Example output**

```
path:       models/Qwen2.5-7B-Instruct
device:     cuda
dtype:      torch.float16
parameters: 7.62B
```

---

## Configuring with Claude Desktop

Add the server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "local-llm": {
      "command": "python",
      "args": ["src/llm_server.py", "--model", "models/Qwen2.5-7B-Instruct"],
      "cwd": "/absolute/path/to/mcp-server"
    }
  }
}
```

## Notes

- The model is loaded once at startup and held in memory for the lifetime of the server.
- GPU (CUDA) is used automatically if available; otherwise the model runs on CPU (slower).
- The HTTP transport enables CORS for all origins — restrict `allow_origins` before exposing beyond localhost.
