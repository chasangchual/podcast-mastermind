# Podcast Mastermind

Podcast Mastermind is a private, self-hosted app that collects podcast episodes from RSS feeds, gets their transcripts, and lets you search them semantically.

- **Transcripts:** published Podcasting 2.0 or publisher transcripts are used first. When none is available, the audio is transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Ubuntu/macOS, CPU or CUDA) or MLX Whisper (Apple Silicon).
- **Storage:** PostgreSQL holds channels, episodes, transcripts, and chunks. Qdrant holds the vectors.
- **Embeddings:** any OpenAI-compatible server (LM Studio, Ollama, vLLM, OpenAI) or Google Gemini.
- **Interfaces:** a web UI and REST API (FastAPI) on port **8801**, plus a CLI for cron-driven syncing.

---

## Quick start

These steps assume PostgreSQL and Qdrant are already running (e.g. on `192.168.1.161`) and an embedding server is reachable.

```bash
# 1. Install uv and Python 3.12 (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh        # then open a new shell
uv python install 3.12

# 2. Install the app
cd podcast-mastermind
uv sync --extra transcription

# 3. Configure (see "Configuration" below)
cp .env.example .env.prod
nano .env.prod

# 4. Create / upgrade the database tables
APP_ENV_FILE=.env.prod uv run alembic upgrade head

# 5. Start the server
APP_ENV_FILE=.env.prod uv run podcast-mastermind serve
```

Then check that it works:

```bash
curl http://127.0.0.1:8801/api/v1/health    # every service should be "ok" (Langfuse may be "disabled")
```

| What | URL |
| --- | --- |
| Web UI | `http://<server-ip>:8801` |
| API docs (Swagger) | `http://<server-ip>:8801/docs` |
| Health check | `http://<server-ip>:8801/api/v1/health` |

Add a podcast and fetch its episodes:

```bash
APP_ENV_FILE=.env.prod uv run podcast-mastermind add-channel \
  my-show "My Show" "https://example.com/feed.xml" --website-url "https://example.com"

APP_ENV_FILE=.env.prod uv run podcast-mastermind sync
```

> **Tip:** to avoid typing `APP_ENV_FILE=...` each time, run `export APP_ENV_FILE=.env.prod` once per shell, or name your file `.env`, which is the default.

---

## Configuration

### How settings are loaded

1. The app reads **one env file** from the project root. This is `.env` by default.
2. To use a different file, set **`APP_ENV_FILE`**, e.g. `APP_ENV_FILE=.env.prod`. An absolute path also works.
3. **Real environment variables override the file**. For example, `APP_PORT=9000 uv run podcast-mastermind serve` works.
4. Unknown keys are ignored, so the file can also hold `mastermind-infra` settings (Neo4j, Redis, RustFS, and so on).

`.env.example` is a complete, commented template. Never commit `.env` or `.env.*`; both are git-ignored except `.env.example`.

### Minimal `.env.prod`

This is the least you need to set for the production setup:

```dotenv
# Web server
APP_HOST=0.0.0.0              # 0.0.0.0 = reachable from other machines; 127.0.0.1 = this machine only
APP_PORT=8801

# PostgreSQL
POSTGRES_HOST=192.168.1.161
POSTGRES_PORT=54321
POSTGRES_DB=mastermind
POSTGRES_USER=<user>
POSTGRES_PASSWORD=<password>

# Qdrant
QDRANT_HOST=192.168.1.161
QDRANT_REST_PORT=6333
QDRANT_API_KEY=<key>

# Embeddings (example: LM Studio / Ollama / any OpenAI-compatible server)
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
EMBEDDING_MODEL=text-embedding-qwen3-embedding-0.6b
EMBEDDING_DIMENSION=1024
```

Everything else has a sensible default.

### All settings

#### Web server

| Setting | Default | Description |
| --- | --- | --- |
| `APP_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` to accept LAN connections |
| `APP_PORT` | `8801` | HTTP port |
| `APP_ENV` | `local` | Free-form environment label |

#### PostgreSQL

