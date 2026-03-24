import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from common.choices import UtteranceStatus
from rooms.services import RoomService
from users.models import User
from utterances.models import Utterance
from utterances.services import UtteranceProcessingService


class BrokenProvider:
    def transcribe(self, *, file_path: str, language_hint: str | None = None):
        raise RuntimeError("provider exploded")


class EmptyTranscriptProvider:
    def transcribe(self, *, file_path: str, language_hint: str | None = None):
        from providers.base import SpeechToTextResult

        return SpeechToTextResult(transcript="   ", source_language="en")


@pytest.mark.django_db
def test_processing_failure_persists_friendly_error(monkeypatch):
    speaker = User.objects.create(display_name="Speaker", email="speaker@example.com")
    room = RoomService.create_room(creator=speaker, name="Room", is_private=False)
    utterance = Utterance.objects.create(
        room=room,
        speaker=speaker,
        source_audio=SimpleUploadedFile("clip.wav", b"RIFF....WAVE", content_type="audio/wav"),
        duration_ms=700,
    )

    monkeypatch.setattr("utterances.services.get_stt_provider", lambda: BrokenProvider())

    processed = UtteranceProcessingService.process(utterance_id=utterance.id)

    utterance.refresh_from_db()
    assert processed.status == UtteranceStatus.FAILED
    assert utterance.status == UtteranceStatus.FAILED
    assert "We couldn't transcribe this audio." in utterance.error_message


@pytest.mark.django_db
def test_empty_transcript_fails_before_translation(monkeypatch):
    speaker = User.objects.create(display_name="Speaker", email="speaker@example.com")
    room = RoomService.create_room(creator=speaker, name="Room", is_private=False)
    utterance = Utterance.objects.create(
        room=room,
        speaker=speaker,
        source_audio=SimpleUploadedFile("clip.wav", b"RIFF....WAVE", content_type="audio/wav"),
        duration_ms=700,
    )

    monkeypatch.setattr("utterances.services.get_stt_provider", lambda: EmptyTranscriptProvider())

    processed = UtteranceProcessingService.process(utterance_id=utterance.id)

    utterance.refresh_from_db()
    assert processed.status == UtteranceStatus.FAILED
    assert utterance.status == UtteranceStatus.FAILED
    assert "No speech was detected in this audio." in utterance.error_message
