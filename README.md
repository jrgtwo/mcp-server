# MCP Local LLM Server

A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes a locally-hosted [llama.cpp](https://github.com/ggerganov/llama.cpp) language model as MCP tools, plus a suite of utility tools for weather, news, web fetching, file I/O, stock data, summarization, and more.

## Overview

This server lets any MCP-compatible client (e.g. Claude Desktop, Cursor) use a local GGUF model for text generation and chat, without sending data to an external API. The model is served by a `llama-server` subprocess; the MCP server communicates with it over a local HTTP port.

```
src/
├── llm_server.py        # Entry point, argument parsing, server startup
├── model.py             # llama-server lifecycle, token generation
├── upload.py            # POST /upload endpoint for PDF and Markdown file uploads
├── resources.py         # MCP resource: llm://info
└── tools/
    ├── generate.py      # Tool: generate
    ├── chat.py          # Tool: chat
    ├── weather.py       # Tool: get_weather
    ├── date_time.py     # Tool: get_datetime
    ├── fetch_url.py     # Tool: fetch_url
    ├── news.py          # Tool: news_headlines
    ├── read_pdf.py      # Tool: read_pdf
    ├── read_markdown.py # Tool: read_markdown
    ├── create_file.py   # Tool: create_file
    ├── list_directory.py# Tool: list_directory
    ├── stock_price.py   # Tool: get_stock_price
    ├── summarize.py     # Tool: summarize_text
    ├── agent.py         # Tool: run_agent (autonomous ReAct agent)
    ├── explain_code.py  # Tool: explain_code (coding tutor)
    ├── review_code.py   # Tool: review_code  (coding tutor)
    ├── coding_tutor.py  # Tool: coding_tutor (orchestrating tutor agent)
    ├── transcribe_audio.py # Tool: transcribe_audio
    ├── text_to_speech.py   # Tool: text_to_speech
    ├── word_definition.py  # Tool: define_word
    └── random_joke.py      # Tool: get_random_joke
```

---

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

The `transcribe_audio` tool requires `faster-whisper`, which is listed in `requirements.txt` but has an optional CUDA-accelerated variant. For GPU inference, install the matching PyTorch CUDA build first:

```bash
# CPU-only (default)
pip install faster-whisper

# GPU (CUDA 12)
pip install faster-whisper
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

---

## Configuration

Some tools require API keys. Create a `.env` file in the project root (already gitignored):

```
NEWSAPI_KEY=your_key_here
```

The server loads this file automatically on startup.

| Variable | Required by | Where to get it |
|---|---|---|
| `NEWSAPI_KEY` | `news_headlines` | [newsapi.org](https://newsapi.org) — free tier available |

All other tools work without any API key.

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

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `--model` | *(required)* | Path to a `.gguf` file, or a directory containing one |
| `--llama-server` | *(required)* | Path to the `llama-server` executable |
| `--transport` | `stdio` | `stdio` or `http` |
| `--host` | `0.0.0.0` | Host to bind for HTTP transport (use `127.0.0.1` for localhost only) |
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

Uploaded files are stored in `uploads/` at the project root and deleted when the server shuts down.

**Example:**
```bash
curl -X POST http://localhost:5174/upload \
  -F "file=@/path/to/report.pdf"

curl -X POST http://localhost:5174/upload \
  -F "file=@/path/to/notes.md"
```

---

## Tools

### `generate`

Generate text from a raw prompt. The input prompt is **not** included in the returned text.

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
    {"role": "user",   "content": "What is the Eiffel Tower?"}
  ],
  "temperature": 0.7,
  "max_new_tokens": 256
}
```

---

### `get_weather`

Fetch current weather for any location using the free [Open-Meteo API](https://open-meteo.com/). No API key required.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `location` | `string` | *(required)* | City name or region (e.g. `"London"`, `"New York"`, `"Tokyo"`) |
| `units` | `string` | `"metric"` | `"metric"` (°C, km/h) or `"imperial"` (°F, mph) |

**Returns:** Current conditions, temperature, humidity, and wind speed.

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

**Returns:** Extracted page text, truncated to `max_chars` if needed. Returns a descriptive error string on connection failure rather than raising an exception.

**Example**

```json
{
  "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
  "max_chars": 2000
}
```

---

### `news_headlines`

Fetch the latest news headlines, optionally filtered by topic. Requires a free [NewsAPI](https://newsapi.org) key.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `topic` | `string` | `""` | Keyword(s) to filter by (e.g. `"AI"`, `"climate change"`). Leave blank for general top headlines |
| `country` | `string` | `"us"` | 2-letter country code used when `topic` is blank (e.g. `us`, `gb`, `au`, `de`) |
| `max_results` | `int` | `5` | Number of headlines to return (1–10) |

**Returns:** Numbered list of headlines with source, publication date, and URL.

**Example**

```json
{"topic": "artificial intelligence", "max_results": 3}
```

**Example output**

```
1. [BBC News] OpenAI releases new model
   Published: 2025-03-01
   https://bbc.co.uk/...

2. [Reuters] ...
```

---

### `read_pdf`

Extract and return the text content of a PDF file, organised by page. Image-only (scanned) PDFs return a clear message rather than empty output.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` | *(required)* | Absolute or relative path to the PDF file |
| `max_chars` | `int` | `8000` | Maximum characters to return before truncating |

**Returns:** Extracted text organised by page, truncated to `max_chars` if needed.

**Example**

```json
{"file_path": "/home/user/documents/report.pdf", "max_chars": 10000}
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
{"file_path": "/home/user/documents/notes.md"}
```

---

### `create_file`

Create a new file with the given name and content. Rejects path traversal attempts and validates the filename before writing.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_name` | `string` | *(required)* | Basename of the file to create (no path separators allowed) |
| `content` | `string` | *(required)* | Text content to write to the file |
| `directory` | `string` | `null` | Subdirectory to create the file in (relative to the server's working directory). Created if it doesn't exist |
| `encoding` | `string` | `"utf-8"` | Character encoding for the file |
| `overwrite` | `bool` | `false` | If `true`, overwrite an existing file at the same path |

**Returns:** A JSON object with keys:
- `success` — `true` if the file was created
- `file_path` — absolute path to the created file (`null` on failure)
- `error` — error message if `success` is `false`
- `message` — human-readable status

**Examples**

```json
{"file_name": "notes.md", "content": "# My Notes\n"}
```

```json
{
  "file_name": "config.json",
  "content": "{\"debug\": true}",
  "directory": "src",
  "overwrite": true
}
```

---

### `list_directory`

List the files and directories at a given path, with optional glob filtering and recursive traversal.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | `string` | *(required)* | Absolute or relative path to the directory to list |
| `pattern` | `string` | `"*"` | Glob pattern to filter results (e.g. `"*.py"`, `"data_*"`, `"**/*.json"`) |
| `recursive` | `bool` | `false` | If `true`, traverse all subdirectories |
| `include_hidden` | `bool` | `false` | If `true`, include files and folders whose names start with `"."` |
| `max_results` | `int` | `200` | Maximum number of entries to return |

**Returns:** A formatted listing showing `[DIR]` and `[FILE]` entries with file sizes, plus a summary count. Truncation is noted if `max_results` is reached.

**Examples**

```json
{"path": "/home/user/projects"}
```

```json
{
  "path": "/home/user/projects/mcp-server",
  "pattern": "*.py",
  "recursive": true
}
```

**Example output**

```
Directory: /home/user/projects/mcp-server/src

  [DIR]  tools/
  [FILE] llm_server.py  (4 KB)
  [FILE] model.py       (7 KB)
  [FILE] resources.py   (1 KB)
  [FILE] upload.py      (2 KB)

4 item(s) shown
```

---

### `get_stock_price`

Get the current stock price and key market data for a ticker symbol via the [Yahoo Finance API](https://finance.yahoo.com/). No API key required.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `ticker` | `string` | *(required)* | Stock ticker symbol (e.g. `"AAPL"`, `"MSFT"`, `"TSLA"`, `"BTC-USD"`) |

**Returns:** Current price, daily change, day range, 52-week range, volume, and market cap.

**Example**

```json
{"ticker": "NVDA"}
```

**Example output**

```
NVIDIA Corp (NVDA)
  Price:       875.40 USD
  Change:      +12.30 (+1.43%)
  Prev close:  863.10 USD
  Day range:   860.00 – 879.50 USD
  52-wk range: 410.00 – 974.00 USD
  Volume:      42,381,200
  Market cap:  2.16T USD
```

> **Tip:** Crypto pairs are also supported (e.g. `"BTC-USD"`, `"ETH-USD"`).

---

### `summarize_text`

Summarize a block of text using the local LLM. Long texts are automatically split into chunks, each summarized independently, then merged into a single coherent summary.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `text` | `string` | *(required)* | The text to summarize. Can be arbitrarily long |
| `focus` | `string` | `""` | Optional instruction to guide the summary (e.g. `"key risks"`, `"action items"`, `"technical details"`). Leave blank for a general summary |
| `max_length` | `int` | `200` | Approximate maximum length of the summary in tokens. Controls verbosity |

**Returns:** A concise summary of the input text.

**Examples**

```json
{"text": "... (long article) ..."}
```

```json
{
  "text": "... (meeting transcript) ...",
  "focus": "action items",
  "max_length": 150
}
```

```json
{
  "text": "... (technical document) ...",
  "focus": "key risks",
  "max_length": 300
}
```

---

### `transcribe_audio`

Transcribe an audio file to text using a local [Whisper](https://github.com/openai/whisper) model via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Runs entirely on-device — no API key or internet connection required. Models are downloaded automatically on first use and cached locally.

**Supported formats:** mp3, mp4, wav, flac, ogg, m4a, webm, and most ffmpeg-readable formats.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `audio_path` | `string` | *(required)* | Absolute or relative path to the audio file |
| `model_size` | `string` | `"base"` | Whisper model to use: `"tiny"` (~150 MB), `"base"` (~290 MB), `"small"` (~970 MB), `"medium"` (~3.1 GB), `"large-v3"` (~6.2 GB) |
| `language` | `string` | `null` | ISO-639-1 language code to force (e.g. `"en"`, `"fr"`). Leave `null` to auto-detect |
| `device` | `string` | `"auto"` | Inference device. `"auto"` selects CUDA if available, else CPU. Explicit: `"cuda"`, `"cpu"` |
| `compute_type` | `string` | `"auto"` | Precision. `"auto"` uses `float16` on GPU and `int8` on CPU. Explicit: `"float16"`, `"int8"`, `"float32"` |

**Returns:** A JSON object with keys:
- `success` — `true` if transcription succeeded
- `text` — the transcribed text (`null` on failure)
- `language` — detected or forced language code
- `duration_seconds` — audio duration in seconds
- `error` — error message if `success` is `false`

**Examples**

```json
{"audio_path": "/home/user/recordings/meeting.mp3"}
```

```json
{
  "audio_path": "/home/user/recordings/lecture.wav",
  "model_size": "small",
  "language": "en"
}
```

> **Tip:** Use `"tiny"` or `"base"` for fast transcription of short clips. Use `"small"` or higher for better accuracy on noisy audio or non-English speech.

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
| `max_new_tokens` | `int` | `4096` | Token ceiling per LLM call. Mainly affects the length of the final answer |
| `max_history_pairs` | `int` | `4` | Recent assistant+tool rounds to keep in full; older rounds are summarised |
| `summary_strategy` | `string` | `"deterministic"` | `"deterministic"` — fast rule-based bullet points. `"llm"` — model-generated prose (adds an extra generation call) |
| `upload_id` | `string` | `""` | ID returned by `POST /upload`. The file's contents are injected into the agent's context before the loop starts |

**Returns:** The agent's final answer as plain text.

> If you see `Agent stopped after N steps without a FINAL answer`, the agent exhausted its iterations. Either increase `max_steps` or simplify the goal.

**Tools available to the agent**

| Tool | Description |
|---|---|
| `get_weather` | Fetch current weather for any city |
| `get_datetime` | Get the current date and time in any timezone |
| `fetch_url` | Fetch and extract text from any URL |
| `news_headlines` | Fetch the latest news headlines by topic |
| `read_pdf` | Extract text from a PDF file at a given path |
| `read_markdown` | Read the contents of a Markdown file at a given path |
| `get_stock_price` | Get the current stock price and market data for a ticker symbol |
| `summarize_text` | Summarize a block of text using the local LLM |
| `create_file` | Create a new file with the given name and content |
| `list_directory` | List files and directories at a given path |
| `transcribe_audio` | Transcribe an audio file to text using a local Whisper model |

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

```json
{
  "goal": "What are the top AI news stories today?",
  "max_steps": 5
}
```

---

### `text_to_speech`

Convert text to an MP3 audio file using [Google Text-to-Speech (gTTS)](https://gtts.readthedocs.io/). Requires an internet connection. No API key required.

> **Dependency:** Install `gTTS` before using this tool:
> ```bash
> pip install gtts
> ```

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `text` | `string` | *(required)* | The text to convert to speech |
| `output_path` | `string` | *(required)* | File path where the MP3 will be saved (e.g. `"output/speech.mp3"`). Parent directories are created automatically |
| `lang` | `string` | `"en"` | BCP-47 language code (e.g. `"en"`, `"fr"`, `"es"`, `"de"`, `"ja"`) |
| `slow` | `bool` | `false` | If `true`, speech is generated at a slower rate |

**Returns:** A JSON object with keys:
- `success` — `true` if the file was saved successfully
- `output_path` — absolute path to the saved MP3 (`null` on failure)
- `error` — error message if `success` is `false`

**Examples**

```json
{
  "text": "Hello, world!",
  "output_path": "output/hello.mp3"
}
```

```json
{
  "text": "Bonjour le monde",
  "output_path": "output/bonjour.mp3",
  "lang": "fr",
  "slow": true
}
```

---

### `define_word`

Look up the definition, phonetics, synonyms, and antonyms of an English word using the free [Dictionary API](https://dictionaryapi.dev/). No API key required.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `word` | `string` | *(required)* | The English word to look up (e.g. `"ephemeral"`, `"serendipity"`) |

**Returns:** A JSON object with keys:
- `success` — `true` if the word was found
- `word` — the normalised word that was looked up
- `results` — list of meanings, each containing:
  - `phonetic` — IPA phonetic spelling (may be `null`)
  - `part_of_speech` — e.g. `"noun"`, `"verb"`, `"adjective"`
  - `definitions` — up to 3 definitions, each with `definition`, `example` (may be `null`), `synonyms` (up to 5), `antonyms` (up to 5)
  - `synonyms` — up to 5 synonyms for this part of speech
  - `antonyms` — up to 5 antonyms for this part of speech
- `error` — error message if `success` is `false`

**Example**

```json
{"word": "ephemeral"}
```

**Example output (abbreviated)**

```json
{
  "success": true,
  "word": "ephemeral",
  "results": [
    {
      "phonetic": "/ɪˈfɛm(ə)r(ə)l/",
      "part_of_speech": "adjective",
      "definitions": [
        {
          "definition": "Lasting for a very short time.",
          "example": "fashions are ephemeral",
          "synonyms": ["transitory", "transient", "fleeting"],
          "antonyms": ["permanent", "eternal"]
        }
      ],
      "synonyms": ["transitory", "transient"],
      "antonyms": ["permanent"]
    }
  ],
  "error": null
}
```

---

### `get_random_joke`

Fetch a random joke from the free [JokeAPI](https://v2.jokeapi.dev/). No API key required.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `category` | `string` | `"Any"` | Joke category: `"Any"`, `"Programming"`, `"Misc"`, `"Dark"`, `"Pun"`, `"Spooky"`, `"Christmas"` |
| `joke_type` | `string` | `"any"` | Format filter: `"any"`, `"single"` (one-liner), `"twopart"` (setup + punchline) |
| `safe_mode` | `bool` | `true` | If `true`, excludes explicit, racist, sexist, and religious jokes |

**Returns:** A JSON object with keys:
- `success` — `true` if a joke was returned
- `category` — the category the joke belongs to
- `type` — `"single"` or `"twopart"`
- `joke` — the joke text; two-part jokes are formatted as `"setup\n\n— delivery"`
- `error` — error message if `success` is `false`

> **Note:** The `"Dark"` category is unavailable when `safe_mode` is `true`.

**Examples**

```json
{"category": "Programming"}
```

```json
{
  "category": "Pun",
  "joke_type": "twopart",
  "safe_mode": true
}
```

---

## Coding Tutor Tools

Three tools that turn the server into an interactive programming tutor. The high-level entry point is `coding_tutor`; the two supporting tools (`explain_code`, `review_code`) can also be called directly.

### `coding_tutor`

An autonomous [ReAct](https://arxiv.org/abs/2210.03629) agent specialised for teaching. It reasons step by step, calling `explain_code`, `review_code`, and `fetch_url` as needed, then produces a pedagogical response.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `question` | `string` | *(required)* | Your coding question, code snippet, or error message |
| `max_steps` | `int` | `8` | Maximum tool-call iterations before stopping |
| `max_new_tokens` | `int` | `1024` | Token ceiling per LLM call |
| `max_history_pairs` | `int` | `4` | Recent assistant+tool rounds to keep before older ones are summarised |
| `summary_strategy` | `string` | `"deterministic"` | `"deterministic"` (fast) or `"llm"` (prose, slower) |

**Returns:** A teaching response as plain text.

**Tools available to the tutor**

| Tool | Description |
|---|---|
| `explain_code` | Explain a code snippet at the learner's skill level |
| `review_code` | Review code for bugs, style, security, or performance issues |
| `fetch_url` | Fetch documentation or a GitHub link referenced by the learner |

**Examples**

```json
{"question": "Why does my list comprehension give the wrong result?\n\nresult = [x * 2 for x in [1, 2, 3] if x > 1]"}
```

```json
{"question": "Explain the difference between a shallow copy and a deep copy in Python, with examples."}
```

> **Tip:** The tutor infers skill level from your question — use plain language for beginner explanations, technical terminology for advanced ones.

---

### `explain_code`

Explain a code snippet using the local LLM, tailored to the learner's skill level.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `code` | `string` | *(required)* | The source code to explain (capped at 6 000 chars) |
| `language` | `string` | `"python"` | Programming language of the snippet |
| `level` | `string` | `"beginner"` | Explanation depth: `"beginner"`, `"intermediate"`, or `"advanced"` |
| `max_new_tokens` | `int` | `1024` | Maximum tokens for the explanation |

**Returns:** A plain-text explanation of the code.

**Example**

```json
{
  "code": "result = {k: v for k, v in zip(keys, values)}",
  "language": "python",
  "level": "beginner"
}
```

---

### `review_code`

Review a code snippet for issues. Outputs a structured report: overall impression, numbered issues with severity, positives, and a top recommendation.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `code` | `string` | *(required)* | The source code to review (capped at 6 000 chars) |
| `language` | `string` | `"python"` | Programming language of the snippet |
| `focus` | `string` | `"general"` | Review focus: `"general"`, `"security"`, `"performance"`, or `"style"` |
| `max_new_tokens` | `int` | `768` | Maximum tokens for the review |

**Returns:** A structured review with four sections: *Overall Impression*, *Issues Found*, *Positives*, and *Top Recommendation*.

**Example**

```json
{
  "code": "def get_user(id):\n    return db.execute(f'SELECT * FROM users WHERE id={id}')",
  "language": "python",
  "focus": "security"
}
```

---

## Resources

### `llm://info`

Returns metadata about the currently loaded model (path, context size, GPU layers).

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

---

## Notes

- The model is loaded once at startup via `llama-server` and held in memory for the lifetime of the server.
- GPU offloading is controlled by `--gpu-layers`; `-1` offloads all layers.
- `--context-size` sets the total token budget shared between prompt and generated output. Increase it if you experience truncation on long responses.
- The HTTP transport binds to `0.0.0.0` by default, making it accessible from other machines on the network. Use `--host 127.0.0.1` to restrict to localhost. CORS is enabled for all origins — restrict `allow_origins` before exposing to untrusted networks.
- Uploaded files (`POST /upload`) are stored in `uploads/` at the project root and automatically deleted on server shutdown.

### Running a standalone llama-server (e.g. for opencode)

```bash
llama-server \
  --model /path/to/model.gguf \
  --port 8000 \
  --host 127.0.0.1 \
  --n-gpu-layers -1 \
  --ctx-size 16384 \
  --no-mmap
```
