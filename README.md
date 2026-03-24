# Walkie Backend

Walkie is an MVP push-to-talk multilingual voice communication backend. Participants join rooms, upload turn-based voice notes, and receive translated text plus synthesized audio in their preferred language.

## Architecture

- Django + DRF for REST APIs
- Django Channels for room-scoped WebSocket events
- Celery + Redis for asynchronous utterance processing
- PostgreSQL for application data
- Django file storage abstraction for source and translated audio
- Sarvam-backed provider layer for STT, translation, and TTS
- Mock provider fallback for tests and credential-free local development

## Project Structure

- `config/`: Django settings, ASGI, Celery, URL config
- `users/`: custom user model, demo auth, preferences API
- `rooms/`: room and participant models, room APIs, seed command
- `utterances/`: upload flow, feed APIs, Celery task orchestration
- `translations/`: translation outputs and feedback
- `realtime/`: WebSocket consumer, event broadcast service, query-string demo auth
- `providers/`: provider interfaces and mock implementations
- `common/`: shared enums, permissions, helpers

## Frontend Contract

### Authentication

Two MVP-friendly options are supported:

- Session-based auth via `POST /api/demo/login/`
- Header-based auth via `X-Demo-User-Id: <user_id>`

### AI Providers

The backend is configured to use Sarvam by default for:

- speech-to-text via `saaras:v3`
- translation via `sarvam-translate:v1`
- text-to-speech via `bulbul:v3`

Relevant env vars:

- `STT_PROVIDER`
- `TRANSLATION_PROVIDER`
- `TTS_PROVIDER`
- `SARVAM_API_KEY`
- `SARVAM_STT_MODEL`
- `SARVAM_TRANSLATION_MODEL`
- `SARVAM_TTS_MODEL`
- `SARVAM_TTS_SPEAKER`
- `SARVAM_TTS_AUDIO_FORMAT`

For public tunnels or hosted frontends, also configure:

