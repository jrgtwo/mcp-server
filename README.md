# MCP Local LLM Server

A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes a locally-hosted HuggingFace language model as MCP tools, plus a suite of utility tools for weather, news, web fetching, and more.

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
    ├── date_time.py    # Tool: get_datetime
    ├── fetch_url.py    # Tool: fetch_url
    ├── news.py         # Tool: news_headlines
    ├── agent.py        # Tool: run_agent (autonomous ReAct agent)
    ├── explain_code.py # Tool: explain_code (coding tutor)
    ├── review_code.py  # Tool: review_code  (coding tutor)
    ├── run_python.py   # Tool: run_python   (coding tutor)
    └── coding_tutor.py # Tool: coding_tutor (orchestrating tutor agent)
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
| `max_new_tokens` | `int` | `1024` | Token ceiling per LLM call. Tool-call steps stop well before this; it mainly affects the length of the final answer |
| `max_history_pairs` | `int` | `4` | Number of recent assistant+tool rounds to keep in full. Older rounds are summarised and replaced to keep the prompt size manageable |
| `summary_strategy` | `string` | `"deterministic"` | How to summarise trimmed history. `"deterministic"` — fast, rule-based bullet points. `"llm"` — model-generated prose summary (adds an extra generation call) |

**Returns:** The agent's final answer as plain text.

> **Note:** If you see `Max steps (N) reached without a FINAL answer`, the agent used all its iterations without concluding. Either the task needs more steps (increase `max_steps`) or the model looped on tool calls — check the step logs to diagnose.

**Tools available to the agent**

| Tool | Description |
|---|---|
| `get_weather` | Fetch current weather for any city |
| `get_datetime` | Get the current date and time in any timezone |
| `fetch_url` | Fetch and extract text from any URL |
| `news_headlines` | Fetch the latest news headlines, using the user's location or subject of interest as the topic |

**Examples**

Single tool call:
```json
{"goal": "What should I wear in Paris today?"}
```

Multi-step (multiple tool calls):
```json
{"goal": "Compare the weather in London and Tokyo, then tell me which city is warmer."}
```

```json
{"goal": "What are the top US political news stories right now? Summarise the top 3."}
```

```json
{"goal": "What time is it in Sydney right now, and what is the weather like there?"}
```

---

## Coding Tutor Tools

Four tools that turn the server into an interactive programming tutor. The high-level entry point is `coding_tutor`; the three supporting tools (`explain_code`, `review_code`, `run_python`) can also be called directly.

### `coding_tutor`

An autonomous [ReAct](https://arxiv.org/abs/2210.03629) agent specialised for teaching. It reasons step by step, calling `explain_code`, `review_code`, `run_python`, and `fetch_url` as needed, then produces a pedagogical answer that explains the *why* before the *what*.

**How it works**

```
Your question
   ↓
Tutor LLM decides: call a tool or answer?
   ↓ (if tool)
explain_code / review_code / run_python / fetch_url
   → result fed back to LLM
   ↓
LLM decides again … (up to max_steps)
   ↓
FINAL teaching response
```

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

```json
{"question": "I'm getting a RecursionError in this code. What does it mean and how do I fix it?\n\ndef count_down(n):\n    return count_down(n - 1)"}
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

**Level guidance**

| Level | Audience |
|---|---|
| `beginner` | New to programming — plain language, analogies, first-principles explanations |
| `intermediate` | Knows the basics — focuses on how/why, language patterns, idioms |
| `advanced` | Experienced developer — design decisions, complexity, edge cases, subtle behaviour |

**Returns:** A plain-text explanation of the code.

**Examples**

```json
{
  "code": "result = [x**2 for x in range(10) if x % 2 == 0]",
  "level": "beginner"
}
```

```json
{
  "code": "with open('data.csv') as f:\n    reader = csv.DictReader(f)\n    rows = list(reader)",
  "language": "python",
  "level": "intermediate"
}
```

---

### `review_code`

Review a code snippet for issues using the local LLM. Outputs a structured report: overall impression, numbered issues with severity, positives, and a top recommendation.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `code` | `string` | *(required)* | The source code to review (capped at 6000 chars) |
| `language` | `string` | `"python"` | Programming language of the snippet |
| `focus` | `string` | `"general"` | Review focus: `"general"`, `"security"`, `"performance"`, or `"style"` |
| `max_new_tokens` | `int` | `768` | Maximum tokens for the review |

**Focus options**

| Focus | What it checks |
|---|---|
| `general` | Bugs, logic errors, bad practices, readability |
| `security` | Injection risks, insecure data handling, auth flaws, secrets in code |
| `performance` | Algorithmic complexity, unnecessary allocations, blocking calls, caching |
| `style` | Naming, function length, duplication, idiomatic patterns, comments |

**Returns:** A structured review with four sections: *Overall Impression*, *Issues Found* (numbered, each with severity, location, description, and fix), *Positives*, and *Top Recommendation*.

**Example**

```json
{
  "code": "def get_user(id):\n    query = f\"SELECT * FROM users WHERE id = {id}\"\n    return db.execute(query)",
  "focus": "security"
}
```

---

### `run_python`

Execute a short Python snippet in a sandboxed subprocess and return its output. Designed for live demos during tutoring sessions — dangerous operations are blocked before execution.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `code` | `string` | *(required)* | The Python code to execute |
| `timeout_seconds` | `int` | `10` | Maximum execution time in seconds (clamped to 1–30) |

**Returns:** A string with three sections:

```
EXIT CODE: 0
STDOUT:
4

STDERR:

```

**Security**

The following patterns are blocked and will never execute:

| Blocked pattern | Reason |
|---|---|
| `import os`, `import sys`, `import subprocess`, `import socket`, `import shutil` | Filesystem / process / network access |
| `__import__`, `importlib` | Dynamic import bypass |
| `open(` | File I/O |
| `exec(`, `eval(`, `compile(` | Arbitrary code execution |

Blocked code returns a clear message identifying the pattern — nothing is executed.

**Examples**

```json
{"code": "print(2 + 2)"}
```
→ `EXIT CODE: 0\nSTDOUT:\n4\nSTDERR:\n`

```json
{"code": "for i in range(5):\n    print(i ** 2)"}
```

```json
{"code": "import os; os.listdir('.')"}
```
→ `Execution blocked: the pattern 'import os' is not permitted for safety reasons.`

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

**Returns:** Extracted page text, truncated to `max_chars` if needed.

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
