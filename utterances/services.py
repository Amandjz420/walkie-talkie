import logging
from time import perf_counter

from django.db import transaction
from django.shortcuts import get_object_or_404

from common.choices import InputLanguageMode, UtteranceStatus
from providers.services import get_stt_provider
from realtime.services import RealtimeEventService
from rooms.models import Room
from translations.services import TranslationFanoutService
from utterances.models import Utterance

logger = logging.getLogger(__name__)


class UtteranceQueryService:
    @staticmethod
    def related_queryset():
        return Utterance.objects.select_related("speaker", "room").prefetch_related("translations")

    @classmethod
    def for_room(cls, room: Room):
        return cls.related_queryset().filter(room=room).order_by("-created_at")

    @classmethod
    def get_for_user(cls, *, utterance_id: int, user):
        return get_object_or_404(
            cls.related_queryset(),
            id=utterance_id,
            room__participants__user=user,
        )

    @classmethod
    def get_for_processing(cls, *, utterance_id: int) -> Utterance:
        return (
            cls.related_queryset()
            .prefetch_related("room__participants__user")
            .get(id=utterance_id)
        )


class UtteranceCreationService:
    @staticmethod
    @transaction.atomic
    def create_utterance(*, room: Room, speaker, audio_file, duration_ms: int) -> Utterance:
        utterance = Utterance.objects.create(
            room=room,
            speaker=speaker,
            source_audio=audio_file,
            duration_ms=duration_ms,
            status=UtteranceStatus.UPLOADED,
        )
        transaction.on_commit(
            lambda: RealtimeEventService.broadcast_utterance_event(
                utterance=utterance,
                event_type="utterance.created",
            )
        )
        return utterance


class UtteranceProcessingService:
    FRIENDLY_ERROR_MESSAGES = {
        "processing": "We couldn't process this utterance.",
        "transcription": "We couldn't transcribe this audio.",
        "translation": "We couldn't generate translated outputs for this utterance.",
    }
    EMPTY_TRANSCRIPT_ERROR = "No speech was detected in this audio."

    @classmethod
    def process(cls, *, utterance_id: int) -> Utterance:
        utterance = UtteranceQueryService.get_for_processing(utterance_id=utterance_id)
        step = "processing"
        started_at = perf_counter()
        stt_elapsed_ms = 0.0
        translation_elapsed_ms = 0.0

        try:
            cls._update_status(utterance, status=UtteranceStatus.PROCESSING, error_message=None)
            RealtimeEventService.broadcast_utterance_event(
                utterance=utterance,
                event_type="utterance.processing",
            )

            step = "transcription"
            stt_provider = get_stt_provider()
            language_hint = (
                utterance.speaker.manual_input_language
                if utterance.speaker.input_language_mode == InputLanguageMode.MANUAL
                else None
            )
            stt_started_at = perf_counter()
            stt_result = stt_provider.transcribe(
                file_path=utterance.source_audio.path,
                language_hint=language_hint,
            )
            stt_elapsed_ms = (perf_counter() - stt_started_at) * 1000
            utterance.original_transcript = stt_result.transcript
            utterance.source_language = stt_result.source_language
            cls._save_utterance(
                utterance,
                status=UtteranceStatus.TRANSCRIBED,
                update_fields=["original_transcript", "source_language", "status"],
            )
            RealtimeEventService.broadcast_utterance_event(
                utterance=utterance,
                event_type="utterance.transcribed",
            )
            cls._ensure_transcript_present(utterance.original_transcript)
            logger.info(
                "Utterance %s transcription complete source=%s stt_ms=%.1f transcript=%r",
                utterance.id,
                utterance.source_language or "unknown",
                stt_elapsed_ms,
                cls._preview_text(utterance.original_transcript),
            )

            step = "translation"
            participants = utterance.room.participants.select_related("user").all()
            translation_started_at = perf_counter()
            TranslationFanoutService.build_translations(
                utterance=utterance,
                transcript=utterance.original_transcript,
                source_language=utterance.source_language,
                participants=participants,
            )
            translation_elapsed_ms = (perf_counter() - translation_started_at) * 1000
            cls._update_status(utterance, status=UtteranceStatus.TRANSLATED)
            cls._update_status(utterance, status=UtteranceStatus.COMPLETED)
            RealtimeEventService.broadcast_utterance_event(
                utterance=utterance,
                event_type="utterance.completed",
            )
            total_elapsed_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Utterance %s completed room=%s speaker=%s targets=%s stt_ms=%.1f translation_ms=%.1f total_ms=%.1f",
                utterance.id,
                utterance.room_id,
                utterance.speaker_id,
                utterance.translations.count(),
                stt_elapsed_ms,
                translation_elapsed_ms,
                total_elapsed_ms,
            )
            return UtteranceQueryService.get_for_processing(utterance_id=utterance_id)
        except Exception as exc:
            cls._mark_failed(utterance=utterance, step=step, exc=exc)
            return UtteranceQueryService.get_for_processing(utterance_id=utterance_id)

    @classmethod
    def _update_status(cls, utterance: Utterance, *, status: str, error_message: str | None = "") -> None:
        utterance.status = status
        utterance.error_message = error_message
        utterance.save(update_fields=["status", "error_message", "updated_at"])

    @classmethod
    def _save_utterance(cls, utterance: Utterance, *, status: str, update_fields: list[str]) -> None:
        utterance.status = status
        utterance.save(update_fields=[*update_fields, "updated_at"])

    @classmethod
    def _mark_failed(cls, *, utterance: Utterance, step: str, exc: Exception) -> None:
        logger.exception("Utterance processing failed", extra={"utterance_id": utterance.id, "step": step})
        detail = str(exc).strip()
        friendly_message = cls.FRIENDLY_ERROR_MESSAGES.get(
            step, cls.FRIENDLY_ERROR_MESSAGES["processing"]
        )
        persisted_message = friendly_message if not detail else f"{friendly_message} Detail: {detail}"
        cls._update_status(
            utterance,
            status=UtteranceStatus.FAILED,
            error_message=persisted_message[:1000],
        )
        RealtimeEventService.broadcast_utterance_event(
            utterance=utterance,
            event_type="utterance.failed",
            error={
                "code": "utterance_processing_failed",
                "message": friendly_message,
                "step": step,
            },
        )

    @classmethod
    def _ensure_transcript_present(cls, transcript: str) -> None:
        if transcript.strip():
            return
        raise ValueError(cls.EMPTY_TRANSCRIPT_ERROR)

    @staticmethod
    def _preview_text(text: str, *, limit: int = 160) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[: limit - 3]}..."
