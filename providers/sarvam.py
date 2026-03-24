import base64
import mimetypes
from functools import lru_cache
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.conf import settings

from providers.base import (
    ProviderConfigurationError,
    ProviderError,
    SpeechToTextProvider,
    SpeechToTextResult,
    TextToSpeechProvider,
    TranslationProvider,
)

SARVAM_LANGUAGE_CODES = {
    "as": "as-IN",
    "as-IN": "as-IN",
    "bn": "bn-IN",
    "bn-IN": "bn-IN",
    "brx": "brx-IN",
    "brx-IN": "brx-IN",
    "doi": "doi-IN",
    "doi-IN": "doi-IN",
    "en": "en-IN",
    "en-IN": "en-IN",
    "gu": "gu-IN",
    "gu-IN": "gu-IN",
    "hi": "hi-IN",
    "hi-IN": "hi-IN",
    "kn": "kn-IN",
    "kn-IN": "kn-IN",
    "kok": "kok-IN",
    "kok-IN": "kok-IN",
    "ks": "ks-IN",
    "ks-IN": "ks-IN",
    "mai": "mai-IN",
    "mai-IN": "mai-IN",
    "ml": "ml-IN",
    "ml-IN": "ml-IN",
    "mni": "mni-IN",
    "mni-IN": "mni-IN",
    "mr": "mr-IN",
    "mr-IN": "mr-IN",
    "ne": "ne-IN",
    "ne-IN": "ne-IN",
    "od": "od-IN",
    "od-IN": "od-IN",
    "or": "od-IN",
    "pa": "pa-IN",
    "pa-IN": "pa-IN",
    "sa": "sa-IN",
    "sa-IN": "sa-IN",
    "sat": "sat-IN",
    "sat-IN": "sat-IN",
    "sd": "sd-IN",
    "sd-IN": "sd-IN",
    "ta": "ta-IN",
    "ta-IN": "ta-IN",
    "te": "te-IN",
    "te-IN": "te-IN",
    "ur": "ur-IN",
    "ur-IN": "ur-IN",
}

SARVAM_STT_LANGUAGE_CODES = set(SARVAM_LANGUAGE_CODES.values())
SARVAM_TRANSLATION_LANGUAGE_CODES = set(SARVAM_LANGUAGE_CODES.values())
SARVAM_TTS_LANGUAGE_CODES = {
    "bn-IN",
    "en-IN",
    "gu-IN",
    "hi-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
}

AUDIO_CODEC_BY_EXTENSION = {
    ".aac": "aac",
    ".aiff": "aiff",
    ".amr": "amr",
    ".flac": "flac",
    ".m4a": "x-m4a",
    ".mp3": "mp3",
    ".mp4": "mp4",
    ".ogg": "ogg",
    ".opus": "opus",
    ".pcm": "pcm_raw",
    ".wav": "wav",
    ".webm": "webm",
    ".wma": "x-ms-wma",
}

SARVAM_STT_PASSTHROUGH_EXTENSIONS = {
    ".aac",
    ".flac",
    ".mp3",
    ".ogg",
    ".wav",
}


