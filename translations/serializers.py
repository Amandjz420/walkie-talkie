from rest_framework import serializers

from common.serializers import AbsoluteURLSerializerMixin
from translations.models import TranslationFeedback, UtteranceTranslation


class UtteranceTranslationSerializer(AbsoluteURLSerializerMixin, serializers.ModelSerializer):
    utterance_id = serializers.IntegerField(source="utterance.id", read_only=True)
    tts_audio_url = serializers.SerializerMethodField()
    has_audio = serializers.SerializerMethodField()
    tts_audio_format = serializers.SerializerMethodField()
    tts_audio_mime_type = serializers.SerializerMethodField()

    class Meta:
        model = UtteranceTranslation
        fields = (
            "utterance_id",
            "target_language",
            "translated_text",
            "tts_audio_url",
            "tts_audio_format",
            "tts_audio_mime_type",
            "has_audio",
        )

    def get_tts_audio_url(self, obj):
        if not obj.tts_audio:
            return None
        return self.build_absolute_uri(obj.tts_audio.url)

    def get_has_audio(self, obj):
        return bool(obj.tts_audio)

    def get_tts_audio_format(self, obj):
        if not obj.tts_audio:
            return None
        return obj.tts_audio.name.rsplit(".", 1)[-1].lower()

    def get_tts_audio_mime_type(self, obj):
        audio_format = self.get_tts_audio_format(obj)
        if audio_format == "mp3":
            return "audio/mpeg"
        if audio_format == "wav":
            return "audio/wav"
        return None


class TranslationFeedbackSerializer(serializers.ModelSerializer):
    utterance_id = serializers.IntegerField(source="utterance.id", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = TranslationFeedback
        fields = ("id", "utterance_id", "user_id", "reason", "created_at")
        read_only_fields = ("id", "created_at")