| Setting | Default | Description |
| --- | --- | --- |
| `POSTGRES_HOST` | `127.0.0.1` | Database host |
| `POSTGRES_PORT` | `5432` | Database port (`54321` in `mastermind-infra`) |
| `POSTGRES_DB` | `podcast_mastermind` | Database name |
| `POSTGRES_USER` | `postgres` | User |
| `POSTGRES_PASSWORD` | `podcast-mastermind` | Password |
| `DATABASE_URL` | – | Full SQLAlchemy URL; overrides all of the above |

#### Qdrant

| Setting | Default | Description |
| --- | --- | --- |
| `QDRANT_HOST` | `127.0.0.1` | Qdrant host |
| `QDRANT_REST_PORT` | `6333` | REST port |
| `QDRANT_API_KEY` | – | API key, if Qdrant requires one |
| `QDRANT_URL` | – | Full URL (e.g. `https://qdrant.example.com`); overrides host and port |

#### Embeddings

| Setting | Default | Description |
| --- | --- | --- |
| `EMBEDDING_PROVIDER` | `openai_compatible` | `openai_compatible` or `gemini` |
| `EMBEDDING_BASE_URL` | `http://127.0.0.1:1234/v1` | API base URL (OpenAI-compatible only) |
| `EMBEDDING_API_KEY` | `lm-studio` | Bearer token (OpenAI-compatible only); leave empty if not needed |
| `EMBEDDING_MODEL` | `text-embedding-qwen3-embedding-0.6b` | Model name as the provider knows it |
| `EMBEDDING_DIMENSION` | `1024` | Vector size; **must match the model's output** |
| `EMBEDDING_SEND_DIMENSIONS` | `false` | Send `dimensions` in the request (OpenAI `text-embedding-3-*`) |
| `GEMINI_API_KEY` | – | Required when `EMBEDDING_PROVIDER=gemini` |
| `EMBEDDING_KEY_PROVIDER` | – | Advanced. Set to `lmstudio` to keep using embeddings created before the provider setting existed |

The old `LMSTUDIO_BASE_URL`, `LMSTUDIO_API_KEY`, `LMSTUDIO_EMBEDDING_MODEL`, and `LMSTUDIO_EMBEDDING_DIMENSION` names are still accepted.

#### Transcription

| Setting | Default | Description |
| --- | --- | --- |
| `TRANSCRIPTION_BACKEND` | `faster_whisper` | `faster_whisper` (Linux/macOS) or `mlx` (Apple Silicon; needs `uv sync --extra mlx`) |
| `WHISPER_MODEL` | `large-v3-turbo` | `tiny`, `base`, `small`, `medium`, `distil-large-v3`, `large-v3-turbo`, `large-v3`. For `mlx`, use a repo such as `mlx-community/whisper-large-v3-turbo` |
| `WHISPER_DEVICE` | `cpu` | `cpu`, `cuda`, or `auto` |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8` for CPU, `float16` for CUDA |
| `WHISPER_CPU_THREADS` | `0` | `0` = automatic |
| `WHISPER_BEAM_SIZE` | `1` | `1` is fastest on CPU; `5` is slightly more accurate |
| `TRANSCRIPT_MIN_WORDS` | `150` | A published transcript shorter than this is treated as incomplete, and the audio is transcribed instead |

#### Langfuse (optional)

| Setting | Default | Description |
| --- | --- | --- |
| `LANGFUSE_HOST` | – | Host (e.g. `192.168.1.161`) or full URL. Empty = disabled |
| `LANGFUSE_WEB_PORT` | `3000` | Web port, used when `LANGFUSE_HOST` is a bare host |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | – | Project API keys from the Langfuse UI |

Langfuse is configuration-only for now. The health check reports whether it is reachable, but no traces are sent yet.

#### Storage and misc

| Setting | Default | Description |
| --- | --- | --- |
| `PODCAST_DATA_PATH` | `./data` | Where downloaded audio is kept (`<path>/audio/<channel>/<year>/`). This can grow to many GB |
| `HTTP_USER_AGENT` | `podcast-mastermind/0.1 ...` | User-Agent for RSS and transcript requests |
| `DIARIZATION_ENABLED`, `DIARIZATION_MODEL`, `HUGGINGFACE_TOKEN` | off | Reserved for future speaker diarization |

### Common changes

#### Change the server port

Pick one of these:

```bash
# A. Permanently: edit the env file
APP_PORT=8802                                              # in .env / .env.prod