def _normalize_language(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.strip()
    if normalized in SARVAM_LANGUAGE_CODES:
        return SARVAM_LANGUAGE_CODES[normalized]
    base_code = normalized.split("-")[0].lower()
    return SARVAM_LANGUAGE_CODES.get(base_code)


def _to_app_language(code: str | None) -> str:
    if not code:
        return "unknown"
    return code.split("-")[0].lower()


def _load_sarvam_client_class():
    try:
        from sarvamai import SarvamAI
    except ImportError as exc:
        raise ProviderConfigurationError(
            "Sarvam provider selected but the 'sarvamai' package is not installed."
        ) from exc
    return SarvamAI


def _extract_sarvam_error_message(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    return str(exc).strip() or "Sarvam request failed."


def _raise_provider_error(exc: Exception, *, action: str) -> None:
    raise ProviderError(f"Sarvam {action} failed: {_extract_sarvam_error_message(exc)}") from exc


def _infer_audio_codec(file_path: str) -> str | None:
    return AUDIO_CODEC_BY_EXTENSION.get(Path(file_path).suffix.lower())


def _infer_content_type(file_path: str) -> str:
    guessed_type, _ = mimetypes.guess_type(file_path)
    return guessed_type or "application/octet-stream"


def _should_retry_stt_with_transcode(exc: Exception) -> bool:
    return "Failed to read the file" in _extract_sarvam_error_message(exc)


def _should_pre_normalize_for_stt(file_path: str) -> bool:
    return Path(file_path).suffix.lower() not in SARVAM_STT_PASSTHROUGH_EXTENSIONS


def _transcode_audio_to_wav(input_path: str, output_path: str) -> None:
    ffmpeg_binary = getattr(settings, "FFMPEG_BINARY", "ffmpeg")
    resolved_binary = shutil.which(ffmpeg_binary) or ffmpeg_binary
    try:
        subprocess.run(
            [
                resolved_binary,
                "-y",
                "-i",
                input_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise ProviderError("Audio normalization via ffmpeg failed before speech-to-text.") from exc


@lru_cache(maxsize=1)
def get_sarvam_client():
    api_key = settings.SARVAM_API_KEY
    if not api_key:
        raise ProviderConfigurationError("SARVAM_API_KEY must be set when using Sarvam providers.")
    SarvamAI = _load_sarvam_client_class()
    return SarvamAI(api_subscription_key=api_key)


def _require_supported_language(code: str, *, provider_name: str, supported_languages: set[str]) -> str:
    mapped = _normalize_language(code)
    if mapped and mapped in supported_languages:
        return mapped
    raise ProviderError(
        f"Sarvam {provider_name} does not support language '{code}'. "
        "Use a supported Sarvam language code or a compatible base code."
    )


class SarvamSpeechToTextProvider(SpeechToTextProvider):
    def transcribe(self, *, file_path: str, language_hint: str | None = None) -> SpeechToTextResult:
        client = get_sarvam_client()
        request_kwargs = {
            "model": settings.SARVAM_STT_MODEL,
            "mode": settings.SARVAM_STT_MODE,
        }
        codec = _infer_audio_codec(file_path)
        if codec:
            request_kwargs["input_audio_codec"] = codec
        if language_hint:
            request_kwargs["language_code"] = _require_supported_language(
                language_hint,
                provider_name="speech-to-text",
                supported_languages=SARVAM_STT_LANGUAGE_CODES,
            )
        if _should_pre_normalize_for_stt(file_path):
            with tempfile.TemporaryDirectory() as temp_dir:
                normalized_path = str(Path(temp_dir) / f"{Path(file_path).stem}.wav")
                _transcode_audio_to_wav(file_path, normalized_path)
                normalized_kwargs = {**request_kwargs, "input_audio_codec": "wav"}
                try:
                    return self._transcribe_file(
                        client=client,
                        file_path=normalized_path,
                        request_kwargs=normalized_kwargs,
                    )
                except Exception as exc:
                    _raise_provider_error(exc, action="speech-to-text")
        try:
            return self._transcribe_file(client=client, file_path=file_path, request_kwargs=request_kwargs)
        except Exception as exc:
            if not _should_retry_stt_with_transcode(exc):
                _raise_provider_error(exc, action="speech-to-text")
            with tempfile.TemporaryDirectory() as temp_dir:
                normalized_path = str(Path(temp_dir) / f"{Path(file_path).stem}.wav")
                try:
                    _transcode_audio_to_wav(file_path, normalized_path)
                except ProviderError:
                    _raise_provider_error(exc, action="speech-to-text")
                retry_kwargs = {**request_kwargs, "input_audio_codec": "wav"}
                try:
                    return self._transcribe_file(
                        client=client,
                        file_path=normalized_path,
                        request_kwargs=retry_kwargs,
                    )
                except Exception as retry_exc:
                    _raise_provider_error(retry_exc, action="speech-to-text")

    @staticmethod
    def _transcribe_file(*, client, file_path: str, request_kwargs: dict) -> SpeechToTextResult:
        with open(file_path, "rb") as audio_file:
            response = client.speech_to_text.transcribe(
                file=(Path(file_path).name, audio_file, _infer_content_type(file_path)),
                **request_kwargs,
            )
        return SpeechToTextResult(
            transcript=response.transcript,
            source_language=_to_app_language(getattr(response, "language_code", None)),
        )


class SarvamTranslationProvider(TranslationProvider):
    def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        client = get_sarvam_client()
        try:
            response = client.text.translate(
                input=text,
                source_language_code=_require_supported_language(
                    source_language,
                    provider_name="translation",
                    supported_languages=SARVAM_TRANSLATION_LANGUAGE_CODES,
                ),
                target_language_code=_require_supported_language(
                    target_language,
                    provider_name="translation",
                    supported_languages=SARVAM_TRANSLATION_LANGUAGE_CODES,
                ),
                model=settings.SARVAM_TRANSLATION_MODEL,
            )
        except Exception as exc:
            _raise_provider_error(exc, action="translation")
        return response.translated_text


class SarvamTextToSpeechProvider(TextToSpeechProvider):
    def synthesize(self, *, text: str, language: str) -> bytes:
        client = get_sarvam_client()
        try:
            response = client.text_to_speech.convert(
                text=text,
                target_language_code=_require_supported_language(
                    language,
                    provider_name="text-to-speech",
                    supported_languages=SARVAM_TTS_LANGUAGE_CODES,
                ),
                model=settings.SARVAM_TTS_MODEL,
                speaker=settings.SARVAM_TTS_SPEAKER,
                pace=settings.SARVAM_TTS_PACE,
                output_audio_codec=settings.SARVAM_TTS_AUDIO_FORMAT,
            )
        except Exception as exc:
            _raise_provider_error(exc, action="text-to-speech")
        if not response.audios:
            raise ProviderError("Sarvam text-to-speech returned no audio payloads.")
        return base64.b64decode(response.audios[0])
