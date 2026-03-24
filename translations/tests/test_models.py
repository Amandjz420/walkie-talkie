import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from rooms.services import RoomService
from translations.models import UtteranceTranslation
from users.models import User
from utterances.models import Utterance


@pytest.mark.django_db
def test_utterance_translation_unique_constraint():
    user = User.objects.create(display_name="Speaker", email="speaker@example.com")
    room = RoomService.create_room(creator=user, name="Room", is_private=False)
    utterance = Utterance.objects.create(
        room=room,
        speaker=user,
        source_audio=SimpleUploadedFile("sample.wav", b"abc", content_type="audio/wav"),
        duration_ms=500,
    )
    UtteranceTranslation.objects.create(
        utterance=utterance,
        target_language="es",
        translated_text="hola",
        tts_audio=SimpleUploadedFile("tts.wav", b"abc", content_type="audio/wav"),
    )

    with pytest.raises(IntegrityError):
        UtteranceTranslation.objects.create(
            utterance=utterance,
            target_language="es",
            translated_text="hola otra vez",
            tts_audio=SimpleUploadedFile("tts2.wav", b"abc", content_type="audio/wav"),
        )
