import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from rooms.services import RoomService
from rooms.models import RoomParticipant
from translations.models import UtteranceTranslation
from translations.services import TranslationFanoutService
from users.models import User
from utterances.models import Utterance


@pytest.mark.django_db
def test_distinct_target_languages_deduplicates_preferences():
    speaker = User.objects.create(display_name="Speaker", email="speaker@example.com")
    listener_one = User.objects.create(
        display_name="Listener One", email="one@example.com", preferred_output_language="es"
    )
    listener_two = User.objects.create(
        display_name="Listener Two", email="two@example.com", preferred_output_language="es"
    )
    listener_three = User.objects.create(
        display_name="Listener Three", email="three@example.com", preferred_output_language="fr"
    )

    participants = [
        RoomParticipant(user=speaker),
        RoomParticipant(user=listener_one),
        RoomParticipant(user=listener_two),
        RoomParticipant(user=listener_three),
    ]

    assert TranslationFanoutService.distinct_target_languages(
        participants=participants, speaker=speaker
    ) == ["en", "es", "fr"]


@pytest.mark.django_db
def test_same_language_translation_reuses_transcript_without_provider_call(monkeypatch):
    speaker = User.objects.create(
        display_name="Speaker",
        email="speaker@example.com",
        preferred_output_language="en",
    )
    room = RoomService.create_room(creator=speaker, name="Room", is_private=False)
    utterance = Utterance.objects.create(
        room=room,
        speaker=speaker,
        source_audio=SimpleUploadedFile("sample.wav", b"abc", content_type="audio/wav"),
        duration_ms=500,
        source_language="en",
        original_transcript="Hello there",
    )

    class ExplodingTranslationProvider:
        def translate(self, *, text: str, source_language: str, target_language: str) -> str:
            raise AssertionError("translate should not be called for same-language output")

    class FakeTTSProvider:
        def synthesize(self, *, text: str, language: str) -> bytes:
            assert text == "Hello there"
            assert language == "en"
            return b"fake-audio"

    monkeypatch.setattr("translations.services.get_translation_provider", lambda: ExplodingTranslationProvider())
    monkeypatch.setattr("translations.services.get_tts_provider", lambda: FakeTTSProvider())
    participants = [RoomParticipant(user=speaker)]

    translations = TranslationFanoutService.build_translations(
        utterance=utterance,
        transcript="Hello there",
        source_language="en",
        participants=participants,
    )

    assert len(translations) == 1
    assert translations[0].translated_text == "Hello there"
    assert UtteranceTranslation.objects.get(utterance=utterance, target_language="en").translated_text == "Hello there"


@pytest.mark.django_db
def test_translation_logging_includes_target_language_and_text(monkeypatch, caplog, settings):
    settings.TRANSLATION_FANOUT_MAX_WORKERS = 1
    speaker = User.objects.create(
        display_name="Speaker",
        email="speaker2@example.com",
        preferred_output_language="en",
    )
    listener = User.objects.create(
        display_name="Listener",
        email="listener@example.com",
        preferred_output_language="es",
    )
    room = RoomService.create_room(creator=speaker, name="Room", is_private=False)
    utterance = Utterance.objects.create(
        room=room,
        speaker=speaker,
        source_audio=SimpleUploadedFile("sample.wav", b"abc", content_type="audio/wav"),
        duration_ms=500,
        source_language="en",
        original_transcript="Hello there",
    )

    class FakeTranslationProvider:
        def translate(self, *, text: str, source_language: str, target_language: str) -> str:
            return "Hola a todos"

    class FakeTTSProvider:
        def synthesize(self, *, text: str, language: str) -> bytes:
            return b"fake-audio"

    monkeypatch.setattr("translations.services.get_translation_provider", lambda: FakeTranslationProvider())
    monkeypatch.setattr("translations.services.get_tts_provider", lambda: FakeTTSProvider())

    with caplog.at_level("INFO"):
        TranslationFanoutService.build_translations(
            utterance=utterance,
            transcript="Hello there",
            source_language="en",
            participants=[RoomParticipant(user=speaker), RoomParticipant(user=listener)],
        )

    assert "target=es" in caplog.text
    assert "Hola a todos" in caplog.text