# B. One run: command-line flag (overrides the env file)
uv run podcast-mastermind serve --port 8802 --host 0.0.0.0

# C. One run: environment variable
APP_PORT=8802 uv run podcast-mastermind serve
```

To check whether a port is already taken, run `ss -ltnp | grep 8801` on Ubuntu or `lsof -i :8801` on macOS.

#### Switch the embedding provider

| Provider | Settings |
| --- | --- |
| LM Studio | `EMBEDDING_PROVIDER=openai_compatible`<br>`EMBEDDING_BASE_URL=http://<host>:1234/v1`<br>`EMBEDDING_MODEL=text-embedding-qwen3-embedding-0.6b`<br>`EMBEDDING_DIMENSION=1024` |
| Ollama | `EMBEDDING_PROVIDER=openai_compatible`<br>`EMBEDDING_BASE_URL=http://<host>:11434/v1`<br>`EMBEDDING_MODEL=qwen3-embedding:0.6b`<br>`EMBEDDING_DIMENSION=1024` |
| vLLM / HF TEI / Infinity | `EMBEDDING_PROVIDER=openai_compatible`<br>`EMBEDDING_BASE_URL=http://<host>/v1`<br>the served model name and its dimension |
| OpenAI | `EMBEDDING_PROVIDER=openai_compatible`<br>`EMBEDDING_BASE_URL=https://api.openai.com/v1`<br>`EMBEDDING_API_KEY=sk-...`<br>`EMBEDDING_MODEL=text-embedding-3-small`<br>`EMBEDDING_DIMENSION=1536` |
| Google Gemini | `EMBEDDING_PROVIDER=gemini`<br>`GEMINI_API_KEY=...`<br>`EMBEDDING_MODEL=gemini-embedding-001`<br>`EMBEDDING_DIMENSION=768` (or `1536` / `3072`) |

Each model and dimension gets its own Qdrant collection. After switching, embed the transcripts you already have into the new collection. Nothing is downloaded or transcribed again:

```bash
APP_ENV_FILE=.env.prod uv run podcast-mastermind reindex
```

If the dimension doesn't match the model, embedding fails with `Embedding dimension mismatch` before anything is written.

#### Speed up transcription on a CPU-only server

With `large-v3-turbo` on CPU, transcribing an episode takes roughly as long as the episode itself, or longer. A large backfill can therefore take days. For a faster first pass:

```dotenv
WHISPER_MODEL=distil-large-v3     # or small
```

Models download from Hugging Face into `~/.cache/huggingface` on first use.

---

## Commands

Prefix each command with `APP_ENV_FILE=.env.prod` (or `export` it) to use the production config.

| Command | What it does |
| --- | --- |
| `uv run podcast-mastermind serve [--host H] [--port P] [--reload]` | Start the web UI and API |
| `uv run podcast-mastermind add-channel SLUG "TITLE" RSS_URL [--website-url URL]` | Add a podcast feed |
| `uv run podcast-mastermind sync [--years N] [--channel SLUG ...]` | Fetch feeds and process new, changed, or failed episodes (default: last 2 years) |
| `uv run podcast-mastermind reindex [--channel SLUG ...]` | Embed stored transcripts into the current embedding model's collection |
| `uv run alembic upgrade head` | Create or upgrade database tables |
| `uv run alembic current` | Show the applied migration |

The shared PostgreSQL database can hold tables from other Mastermind apps. This app only manages `podcast_*` tables and records its migration state in `podcast_alembic_version`.

