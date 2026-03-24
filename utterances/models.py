from django.conf import settings
from django.db import models

from common.choices import UtteranceStatus
from rooms.models import Room


def source_audio_upload_to(instance, filename: str) -> str:
    return f"utterances/source/{instance.room_id}/{instance.speaker_id}/{filename}"


class Utterance(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="utterances")
    speaker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="utterances"
    )
    source_audio = models.FileField(upload_to=source_audio_upload_to)
    source_language = models.CharField(max_length=16, blank=True, null=True)
    original_transcript = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16, choices=UtteranceStatus.choices, default=UtteranceStatus.UPLOADED
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Utterance {self.pk} in room {self.room_id}"
