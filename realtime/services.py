from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from realtime.presence import RoomPresenceService
from realtime.serializers import (
    ParticipantEventPayloadSerializer,
    RoomEventSerializer,
    TranslationReadyEventPayloadSerializer,
    UtteranceEventPayloadSerializer,
)
from rooms.models import RoomParticipant
from translations.models import UtteranceTranslation
from utterances.models import Utterance


class RealtimeEventService:
    @staticmethod
    def room_group_name(room_id: int) -> str:
        return f"room_{room_id}"

    @classmethod
    def build_event(cls, *, room_id: int, event_type: str, payload: dict) -> dict:
        return RoomEventSerializer(
            {
                "type": event_type,
                "room_id": room_id,
                "occurred_at": timezone.now(),
                "payload": payload,
            }
        ).data

    @classmethod
    def broadcast_room_event(cls, *, room_id: int, event_type: str, payload: dict) -> None:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            cls.room_group_name(room_id),
            {
                "type": "room.event",
                "event": cls.build_event(room_id=room_id, event_type=event_type, payload=payload),
            },
        )

    @staticmethod
    def get_participant(participant: RoomParticipant) -> RoomParticipant:
        return RoomParticipant.objects.select_related("user", "room").get(id=participant.id)

    @staticmethod
    def get_utterance(utterance: Utterance) -> Utterance:
        return (
            Utterance.objects.select_related("speaker", "room")
            .prefetch_related("translations")
            .get(id=utterance.id)
        )

    @staticmethod
    def get_translation(translation: UtteranceTranslation) -> UtteranceTranslation:
        return UtteranceTranslation.objects.select_related("utterance").get(id=translation.id)

    @classmethod
    def broadcast_participant_joined(
        cls, participant: RoomParticipant, *, presence_kind: str | None = "membership"
    ) -> None:
        participant = cls.get_participant(participant)
        payload = ParticipantEventPayloadSerializer(
            {
                "participant": participant,
                "presence_kind": presence_kind,
            },
            context={"presence_map": RoomPresenceService.presence_map(room_id=participant.room_id)},
        ).data
        cls.broadcast_room_event(
            room_id=participant.room_id,
            event_type="room.participant_joined",
            payload=payload,
        )

    @classmethod
    def broadcast_participant_left(cls, participant: RoomParticipant) -> None:
        participant = cls.get_participant(participant)
        payload = ParticipantEventPayloadSerializer(
            {
                "participant": participant,
                "presence_kind": "offline",
            },
            context={"presence_map": RoomPresenceService.presence_map(room_id=participant.room_id)},
        ).data
        cls.broadcast_room_event(
            room_id=participant.room_id,
            event_type="room.participant_left",
            payload=payload,
        )

    @classmethod
    def broadcast_utterance_event(
        cls, *, utterance: Utterance, event_type: str, error: dict | None = None
    ) -> None:
        payload = UtteranceEventPayloadSerializer(
            {"utterance": cls.get_utterance(utterance), "error": error}
        ).data
        cls.broadcast_room_event(room_id=utterance.room_id, event_type=event_type, payload=payload)

    @classmethod
    def broadcast_translation_ready(
        cls, *, utterance: Utterance, translation: UtteranceTranslation
    ) -> None:
        payload = TranslationReadyEventPayloadSerializer(
            {
                "utterance": cls.get_utterance(utterance),
                "translation": cls.get_translation(translation),
            }
        ).data
        cls.broadcast_room_event(
            room_id=utterance.room_id,
            event_type="utterance.translation_ready",
            payload=payload,
        )