- `DJANGO_ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

If you need fully offline dev or test behavior, set all three provider vars back to `mock`.

### REST APIs

- `POST /api/demo/login/`
- `GET /api/me/`
- `PATCH /api/me/preferences/`
- `POST /api/rooms/`
- `GET /api/rooms/{room_id}/`
- `POST /api/rooms/{room_id}/join/`
- `GET /api/rooms/{room_id}/participants/`
- `POST /api/rooms/{room_id}/utterances/`
- `GET /api/rooms/{room_id}/utterances/`
- `GET /api/utterances/{utterance_id}/`
- `POST /api/utterances/{utterance_id}/feedback/`

`GET /api/me/`, `POST /api/demo/login/`, and `PATCH /api/me/preferences/` all return the same full user resource shape.

### Room Feed Shape

Each utterance representation includes:

- `id`
- `room_id`
- `speaker_id`
- `speaker`
- `speaker_name`
- `created_at`
- `source_language`
- `source_language_display`
- `original_transcript`
- `status`
- `status_display`
- `duration_ms`
- `source_audio_url`
- `source_audio_available`
- `translations[]`
- `translation_count`
- `available_translation_languages[]`
- `preferred_translation`
- `preferred_translation_language`
- `has_preferred_translation`
- `error_message`
- `error`

Each translation object includes:

- `utterance_id`
- `target_language`
- `translated_text`
- `tts_audio_url`
- `tts_audio_format`
- `tts_audio_mime_type`
- `has_audio`

Utterance uploads from the frontend can be sent as browser-native recordings such as `audio/webm` or `audio/mp4`.
The backend will accept either and normalize them for speech-to-text when needed.
TTS responses are returned as MP3 when ElevenLabs is the active TTS provider.

Participant objects include frontend-friendly aliases in addition to the nested `user` object:

- `room_id`
- `user_id`
- `display_name`
- `preferred_output_language`
- `is_current_user`

### WebSocket

- URL: `/ws/rooms/{room_id}/`
- Demo auth fallback: `/ws/rooms/{room_id}/?user_id=<user_id>`
- Group name format: `room_{room_id}`

Every websocket event includes:

```json
{
  "type": "utterance.completed",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:00:00Z",
  "payload": {}
}
```

`room.participant_joined`

```json
{
  "type": "room.participant_joined",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:00:00Z",
  "payload": {
    "participant": {
      "id": 7,
      "room_id": 1,
      "user_id": 2,
      "display_name": "Sofia",
      "preferred_output_language": "es",
      "is_current_user": false,
      "user": {
        "id": 2,
        "email": "sofia@example.com",
        "display_name": "Sofia",
        "preferred_output_language": "es",
        "input_language_mode": "auto",
        "manual_input_language": null,
        "effective_input_language": "auto",
        "is_demo_user": false,
        "created_at": "2026-03-23T09:59:00Z",
        "updated_at": "2026-03-23T09:59:00Z"
      },
      "joined_at": "2026-03-23T10:00:00Z"
    }
  }
}
```

`room.participant_left`

```json
{
  "type": "room.participant_left",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:05:00Z",
  "payload": {
    "participant": {
      "id": 7,
      "room_id": 1,
      "user_id": 2,
      "display_name": "Sofia",
      "preferred_output_language": "es",
      "is_current_user": false
    }
  }
}
```

`utterance.created`

```json
{
  "type": "utterance.created",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:10:00Z",
  "payload": {
    "utterance": {
      "id": 12,
      "room_id": 1,
      "speaker_id": 1,
      "speaker": {
        "id": 1,
        "display_name": "Aman",
        "preferred_output_language": "en"
      },
      "speaker_name": "Aman",
      "created_at": "2026-03-23T10:10:00Z",
      "source_language": null,
      "source_language_display": "Pending detection",
      "original_transcript": "",
      "status": "uploaded",
      "status_display": "Uploaded",
      "duration_ms": 1200,
      "source_audio_url": "/media/utterances/source/1/1/hello.wav",
      "source_audio_available": true,
      "translations": [],
      "translation_count": 0,
      "available_translation_languages": [],
      "preferred_translation": null,
      "preferred_translation_language": null,
      "has_preferred_translation": false,
      "error_message": null,
      "error": null
    },
    "error": null
  }
}
```

`utterance.processing`

```json
{
  "type": "utterance.processing",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:10:02Z",
  "payload": {
    "utterance": {
      "id": 12,
      "status": "processing",
      "status_display": "Processing"
    },
    "error": null
  }
}
```

`utterance.transcribed`

```json
{
  "type": "utterance.transcribed",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:10:03Z",
  "payload": {
    "utterance": {
      "id": 12,
      "source_language": "en",
      "source_language_display": "en",
      "original_transcript": "Mock transcript for hello.wav",
      "status": "transcribed",
      "status_display": "Transcribed"
    },
    "error": null
  }
}
```

`utterance.translation_ready`

```json
{
  "type": "utterance.translation_ready",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:10:04Z",
  "payload": {
    "utterance": {
      "id": 12,
      "status": "transcribed",
      "status_display": "Transcribed"
    },
    "translation": {
      "utterance_id": 12,
      "target_language": "es",
      "translated_text": "[es] Mock transcript for hello.wav",
      "tts_audio_url": "/media/utterances/tts/1/es/utterance_12_es.mp3",
      "tts_audio_format": "mp3",
      "tts_audio_mime_type": "audio/mpeg",
      "has_audio": true
    }
  }
}
```

`utterance.completed`

```json
{
  "type": "utterance.completed",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:10:05Z",
  "payload": {
    "utterance": {
      "id": 12,
      "room_id": 1,
      "speaker_id": 1,
      "speaker": {
        "id": 1,
        "display_name": "Aman",
        "preferred_output_language": "en"
      },
      "speaker_name": "Aman",
      "created_at": "2026-03-23T10:10:00Z",
      "source_language": "en",
      "source_language_display": "en",
      "original_transcript": "Mock transcript for hello.wav",
      "status": "completed",
      "status_display": "Completed",
      "duration_ms": 1200,
      "source_audio_url": "/media/utterances/source/1/1/hello.wav",
      "source_audio_available": true,
      "translations": [
        {
          "utterance_id": 12,
          "target_language": "es",
          "translated_text": "[es] Mock transcript for hello.wav",
          "tts_audio_url": "/media/utterances/tts/1/es/utterance_12_es.mp3",
          "tts_audio_format": "mp3",
          "tts_audio_mime_type": "audio/mpeg",
          "has_audio": true
        }
      ],
      "translation_count": 1,
      "available_translation_languages": [
        "es"
      ],
      "preferred_translation": null,
      "preferred_translation_language": null,
      "has_preferred_translation": false,
      "error_message": null,
      "error": null
    },
    "error": null
  }
}
```

`utterance.failed`

```json
{
  "type": "utterance.failed",
  "room_id": 1,
  "occurred_at": "2026-03-23T10:10:06Z",
  "payload": {
    "utterance": {
      "id": 12,
      "status": "failed",
      "status_display": "Failed",
      "error_message": "We couldn't transcribe this audio. Detail: provider exploded",
      "error": {
        "code": "utterance_processing_failed",
        "message": "We couldn't transcribe this audio. Detail: provider exploded"
      }
    },
    "error": {
      "code": "utterance_processing_failed",
      "message": "We couldn't transcribe this audio.",
      "step": "transcription"
    }
  }
}
```

Supported event types:

- `room.participant_joined`
- `room.participant_left`
- `utterance.created`
- `utterance.processing`
- `utterance.transcribed`
- `utterance.translation_ready`
- `utterance.completed`
- `utterance.failed`

## Processing Pipeline

1. Client uploads audio with `duration_ms`.
2. Backend stores an `Utterance` with status `uploaded`.
3. Celery enqueues processing.
4. Mock STT produces deterministic transcript and source language.
5. Distinct participant output languages are computed once.
6. Translation and TTS run once per distinct target language.
7. `UtteranceTranslation` rows and audio files are stored.
8. Room WebSocket events are emitted during progress and completion.

## Local Setup

1. Copy `.env.example` to `.env`.
   If you are using ngrok or another HTTPS tunnel, add that origin to `CSRF_TRUSTED_ORIGINS` and its host to `DJANGO_ALLOWED_HOSTS`.
2. Start dependencies:

```bash
docker compose up -d
```

3. Create a virtual environment and install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Seed demo data:

```bash
python manage.py seed_demo
```

6. Start Django:

```bash
python manage.py runserver
```

7. Start Celery worker in another shell:

```bash
celery -A config worker -l info
```

If you want to bypass Sarvam and run everything with deterministic local mocks instead, set:

```bash
STT_PROVIDER=mock
TRANSLATION_PROVIDER=mock
TTS_PROVIDER=mock
```

## Demo Data

`seed_demo` creates:

- demo users with different language preferences
- one shared demo room
- room memberships for those users

## Tests

Run:

```bash
pytest
```

Tests cover:

- model uniqueness constraints
- language fanout deduplication logic
- upload-to-processing integration with mock providers
- room WebSocket event delivery

## Assumptions

- MVP auth is demo-friendly and not intended for production hardening.
- WebSocket auth supports query-string user IDs to make frontend development easier.
- Mock TTS emits a tiny WAV payload so frontend audio playback plumbing can be exercised locally.
- Public room join does not require a room code; private room join does.
- `room.participant_left` is documented for frontend planning, but there is still no leave-room API in this MVP.
- Sarvam language support is narrower than generic “multilingual”; the current integration is best for English plus Sarvam-supported Indian languages.
