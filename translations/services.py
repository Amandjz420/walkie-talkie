from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from time import perf_counter

from django.conf import settings
from django.core.files.base import ContentFile

from providers.services import get_translation_provider, get_tts_provider, get_tts_storage_extension
from realtime.services import RealtimeEventService
from translations.models import UtteranceTranslation

logger = logging.getLogger(__name__)


class TranslationFanoutService:
    LOG_TEXT_PREVIEW_CHARS = 160

    @staticmethod
    def distinct_target_languages(*, participants, speaker) -> list[str]:
        languages = {participant.user.preferred_output_language for participant in participants}
        speaker_language = getattr(speaker, "preferred_output_language", None)
        if speaker_language:
            languages.add(speaker_language)
        return sorted(language for language in languages if language)

    @classmethod
    def build_translations(cls, *, utterance, transcript: str, source_language: str, participants):
        cleaned_transcript = transcript.strip()
        target_languages = cls.distinct_target_languages(participants=participants, speaker=utterance.speaker)
        if not target_languages:
            return []

        max_workers = min(
            len(target_languages),
            max(1, getattr(settings, "TRANSLATION_FANOUT_MAX_WORKERS", 4)),
        )
        created_by_language = {}

        if max_workers == 1:
            for target_language in target_languages:
                rendered = cls._render_translation_assets(
                    utterance_id=utterance.id,
                    target_language=target_language,
                    transcript=cleaned_transcript,
                    source_language=source_language,
                )
                translation = cls._persist_translation(utterance=utterance, **rendered)
                created_by_language[target_language] = translation
                RealtimeEventService.broadcast_translation_ready(
                    utterance=utterance,
                    translation=translation,
                )
            return [created_by_language[language] for language in target_languages]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    cls._render_translation_assets,
                    utterance_id=utterance.id,
                    target_language=target_language,
                    transcript=cleaned_transcript,
                    source_language=source_language,
                ): target_language
                for target_language in target_languages
            }
            for future in as_completed(futures):
                rendered = future.result()
                translation = cls._persist_translation(utterance=utterance, **rendered)
                created_by_language[translation.target_language] = translation
                RealtimeEventService.broadcast_translation_ready(
                    utterance=utterance,
                    translation=translation,
                )

        return [created_by_language[language] for language in target_languages]

    @staticmethod
    def _render_translation_assets(
        *,
        utterance_id: int,
        target_language: str,
        transcript: str,
        source_language: str,
    ):
        translation_provider = get_translation_provider()
        tts_provider = get_tts_provider()
        started_at = perf_counter()
        translation_started_at = started_at
        translated_text = TranslationFanoutService._resolve_text_for_target_language(
            transcript=transcript,
            source_language=source_language,
            target_language=target_language,
            translation_provider=translation_provider,
        )
        translation_elapsed_ms = (perf_counter() - translation_started_at) * 1000
        tts_started_at = perf_counter()
        audio_bytes = tts_provider.synthesize(text=translated_text, language=target_language)
        tts_elapsed_ms = (perf_counter() - tts_started_at) * 1000
        total_elapsed_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "Utterance %s translation ready target=%s source=%s translate_ms=%.1f tts_ms=%.1f total_ms=%.1f text=%r",
            utterance_id,
            target_language,
            source_language or "unknown",
            translation_elapsed_ms,
            tts_elapsed_ms,
            total_elapsed_ms,
            TranslationFanoutService._preview_text(translated_text),
        )
        return {
            "target_language": target_language,
            "translated_text": translated_text,
            "audio_bytes": audio_bytes,
        }

    @staticmethod
    def _persist_translation(*, utterance, target_language: str, translated_text: str, audio_bytes: bytes):
        translation, _ = UtteranceTranslation.objects.update_or_create(
            utterance=utterance,
            target_language=target_language,
            defaults={"translated_text": translated_text},
        )
        extension = get_tts_storage_extension()
        translation.tts_audio.save(
            f"utterance_{utterance.id}_{target_language}.{extension}",
            ContentFile(audio_bytes),
            save=True,
        )
        return translation

    @staticmethod
    def _resolve_text_for_target_language(
        *,
        transcript: str,
        source_language: str,
        target_language: str,
        translation_provider,
    ) -> str:
        if source_language and source_language.lower() == target_language.lower():
            return transcript
        return translation_provider.translate(
            text=transcript,
            source_language=source_language,
            target_language=target_language,
        )

    @classmethod
    def _preview_text(cls, text: str) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= cls.LOG_TEXT_PREVIEW_CHARS:
            return cleaned
        return f"{cleaned[: cls.LOG_TEXT_PREVIEW_CHARS - 3]}..."
