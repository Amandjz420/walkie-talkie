from functools import lru_cache
import logging
import threading
import time

from django.conf import settings

from providers.base import ProviderConfigurationError, ProviderError, TextToSpeechProvider

logger = logging.getLogger(__name__)

ELEVENLABS_TTS_LANGUAGE_CODES = {
    "ar",
    "bg",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fi",
    "fil",
    "fr",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "ms",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sv",
    "ta",
    "tr",
    "uk",
    "vi",
    "zh",
}

_VOICE_LOCKS: dict[str, threading.Lock] = {}
_VOICE_LOCKS_GUARD = threading.Lock()


def _load_elevenlabs_client_class():
    try:
        from elevenlabs.client import ElevenLabs
    except ImportError as exc:
        raise ProviderConfigurationError(
            "ElevenLabs provider selected but the 'elevenlabs' package is not installed."
        ) from exc
    return ElevenLabs


def _extract_elevenlabs_error_message(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):
            if detail.get("message"):
                return str(detail["message"])
            if detail.get("status"):
                return str(detail["status"])
        if detail:
            return str(detail)
    message = getattr(exc, "message", None)
    if message:
        return str(message)
    return str(exc).strip() or "ElevenLabs request failed."


def _raise_provider_error(exc: Exception, *, action: str) -> None:
    raise ProviderError(f"ElevenLabs {action} failed: {_extract_elevenlabs_error_message(exc)}") from exc


def _normalize_language_code(language: str) -> str:
    normalized = language.strip().split("-")[0].lower()
    if normalized not in ELEVENLABS_TTS_LANGUAGE_CODES:
        raise ProviderError(
            f"ElevenLabs text-to-speech does not support language '{language}'."
        )
    return normalized


def _coerce_audio_bytes(response) -> bytes:
    if isinstance(response, bytes):
        return response
    if isinstance(response, bytearray):
        return bytes(response)
    if hasattr(response, "read"):
        return response.read()
    if isinstance(response, str):
        return response.encode()
    if response is None:
        return b""
    try:
        return b"".join(
            chunk if isinstance(chunk, bytes) else bytes(chunk)
            for chunk in response
            if chunk
        )
    except TypeError as exc:
        raise ProviderError("ElevenLabs returned an unsupported audio payload.") from exc


def _is_retryable_tts_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {409, 429, 500, 502, 503, 504}:
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict) and detail.get("code") == "already_running":
            return True
    return False


def _voice_lock_for(voice_id: str) -> threading.Lock:
    with _VOICE_LOCKS_GUARD:
        lock = _VOICE_LOCKS.get(voice_id)
        if lock is None:
            lock = threading.Lock()
            _VOICE_LOCKS[voice_id] = lock
        return lock


def infer_elevenlabs_audio_extension(output_format: str) -> str:
    normalized = (output_format or "").split("_", 1)[0].lower()
    if normalized in {"mp3", "pcm", "ulaw", "wav", "opus"}:
        return "mp3" if normalized == "mp3" else normalized
    return "mp3"


@lru_cache(maxsize=1)
def get_elevenlabs_client():
    api_key = settings.ELEVENLABS_API_KEY
    if not api_key:
        raise ProviderConfigurationError(
            "ELEVENLABS_API_KEY must be set when using ElevenLabs text-to-speech."
        )
    ElevenLabs = _load_elevenlabs_client_class()
    return ElevenLabs(api_key=api_key)


class ElevenLabsTextToSpeechProvider(TextToSpeechProvider):
    def synthesize(self, *, text: str, language: str) -> bytes:
        voice_id = settings.ELEVENLABS_TTS_VOICE_ID
        if not voice_id:
            raise ProviderConfigurationError(
                "ELEVENLABS_TTS_VOICE_ID must be set when using ElevenLabs text-to-speech."
            )

        client = get_elevenlabs_client()
        language_code = _normalize_language_code(language)
        max_retries = max(0, int(getattr(settings, "ELEVENLABS_TTS_MAX_RETRIES", 2)))
        base_delay = float(getattr(settings, "ELEVENLABS_TTS_RETRY_BASE_DELAY", 0.5))

        with _voice_lock_for(voice_id):
            for attempt in range(max_retries + 1):
                try:
                    response = client.text_to_speech.convert(
                        voice_id=voice_id,
                        output_format=settings.ELEVENLABS_TTS_OUTPUT_FORMAT,
                        text=text,
                        model_id=settings.ELEVENLABS_TTS_MODEL,
                        language_code=language_code,
                    )
                    return _coerce_audio_bytes(response)
                except Exception as exc:
                    if attempt >= max_retries or not _is_retryable_tts_error(exc):
                        _raise_provider_error(exc, action="text-to-speech")
                    delay_seconds = base_delay * (2**attempt)
                    logger.warning(
                        "ElevenLabs TTS retry voice=%s language=%s attempt=%s delay_s=%.2f reason=%s",
                        voice_id,
                        language_code,
                        attempt + 1,
                        delay_seconds,
                        _extract_elevenlabs_error_message(exc),
                    )
                    time.sleep(delay_seconds)
