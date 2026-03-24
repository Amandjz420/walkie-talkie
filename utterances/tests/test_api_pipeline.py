import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from common.choices import UtteranceStatus
from translations.serializers import UtteranceTranslationSerializer
from rooms.models import RoomParticipant
from rooms.services import RoomService
from users.models import User
from utterances.models import Utterance
from utterances.serializers import UtteranceCreateSerializer


@pytest.mark.django_db(transaction=True)
def test_upload_triggers_async_processing_and_reuses_language_outputs(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    speaker = User.objects.create(
        display_name="Speaker", email="speaker@example.com", preferred_output_language="en"
    )
    listener_one = User.objects.create(
        display_name="Listener One", email="one@example.com", preferred_output_language="es"
    )
    listener_two = User.objects.create(
        display_name="Listener Two", email="two@example.com", preferred_output_language="es"
    )
    room = RoomService.create_room(creator=speaker, name="Room", is_private=False)
    RoomParticipant.objects.create(room=room, user=listener_one)
    RoomParticipant.objects.create(room=room, user=listener_two)

    client = APIClient()
    client.credentials(HTTP_X_DEMO_USER_ID=str(speaker.id))
    room_ref = room.code.lower()
    response = client.post(
        f"/api/rooms/{room_ref}/utterances/",
        {
            "audio": SimpleUploadedFile("clip.wav", b"RIFF....WAVE", content_type="audio/wav"),
            "duration_ms": 1200,
        },
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["room_id"] == room.id
    assert response.data["speaker_id"] == speaker.id
    assert response.data["source_audio_available"] is True
    utterance = Utterance.objects.prefetch_related("translations").get(id=response.data["id"])
    assert utterance.status == UtteranceStatus.COMPLETED
    assert utterance.original_transcript == "Mock transcript for clip.wav"
    assert utterance.source_language == "en"
    assert utterance.translations.count() == 2
    assert sorted(utterance.translations.values_list("target_language", flat=True)) == ["en", "es"]

    feed_response = client.get(f"/api/rooms/{room_ref}/utterances/")
    assert feed_response.status_code == 200
    assert feed_response.data[0]["translation_count"] == 2
    assert feed_response.data[0]["available_translation_languages"] == ["en", "es"]
    assert feed_response.data[0]["has_preferred_translation"] is True
    assert feed_response.data[0]["preferred_translation"]["target_language"] == "en"


def test_utterance_create_serializer_accepts_browser_audio_types():
    webm_serializer = UtteranceCreateSerializer(
        data={
            "audio": SimpleUploadedFile(
                "recording.webm",
                b"webm-bytes",
                content_type="audio/webm;codecs=opus",
            ),
            "duration_ms": 1000,
        }
    )
    mp4_serializer = UtteranceCreateSerializer(
        data={
            "audio": SimpleUploadedFile(
                "recording.mp4",
                b"mp4-bytes",
                content_type="audio/mp4",
            ),
            "duration_ms": 1000,
        }
    )

    assert webm_serializer.is_valid(), webm_serializer.errors
    assert mp4_serializer.is_valid(), mp4_serializer.errors


@pytest.mark.django_db
def test_translation_serializer_exposes_mp3_metadata():
    speaker = User.objects.create(
        display_name="Speaker",
        email="speaker-metadata@example.com",
        preferred_output_language="en",
    )
    room = RoomService.create_room(creator=speaker, name="Metadata Room", is_private=False)
    utterance = Utterance.objects.create(
        room=room,
        speaker=speaker,
        source_audio=SimpleUploadedFile("clip.wav", b"RIFF....WAVE", content_type="audio/wav"),
        duration_ms=1000,
    )
    translation = utterance.translations.create(
        target_language="hi",
        translated_text="नमस्ते",
        tts_audio=SimpleUploadedFile("tts.mp3", b"ID3fake", content_type="audio/mpeg"),
    )

    data = UtteranceTranslationSerializer(translation).data

    assert data["tts_audio_format"] == "mp3"
    assert data["tts_audio_mime_type"] == "audio/mpeg"
