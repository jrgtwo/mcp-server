# MCP Local LLM Server

A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes a locally-hosted [llama.cpp](https://github.com/ggerganov/llama.cpp) language model as MCP tools, plus a suite of utility tools for weather, news, web fetching, PDF reading, and more.

## Overview

This server lets any MCP-compatible client (e.g. Claude Desktop, Cursor) use a local GGUF model for text generation and chat, without sending data to an external API. The model is served by a `llama-server` subprocess; the MCP server communicates with it over a local HTTP port.

```
src/
├── llm_server.py       # Entry point, argument parsing, server startup
├── model.py            # llama-server lifecycle, token generation
├── upload.py           # POST /upload endpoint for PDF and Markdown file uploads
├── resources.py        # MCP resource: llm://info
└── tools/
    ├── generate.py     # Tool: generate
    ├── chat.py         # Tool: chat
    ├── weather.py      # Tool: get_weather
    ├── date_time.py    # Tool: get_datetime
    ├── fetch_url.py    # Tool: fetch_url
    ├── news.py         # Tool: news_headlines
    ├── read_pdf.py     # Tool: read_pdf
    ├── read_markdown.py # Tool: read_markdown
    ├── agent.py        # Tool: run_agent (autonomous ReAct agent)
    ├── explain_code.py # Tool: explain_code (coding tutor)
    ├── review_code.py  # Tool: review_code  (coding tutor)
    └── coding_tutor.py # Tool: coding_tutor (orchestrating tutor agent)
```

## Requirements

- Python 3.10+
- A `llama-server` binary from [llama.cpp](https://github.com/ggerganov/llama.cpp/releases)
- A GGUF model file (e.g. `models/Qwen2.5-7B-Instruct-Q4_K_M.gguf`)
- CUDA-capable GPU recommended for large models

Install dependencies:

```bash
pip install -r requirements.txt
```

On Windows, IANA timezone data is not bundled with Python. Install it for the `get_datetime` tool to support non-UTC timezones:

```bash
pip install tzdata
```

## Configuration

Some tools require API keys. Create a `.env` file in the project root (it is already gitignored):

```
NEWSAPI_KEY=your_key_here
```

The server loads this file automatically on startup. Keys are never committed to version control.

| Variable | Required by | Where to get it |
|---|---|---|
| `NEWSAPI_KEY` | `news_headlines` | [newsapi.org](https://newsapi.org) — free tier available |

---

## Starting the Server

### stdio transport (for MCP clients like Claude Desktop)

```bash
python src/llm_server.py \
  --model models/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --llama-server /path/to/llama-server
```

### HTTP transport (for network clients or testing with curl)

```bash
python src/llm_server.py \
  --model models/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --llama-server /path/to/llama-server \
  --transport http \
  --port 5174
```

**CLI flags**

| Flag | Default | Description |
|---|---|---|
| `--model` | *(required)* | Path to a `.gguf` file, or a directory containing one |
| `--llama-server` | *(required)* | Path to the `llama-server` executable |
| `--transport` | `stdio` | `stdio` or `http` |
| `--host` | `0.0.0.0` | Host to bind for HTTP transport (use `127.0.0.1` to restrict to localhost) |
| `--port` | `5174` | MCP server port (HTTP transport only) |
| `--server-port` | `8080` | Port for the internal llama-server backend |
| `--gpu-layers` | `-1` | Layers to offload to GPU; `-1` = all |
| `--context-size` | `16384` | Total context window in tokens (prompt + output combined) |

---

## HTTP Endpoints

These endpoints are only available when using `--transport http`.

### `POST /upload`

Upload a PDF or Markdown file to the server and receive an `upload_id` to pass to `run_agent`.

**Supported types:** `.pdf`, `.md`, `.markdown`

**Request:** `multipart/form-data` with a single field named `file`.

**Response:**
```json
{
  "upload_id": "3f8a1c...",
  "filename": "report.pdf",
  "size": 84210
}
```

Uploaded files are stored in the `uploads/` folder at the project root and deleted when the server shuts down.

**Example (curl):**
```bash
curl -X POST http://localhost:5174/upload \
  -F "file=@/path/to/report.pdf"

curl -X POST http://localhost:5174/upload \
  -F "file=@/path/to/notes.md"
```

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

Chat with the local LLM using a conversation history.

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

Run an autonomous [ReAct](https://arxiv.org/abs/2210.03629) agent powered by the local LLM. The agent reasons step by step and calls tools as many times as needed before producing a final answer.

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
| `max_new_tokens` | `int` | `4096` | Token ceiling per LLM call. Tool-call steps stop well before this; it mainly affects the length of the final answer |
| `max_history_pairs` | `int` | `4` | Number of recent assistant+tool rounds to keep in full. Older rounds are summarised to keep the prompt size manageable |
| `summary_strategy` | `string` | `"deterministic"` | How to summarise trimmed history. `"deterministic"` — fast, rule-based bullet points. `"llm"` — model-generated prose summary (adds an extra generation call) |
| `upload_id` | `string` | `""` | ID returned by `POST /upload`. When provided, the PDF is read and injected into the agent's context before the loop starts |

**Returns:** The agent's final answer as plain text.

> **Note:** If you see `Max steps (N) reached without a FINAL answer`, the agent used all its iterations without concluding. Either the task needs more steps (increase `max_steps`) or the model looped on tool calls — check the step logs to diagnose.

**Tools available to the agent**

| Tool | Description |
|---|---|
| `get_weather` | Fetch current weather for any city |
| `get_datetime` | Get the current date and time in any timezone |
| `fetch_url` | Fetch and extract text from any URL |
| `news_headlines` | Fetch the latest news headlines by topic |
| `read_pdf` | Extract text from a PDF file at a given path |
| `read_markdown` | Read the contents of a Markdown file at a given path |

**Examples**

```json
{"goal": "What should I wear in Paris today?"}
```

```json
{"goal": "Compare the weather in London and Tokyo, then tell me which city is warmer."}
```

```json
{"goal": "Summarise this document", "upload_id": "3f8a1c..."}
```

---

### `read_pdf`

Extract and return the text content of a PDF file. Text is organised by page. Image-only (scanned) PDFs will return a clear message rather than empty output.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` | *(required)* | Absolute or relative path to the PDF file |
| `max_chars` | `int` | `8000` | Maximum characters to return before truncating |

**Returns:** Extracted text organised by page, truncated to `max_chars` if needed.

**Example**

```json
{"file_path": "C:/Users/jonat/Documents/report.pdf", "max_chars": 10000}
```

---

### `read_markdown`

Read and return the contents of a Markdown file.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` | *(required)* | Absolute or relative path to the `.md` or `.markdown` file |
| `max_chars` | `int` | `8000` | Maximum characters to return before truncating |

**Returns:** The file's text content, truncated to `max_chars` if needed.

**Example**

```json
{"file_path": "C:/Users/jonat/Documents/notes.md", "max_chars": 5000}
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

### `get_datetime`

Return the current date and time for any IANA timezone. No API key required.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `timezone` | `string` | `"UTC"` | IANA timezone name (e.g. `"America/New_York"`, `"Europe/London"`, `"Asia/Tokyo"`) |

**Returns:** A formatted date/time string, e.g. `"2025-03-01 14:30:00 EST (UTC-0500)"`.

> **Windows note:** Non-UTC timezones require `pip install tzdata`.

**Example**

```json
{"timezone": "America/Chicago"}
```

---

### `fetch_url`

Fetch the content of any URL and return it as plain text. HTML pages are stripped of tags; JSON and plain-text responses are returned as-is. No API key required.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | `string` | *(required)* | URL to fetch (must start with `http://` or `https://`) |
| `max_chars` | `int` | `4000` | Maximum characters to return before truncating |

**Returns:** Extracted page text, truncated to `max_chars` if needed. Returns a descriptive error string if the connection fails (e.g. SSL error, timeout, HTTP error) rather than raising an exception.

**Example**

```json
{"url": "https://en.wikipedia.org/wiki/Python_(programming_language)", "max_chars": 2000}
```

---

### `news_headlines`

Fetch the latest news headlines, optionally filtered by a topic keyword. Requires a free [NewsAPI](https://newsapi.org) key set in `.env`.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `topic` | `string` | `""` | Keyword(s) to filter by (e.g. `"AI"`, `"climate change"`). Leave blank for general top headlines |
| `country` | `string` | `"us"` | 2-letter country code used when `topic` is blank (e.g. `us`, `gb`, `au`, `de`) |
| `max_results` | `int` | `5` | Number of headlines to return (1–10) |

**Returns:** A numbered list of headlines with source name, publication date, and URL.

**Example output**

```
1. [BBC News] Scientists discover new exoplanet
   Published: 2025-03-01
   https://bbc.co.uk/...

2. [Reuters] ...
```

---

## Coding Tutor Tools

Three tools that turn the server into an interactive programming tutor. The high-level entry point is `coding_tutor`; the two supporting tools (`explain_code`, `review_code`) can also be called directly.

### `coding_tutor`

An autonomous [ReAct](https://arxiv.org/abs/2210.03629) agent specialised for teaching. It reasons step by step, calling `explain_code`, `review_code`, and `fetch_url` as needed, then produces a pedagogical answer.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `question` | `string` | *(required)* | Your coding question, code snippet, or error message |
| `max_steps` | `int` | `8` | Maximum tool-call iterations before stopping |
| `max_new_tokens` | `int` | `1024` | Token ceiling per LLM call |
| `max_history_pairs` | `int` | `4` | Recent assistant+tool rounds to keep before older ones are summarised |
| `summary_strategy` | `string` | `"deterministic"` | `"deterministic"` (fast bullet-point summary) or `"llm"` (model-generated prose) |

**Returns:** A teaching response as plain text.

**Examples**

```json
{"question": "Why does my list comprehension give the wrong result?\n\nmy_list = [1, 2, 3]\nresult = [x * 2 for x in my_list if x > 1]"}
```

```json
{"question": "Explain the difference between a shallow copy and a deep copy in Python, with examples."}
```

> **Tip:** The tutor infers your skill level from your question. Use plain language for beginner explanations, or technical terminology to get a more advanced response.

---

### `explain_code`

Explain a code snippet using the local LLM, tailored to the learner's skill level.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `code` | `string` | *(required)* | The source code to explain (capped at 6000 chars) |
| `language` | `string` | `"python"` | Programming language of the snippet |
| `level` | `string` | `"beginner"` | Explanation depth: `"beginner"`, `"intermediate"`, or `"advanced"` |
| `max_new_tokens` | `int` | `768` | Maximum tokens for the explanation |

**Returns:** A plain-text explanation of the code.

---

### `review_code`

Review a code snippet for issues. Outputs a structured report: overall impression, numbered issues with severity, positives, and a top recommendation.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `code` | `string` | *(required)* | The source code to review (capped at 6000 chars) |
| `language` | `string` | `"python"` | Programming language of the snippet |
| `focus` | `string` | `"general"` | Review focus: `"general"`, `"security"`, `"performance"`, or `"style"` |
| `max_new_tokens` | `int` | `768` | Maximum tokens for the review |

**Returns:** A structured review with four sections: *Overall Impression*, *Issues Found*, *Positives*, and *Top Recommendation*.

---


## Resources

### `llm://info`

Returns metadata about the currently loaded model.

---

## Configuring with Claude Desktop

Add the server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "local-llm": {
      "command": "python",
      "args": [
        "src/llm_server.py",
        "--model", "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "--llama-server", "/path/to/llama-server"
      ],
      "cwd": "/absolute/path/to/mcp-server"
    }
  }
}
```

## Notes

- The model is loaded once at startup via `llama-server` and held in memory for the lifetime of the server.
- GPU offloading is controlled by `--gpu-layers`; `-1` offloads all layers.
- `--context-size` sets the total token budget shared between the prompt and generated output. Increase it if you experience truncation on long responses.
- The HTTP transport binds to `0.0.0.0` by default, making it accessible from other machines on the network. Use `--host 127.0.0.1` to restrict to localhost. CORS is enabled for all origins — restrict `allow_origins` before exposing to untrusted networks.
- Uploaded files (`POST /upload`) are stored in `uploads/` at the project root and automatically deleted on server shutdown.


### Running local llama server to connect with opencode
`llama-server --model /path/to/model.gguf --port 8000 --host 127.0.0.1 --n-gpu-layers -1 --ctx-size 16384 --no-mmap`