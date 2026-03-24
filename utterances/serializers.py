from rest_framework import serializers

from common.choices import UtteranceStatus
from common.serializers import AbsoluteURLSerializerMixin
from translations.serializers import UtteranceTranslationSerializer
from utterances.models import Utterance
from users.serializers import UserSummarySerializer


class UtteranceCreateSerializer(serializers.Serializer):
    audio = serializers.FileField()
    duration_ms = serializers.IntegerField(min_value=1)

    SUPPORTED_AUDIO_CONTENT_TYPES = {
        "audio/mp4",
        "audio/mpeg",
        "audio/mp3",
        "audio/m4a",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "video/mp4",
        "video/webm",
    }

    def validate_audio(self, value):
        content_type = getattr(value, "content_type", "") or ""
        normalized_content_type = content_type.split(";", 1)[0].strip().lower()
        if normalized_content_type and normalized_content_type not in self.SUPPORTED_AUDIO_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Unsupported audio type. Use a browser recording such as audio/webm or audio/mp4."
            )
        return value


class UtteranceSerializer(AbsoluteURLSerializerMixin, serializers.ModelSerializer):
    room_id = serializers.IntegerField(source="room.id", read_only=True)
    speaker_id = serializers.IntegerField(source="speaker.id", read_only=True)
    speaker_name = serializers.CharField(source="speaker.display_name", read_only=True)
    speaker = UserSummarySerializer(read_only=True)
    translations = UtteranceTranslationSerializer(many=True, read_only=True)
    preferred_translation = serializers.SerializerMethodField()
    preferred_translation_language = serializers.SerializerMethodField()
    has_preferred_translation = serializers.SerializerMethodField()
    available_translation_languages = serializers.SerializerMethodField()
    translation_count = serializers.SerializerMethodField()
    source_audio_url = serializers.SerializerMethodField()
    source_audio_available = serializers.SerializerMethodField()
    source_language_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()

    class Meta:
        model = Utterance
        fields = (
            "id",
            "room_id",
            "speaker_id",
            "speaker",
            "speaker_name",
            "created_at",
            "source_language",
            "source_language_display",
            "original_transcript",
            "status",
            "status_display",
            "duration_ms",
            "source_audio_url",
            "source_audio_available",
            "translations",
            "translation_count",
            "available_translation_languages",
            "preferred_translation",
            "preferred_translation_language",
            "has_preferred_translation",
            "error_message",
            "error",
        )

    def get_preferred_translation(self, obj):
        translation = self._get_preferred_translation(obj)
        if not translation:
            return None
        return UtteranceTranslationSerializer(translation, context=self.context).data

    def get_preferred_translation_language(self, obj):
        translation = self._get_preferred_translation(obj)
        return translation.target_language if translation else None

    def get_has_preferred_translation(self, obj):
        return self._get_preferred_translation(obj) is not None

    def get_available_translation_languages(self, obj):
        return sorted(translation.target_language for translation in obj.translations.all())

    def get_translation_count(self, obj):
        return len(obj.translations.all())

    def get_source_audio_url(self, obj):
        if not obj.source_audio:
            return None
        return self.build_absolute_uri(obj.source_audio.url)

    def get_source_audio_available(self, obj):
        return bool(obj.source_audio)

    def get_source_language_display(self, obj):
        return obj.source_language or "Pending detection"

    def get_status_display(self, obj):
        return UtteranceStatus(obj.status).label if obj.status else None

    def get_error(self, obj):
        if not obj.error_message:
            return None
        return {
            "code": "utterance_processing_failed",
            "message": obj.error_message,
        }

    def _get_preferred_translation(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        for translation in obj.translations.all():
            if translation.target_language == user.preferred_output_language:
                return translation
        return None


class RealtimeUtteranceSerializer(UtteranceSerializer):
    pass