### REST API

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/health` | Status of PostgreSQL, Qdrant, the embedding provider, and Langfuse |
| `GET/POST /api/v1/channels` | List or add podcast feeds |
| `PATCH /api/v1/channels/{slug}` | Update a channel |
| `GET /api/v1/episodes` | List episodes (`?channel=`, `?limit=`, `?offset=`) |
| `GET /api/v1/episodes/{public_id}` | Episode metadata and transcript |
| `POST /api/v1/sync` | Run ingestion (prefer the CLI for long runs) |
| `POST /api/v1/search` | Semantic search over transcript chunks |

---

## Running on Ubuntu as a service

### Web server (systemd)

Create `/etc/systemd/system/podcast-mastermind.service`. Adjust `User`, `WorkingDirectory`, and the `uv` path (`which uv`):

```ini
[Unit]
Description=Podcast Mastermind
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/opt/podcast-mastermind
Environment=APP_ENV_FILE=.env.prod
ExecStart=/home/ubuntu/.local/bin/uv run podcast-mastermind serve
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now podcast-mastermind
sudo systemctl status podcast-mastermind
journalctl -u podcast-mastermind -f          # follow logs
```

### Daily sync (cron)

Run `crontab -e` and add the following to sync at 03:00 Toronto time:

```cron
CRON_TZ=America/Toronto
0 3 * * * cd /opt/podcast-mastermind && APP_ENV_FILE=.env.prod /home/ubuntu/.local/bin/uv run podcast-mastermind sync --years 2 >> data/sync.log 2>&1
```

---

## Local development (macOS)

Local PostgreSQL and Qdrant come from the sibling [`mastermind-infra`](https://github.com/chasangchual/mastermind-infra) repository:

```bash
docker compose -f ../mastermind-infra/docker-compose.yml up -d postgresql qdrant
uv sync --extra dev --extra transcription --extra mlx     # mlx is optional
uv run alembic upgrade head
uv run podcast-mastermind serve --reload                  # uses .env
```

On Apple Silicon, set `TRANSCRIPTION_BACKEND=mlx` and `WHISPER_MODEL=mlx-community/whisper-large-v3-turbo` in `.env` to use the GPU.

Run the checks:

```bash
uv run ruff check .
uv run pytest
uv run alembic check
```

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Health shows `postgres`/`qdrant` error `No route to host` or `Connection refused` | Check `*_HOST`/`*_PORT`, check that the service is running, and check firewall rules on the services host |
| `address already in use` on start | Another app has the port. Change it (see [Change the server port](#change-the-server-port)) |
| `Embedding dimension mismatch` | Set `EMBEDDING_DIMENSION` to the model's actual output size |
| `model_available: false` in health | The model named by `EMBEDDING_MODEL` isn't loaded in LM Studio/Ollama. Load it, or fix the name |
| `Local transcription requires: uv sync --extra transcription` | Install the transcription extra |
| Search returns nothing after switching models | Run `podcast-mastermind reindex` |
| Settings seem ignored | Make sure `APP_ENV_FILE` points to the file you edited. Exported shell variables override the file |

---

## Project structure

```text
podcast-mastermind/
├── app/
│   ├── main.py                  # FastAPI application and router registration
│   ├── cli.py                   # serve, add-channel, sync, and reindex commands
│   ├── config/
│   │   ├── app_config.py        # All settings (env file selected by APP_ENV_FILE)
│   │   └── db.py                # SQLAlchemy engine and request sessions
│   ├── model/                   # Channel, episode, chunk, and embedding tables
│   ├── routers/                 # REST API, schemas, and web UI routes
│   ├── service/
│   │   ├── rss.py               # Conditional RSS fetching and parsing
│   │   ├── transcripts.py       # Published transcript lookup
│   │   ├── transcription.py     # faster-whisper / MLX Whisper
│   │   ├── chunking.py          # Paragraph-first transcript splitting
│   │   ├── embeddings.py        # OpenAI-compatible and Gemini clients
│   │   ├── vector_store.py      # Qdrant collections, upserts, and search
│   │   └── sync.py              # Ingestion orchestration
│   ├── templates/, static/      # Web UI
├── migration/                   # Alembic migrations
├── tests/
├── .env.example                 # Settings template
├── pyproject.toml, uv.lock      # Dependencies
└── PLAN.md                      # Original design notes
```

## Dependencies

| Requirement | Purpose |
| --- | --- |
| Python 3.12 + `uv` | Runtime and dependency management |
| PostgreSQL, Qdrant | Storage (remote host, or local via `mastermind-infra`) |
| Embedding provider | OpenAI-compatible server or Gemini API key |
| Langfuse | Optional |

| `uv` extra | Installs | When to use |
| --- | --- | --- |
| `transcription` | `faster-whisper`, `av` | Always on servers. Local transcription (CPU/CUDA); ffmpeg is not needed |
| `mlx` | `mlx-whisper` | Optional, Apple Silicon only |
| `dev` | pytest, Ruff | Tests and linting |
| `diarization` | `pyannote.audio` | Reserved for future use |
