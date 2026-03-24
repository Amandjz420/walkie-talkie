from rest_framework import serializers

from rooms.serializers import RoomParticipantSerializer
from translations.serializers import UtteranceTranslationSerializer
from utterances.serializers import RealtimeUtteranceSerializer


class ProcessingErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    step = serializers.CharField(required=False, allow_null=True)


class ParticipantEventPayloadSerializer(serializers.Serializer):
    participant = RoomParticipantSerializer()
    presence_kind = serializers.CharField(required=False, allow_null=True)


class UtteranceEventPayloadSerializer(serializers.Serializer):
    utterance = RealtimeUtteranceSerializer()
    error = ProcessingErrorSerializer(required=False, allow_null=True)


class TranslationReadyEventPayloadSerializer(serializers.Serializer):
    utterance = RealtimeUtteranceSerializer()
    translation = UtteranceTranslationSerializer()


class RoomEventSerializer(serializers.Serializer):
    type = serializers.CharField()
    room_id = serializers.IntegerField()
    occurred_at = serializers.DateTimeField()
    payload = serializers.JSONField()
