from django.conf import settings
from django.db import models

from utterances.models import Utterance


def tts_audio_upload_to(instance, filename: str) -> str:
    return f"utterances/tts/{instance.utterance.room_id}/{instance.target_language}/{filename}"


class UtteranceTranslation(models.Model):
    utterance = models.ForeignKey(
        Utterance, on_delete=models.CASCADE, related_name="translations"
    )
    target_language = models.CharField(max_length=16)
    translated_text = models.TextField()
    tts_audio = models.FileField(upload_to=tts_audio_upload_to)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["utterance", "target_language"], name="unique_utterance_translation"
            )
        ]

    def __str__(self) -> str:
        return f"{self.utterance_id} -> {self.target_language}"


class TranslationFeedback(models.Model):
    utterance = models.ForeignKey(
        Utterance, on_delete=models.CASCADE, related_name="feedback_items"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="translation_feedback"
    )
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Feedback by {self.user_id} on {self.utterance_id}"
