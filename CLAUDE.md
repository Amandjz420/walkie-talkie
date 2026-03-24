# Walkie Backend - Claude Code Instructions

## Project Overview

Walkie is an MVP push-to-talk multilingual voice communication backend. Users join rooms, upload voice notes, and receive translated text and synthesized audio in their preferred language.

## Tech Stack

- **Framework**: Django 5.2+ with Django REST Framework (DRF)
- **Real-time**: Django Channels 4.2+ for WebSocket room events
- **Async Processing**: Celery 5.5+ with Redis broker for utterance processing pipeline
- **Database**: PostgreSQL 3.2+
- **Cache/Broker**: Redis 5.2+
- **Testing**: pytest with pytest-django, pytest-asyncio, model-bakery
- **Python**: 3.12+ (uses pyproject.toml for dependencies)

## Architecture

### Django Apps Structure

- `config/` - Settings, ASGI/WSGI, Celery config, root URLs
- `users/` - Custom user model, demo auth, preferences API
- `rooms/` - Room and participant models, room APIs, seed command
- `utterances/` - Upload flow, feed APIs, Celery task orchestration
- `translations/` - Translation outputs and feedback models
- `realtime/` - WebSocket consumer, event broadcast service
- `providers/` - Provider interfaces + mock STT/translation/TTS implementations
- `common/` - Shared enums, permissions, helpers

### Processing Pipeline

1. Client uploads audio → `Utterance` created with status `uploaded`
2. Celery task processes: Mock STT → transcript + source language
3. Compute distinct participant output languages (deduped)
4. Run translation + TTS once per distinct target language
5. Store `UtteranceTranslation` rows and audio files
6. Emit WebSocket events during progress and completion

### Provider Architecture

The project uses a provider abstraction layer to support both mock (local dev) and real AI services:

- `STT_PROVIDER`, `TRANSLATION_PROVIDER`, `TTS_PROVIDER` environment variables
- Default to `mock` for local development without external API keys
- Mock providers produce deterministic outputs for testing

## Development Workflow

### Setup

```bash
# Copy environment file
cp .env.example .env

# Start dependencies
docker compose up -d

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .[dev]

# Run migrations
python manage.py migrate

# Seed demo data
python manage.py seed_demo

# Start Django server
python manage.py runserver

# Start Celery worker (separate terminal)
celery -A config worker -l info
```

### Testing

```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest path/to/test.py    # Run specific test file
```

Tests cover:
- Model uniqueness constraints
- Language fanout deduplication logic
- Upload-to-processing integration with mock providers
- WebSocket event delivery

### Common Commands

```bash
python manage.py migrate                 # Run migrations
python manage.py makemigrations          # Create new migrations
python manage.py seed_demo               # Seed demo users and rooms
python manage.py shell                   # Django shell
celery -A config worker -l info          # Start Celery worker
celery -A config purge                   # Purge Celery tasks
```

## Code Conventions

### Authentication

Two MVP-friendly auth methods (not production-hardened):
- Session-based: `POST /api/demo/login/`
- Header-based: `X-Demo-User-Id: <user_id>` header
- WebSocket query-string fallback: `?user_id=<user_id>`

### API Patterns

- REST endpoints use DRF viewsets and serializers
- Standard CRUD patterns with DRF conventions
- Permissions: `IsAuthenticated` or custom room-scoped permissions
- OpenAPI schema via drf-spectacular

### WebSocket Events

- Group name format: `room_{room_id}`
- Events broadcast via `realtime/services.py::broadcast_room_event`
- Event types: `utterance.created`, `utterance.processing`, `utterance.completed`, etc.
- Payload includes full utterance representation with translations

### Celery Tasks

- Task definitions in `utterances/tasks.py`
- Use `.delay()` for async execution
- Mock providers allow local testing without external dependencies

### File Storage

- Django file storage abstraction for source/translated audio
- `MEDIA_ROOT` and `MEDIA_URL` configured in settings
- Files stored locally in `media/` directory for MVP

## Important Patterns

### Language Deduplication

When processing utterances, the system computes distinct participant output languages once to avoid redundant translation/TTS work.

### Status Progression

Utterance status flows: `uploaded` → `processing` → `transcribed` → `completed` or `failed`

### WebSocket Events During Processing

The pipeline emits granular WebSocket events so frontends can show real-time progress:
- `utterance.created` - immediately after upload
- `utterance.processing` - when Celery task starts
- `utterance.transcribed` - after STT completes
- `utterance.translation_ready` - after each translation completes
- `utterance.completed` - when fully processed
- `utterance.failed` - on any error

## Environment Variables

Key environment variables (see `.env.example`):

```bash
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=true
POSTGRES_DB=walkie
POSTGRES_USER=walkie
POSTGRES_PASSWORD=walkie
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
STT_PROVIDER=mock
TRANSLATION_PROVIDER=mock
TTS_PROVIDER=mock
```

## File Editing Preferences

- Follow existing Django app structure conventions
- Keep models, views, serializers, tasks separate
- Use DRF serializers for API validation
- Add docstrings to complex business logic
- Update tests when modifying core logic

## Common Tasks

### Adding a New API Endpoint

1. Define model in appropriate app's `models.py`
2. Create serializer in `serializers.py`
3. Add viewset in `views.py`
4. Register route in `urls.py`
5. Add tests in `tests.py`

### Adding a New WebSocket Event Type

1. Define event type in `common/enums.py` if needed
2. Emit event via `realtime.services.broadcast_room_event()`
3. Update frontend contract in README.md

### Adding a New Provider

1. Define interface in `providers/interfaces.py`
2. Implement mock in `providers/mock_*.py`
3. Update provider factory in `providers/__init__.py`
4. Add environment variable to `.env.example`

## Testing Philosophy

- Use `model_bakery` for test data generation
- Mock external dependencies (providers are already mocked)
- Test critical paths: upload → process → WebSocket delivery
- Async tests use `pytest-asyncio` for WebSocket consumers
