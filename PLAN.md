## Summary

  Build a FastAPI application implemented with Python 3.12 and managed with uv. Follow the structure and SQLAlchemy/Alembic conventions of https://github.com/chasangchual/rag-mastermind. Provide REST APIs and a server-rendered frontend UI.

  The document will specify a standalone Python 3.12/uv project that:

  - Collects the requested 11 podcast channels through RSS.
  - Looks back --years N, defaulting to two years.
  - Prefers public publisher transcripts.
  - Uses local transcription when a complete publisher transcript is unavailable.
  - Stores channels, episodes, participants, transcripts, and chunks in PostgreSQL.
  - Stores embeddings and searchable metadata in Qdrant.
  - Runs idempotently through a daily cron-invoked CLI.

  ## Selected Local Models

  - Default transcription: mlx-whisper with mlx-community/whisper-large-v3-turbo.
      - Selected for the available M1 Pro/32 GB Mac.
      - MLX provides an Apple-Silicon-native Python interface. MLX Whisper

  - Default embeddings: an LM Studio embedding model served through its OpenAI-compatible API.
      - Default placeholder: text-embedding-qwen3-embedding-0.6b with 1,024-dimensional output; both model identifier and dimension are configurable.

  - Diarization is disabled by default.
      - Participant names come from RSS, publisher metadata, and named publisher transcripts.
      - Optional future provider: pyannote/speaker-diarization-community-1; it requires accepting model terms and an initial Hugging Face token. Pyannote

  - Document whisper.cpp as the supported alternative transcription backend for non-MLX environments. It supports Metal and Core ML on Apple Silicon. whisper.cpp

  ## Planned Architecture

  - CLI: uv run podcast-mastermind sync --years 2 [--channel SLUG ...]
  - External scheduling: cron at 03:00 America/Toronto.
  - Host processes:
      - Python ingestion pipeline
      - MLX Whisper
      - LM Studio (OpenAI-compatible local embeddings API)
      - ffmpeg

  - Docker services, started from the sibling mastermind-infra repository:
      - PostgreSQL 18 with pgvector
      - Qdrant

  - Local audio archive:
      - ${PODCAST_DATA_PATH}/audio/<channel>/<year>/<episode-id>.<ext>
      - Original audio is retained only when downloaded for local transcription.
      - Temporary normalized/segmented files are deleted after successful processing.

  Transcript resolution order:

  1. Podcasting 2.0 <podcast:transcript>.
  2. Public publisher adapters for NPR, Freakonomics, MacroVoices, Motley Fool, The Investor’s Podcast Network, and Colossus.
  3. Archived RSS audio transcribed with MLX Whisper.

  The plan will explicitly prohibit bypassing logins, paywalls, robots restrictions, or publisher access controls.

  ## Planned Data Model

  - podcast_channels
      - Stable slug, title, RSS and website URLs, active state, ETag, last-modified value, and polling timestamps.

  - podcast_episodes
      - Channel foreign key, RSS GUID, title, description, publication timestamp, duration, source URLs, archived-audio metadata, and participant JSON.
      - Full transcript, timestamped segments, language, source, model, content hash, processing status, and failure details.
      - Unique (channel_id, external_guid); derive a deterministic identifier when GUID is absent.

  - podcast_transcript_chunks
      - Episode foreign key, ordinal, text, hash, character count, overlap information, optional time bounds, and speaker labels.
      - Paragraph-first chunks of approximately 4,000 characters with 400-character overlap.
      - Unique (episode_id, chunk_index).

  - podcast_chunk_embeddings
      - Chunk foreign key, embedding provider/model key, dimension, Qdrant collection, point ID, and completion timestamp.
      - Unique (chunk_id, embedding_key).

  Qdrant will use one collection per embedding configuration, cosine distance, deterministic chunk UUIDs, and payload containing channel, episode, title, date, participants, transcript source, chunk index, and text. Qdrant collections require a consistent vector dimension, while point
  upserts support idempotent replacement. Qdrant collections, Qdrant points

  ## Planned Validation

  The document will require:

  - Fixture-based tests for all RSS and publisher adapters.
  - Lookback and leap-year boundary tests.
  - Duplicate-run idempotency tests.
  - Publisher-transcript preference and partial-transcript rejection tests.
  - Local transcription parsing and failure-retry tests.
  - PostgreSQL migration, constraint, JSON, and cascade tests.
  - Qdrant collection dimension, payload, model-switching, and duplicate-upsert tests.
  - An end-to-end fixture proving that publisher and locally transcribed episodes both produce PostgreSQL chunks and Qdrant points.

  ## Assumptions

  - “Script” means the episode transcript.
  - Stored transcripts are private and will not be publicly served.
  - The daily run scans the configured lookback window but processes only new, changed, failed, or incompletely embedded records.
  - Local Whisper does not identify real speaker names. Unknown voices remain generic speaker labels unless publisher metadata supplies identities.
  - The first implementation targets this Apple Silicon machine; whisper.cpp provides the portability path.
  - The audio archive has no automatic retention limit and may consume substantial disk space.
